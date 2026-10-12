"""T085 — exportar/importar soluções via API (jobs da raia aux)."""

from __future__ import annotations

import time
from datetime import timedelta
from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient

from gto_api.db.models import AuxJobRow, now_utc
from gto_api.main import create_app
from gto_api.settings import Settings
from tests.fakes import FakeJobRunner
from tests.helpers import small_request, wait_solve


def wait_aux(
    client: TestClient, job_id: str, statuses: tuple[str, ...], timeout: float = 30
) -> dict[str, Any]:
    t0 = time.monotonic()
    while True:
        body: dict[str, Any] = client.get(f"/api/v1/aux-jobs/{job_id}").json()
        if body["status"] in statuses:
            return body
        assert time.monotonic() - t0 < timeout, body
        time.sleep(0.05)


def solved(client: TestClient, **over: Any) -> dict[str, Any]:
    s = client.post("/api/v1/solves", json=small_request(**over)).json()
    return wait_solve(client, s["id"], ("completed",))


def test_exportar_baixar_e_importar(client: TestClient, tmp_path: Path) -> None:
    s = solved(client)
    r = client.post(f"/api/v1/solves/{s['id']}/exports")
    assert r.status_code == 202, r.text
    job = r.json()
    assert job["kind"] == "export" and job["solve_id"] == s["id"]
    early = client.get(f"/api/v1/aux-jobs/{job['id']}/file")
    assert early.status_code in (200, 409)
    with client.websocket_connect(f"/api/v1/jobs/{job['id']}/events") as ws:
        kinds = []
        while True:
            m = ws.receive_json()
            kinds.append(m["job_kind"])
            if m["type"] == "finished":
                break
    assert set(kinds) == {"export"} and m["status"] == "completed"
    done = wait_aux(client, job["id"], ("completed",))
    assert done["progress"] == 1 and done["download_url"] == f"/api/v1/aux-jobs/{job['id']}/file"
    assert done["file_expires_at"]
    f = client.get(done["download_url"])
    assert f.status_code == 200 and f.headers["content-type"] == "application/octet-stream"
    path = tmp_path / "sol.npz"
    path.write_bytes(f.content)
    # exportar conta como uso (FR-028)
    assert client.get(f"/api/v1/solves/{s['id']}").json()["last_used_at"] is not None

    imp = client.post(
        "/api/v1/solutions/import",
        files={"file": ("sol.npz", path.read_bytes(), "application/octet-stream")},
    )
    assert imp.status_code == 202, imp.text
    idone = wait_aux(client, imp.json()["id"], ("completed",))
    new = client.get(f"/api/v1/solves/{idone['solve_id']}").json()
    assert new["origin"] == "import" and new["status"] == "completed"
    assert (
        new["exploitability_pct"] == s["exploitability_pct"]
        and new["iterations"] == s["iterations"]
    )
    a = client.get(f"/api/v1/solves/{s['id']}/nodes", params={"path": "x"}).json()
    b = client.get(f"/api/v1/solves/{new['id']}/nodes", params={"path": "x"}).json()
    assert a["actions"] == b["actions"] and a["combos"] == b["combos"]


def test_download_expira_em_24h(client: TestClient) -> None:
    s = solved(client)
    job = client.post(f"/api/v1/solves/{s['id']}/exports").json()
    wait_aux(client, job["id"], ("completed",))
    with client.app.state.db.session() as db:  # type: ignore[attr-defined]
        row = db.get(AuxJobRow, job["id"])
        row.finished_at = now_utc() - timedelta(hours=25)
    r = client.get(f"/api/v1/aux-jobs/{job['id']}/file")
    assert r.status_code == 410 and r.json()["code"] == "arquivo_expirado"


def test_import_invalido_e_grande_demais(client: TestClient, tmp_path: Path) -> None:
    r = client.post(
        "/api/v1/solutions/import", files={"file": ("x.npz", b"lixo", "application/octet-stream")}
    )
    assert r.status_code == 202
    j = wait_aux(client, r.json()["id"], ("failed",))
    assert j["error"]["code"] == "arquivo_invalido"
    app = create_app(
        Settings(data_dir=tmp_path / "d", use_processes=False, max_import_bytes=10), FakeJobRunner()
    )
    with TestClient(app) as c:
        big = c.post(
            "/api/v1/solutions/import",
            files={"file": ("x.npz", b"0" * 100, "application/octet-stream")},
        )
        assert big.status_code == 413 and big.json()["code"] == "arquivo_grande_demais"


def test_exportacao_roda_com_a_raia_solve_ocupada(client: TestClient) -> None:
    s = solved(client)
    busy = client.post(
        "/api/v1/solves",
        json=small_request(pot=17, params={"target_exploitability_pct": 1e-9, "time_limit_s": 60}),
    ).json()
    wait_solve(client, busy["id"], ("running",))
    job = client.post(f"/api/v1/solves/{s['id']}/exports").json()
    wait_aux(client, job["id"], ("completed",), timeout=10)
    assert client.get(f"/api/v1/solves/{busy['id']}").json()["status"] == "running"
    client.delete(f"/api/v1/solves/{busy['id']}")


def test_exportar_sem_solucao_409(client: TestClient) -> None:
    busy = client.post(
        "/api/v1/solves",
        json=small_request(pot=19, params={"target_exploitability_pct": 1e-9, "time_limit_s": 60}),
    ).json()
    r = client.post(f"/api/v1/solves/{busy['id']}/exports")
    assert r.status_code == 409
    client.delete(f"/api/v1/solves/{busy['id']}")
