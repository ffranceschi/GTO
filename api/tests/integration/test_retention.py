"""T086 — retenção, fixação e uso de disco (FR-028 a FR-030)."""

from __future__ import annotations

import time
from datetime import timedelta
from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient

from gto_api.db.models import SolveRow, now_utc
from gto_api.main import create_app
from gto_api.settings import Settings
from tests.fakes import FakeJobRunner
from tests.helpers import small_request, wait_solve


def solved(c: TestClient, pot: float) -> dict[str, Any]:
    s = c.post("/api/v1/solves", json=small_request(pot=pot)).json()
    return wait_solve(c, s["id"], ("completed",))


def run_cleanup(c: TestClient) -> list[dict[str, Any]]:
    job_id = c.portal.call(c.app.state.schedule_cleanup)  # type: ignore[attr-defined]
    msgs = []
    with c.websocket_connect(f"/api/v1/jobs/{job_id}/events") as ws:
        while True:
            m = ws.receive_json()
            msgs.append(m)
            if m["type"] == "finished":
                return msgs


def test_cleanup_respeita_fixadas_e_ativos(tmp_path: Path) -> None:
    app = create_app(
        Settings(data_dir=tmp_path, use_processes=False, solution_retention_days=0), FakeJobRunner()
    )
    with TestClient(app) as c:
        a, b = solved(c, 10), solved(c, 11)
        assert (
            c.patch(f"/api/v1/solves/{b['id']}", json={"pinned": True}).json()["expires_at"] is None
        )
        active = c.post(
            "/api/v1/solves",
            json=small_request(
                pot=12, params={"target_exploitability_pct": 1e-9, "time_limit_s": 60}
            ),
        ).json()
        wait_solve(c, active["id"], ("running",))
        time.sleep(0.05)
        msgs = run_cleanup(c)
        assert msgs[-1]["status"] == "completed"
        prog = [m["progress"] for m in msgs if m["type"] == "progress"]
        assert prog == sorted(prog)
        ga = c.get(f"/api/v1/solves/{a['id']}").json()
        assert ga["status"] == "expired"
        assert not (tmp_path / "solutions" / a["input_hash"]).exists()
        assert c.get(f"/api/v1/solves/{b['id']}").json()["status"] == "completed"
        assert (tmp_path / "solutions" / b["input_hash"]).exists()
        assert c.get(f"/api/v1/solves/{active['id']}").json()["status"] == "running"
        c.delete(f"/api/v1/solves/{active['id']}")


def test_fixar_storage_e_last_used(client: TestClient) -> None:
    s = solved(client, 10)
    assert s["expires_at"] is not None
    p = client.patch(f"/api/v1/solves/{s['id']}", json={"pinned": True}).json()
    assert p["pinned"] is True and p["expires_at"] is None
    up = client.patch(f"/api/v1/solves/{s['id']}", json={"pinned": False}).json()
    assert up["pinned"] is False and up["expires_at"] is not None
    st = client.get("/api/v1/storage").json()
    assert st["solutions"] >= 1 and st["total_bytes"] >= s["size_bytes"]
    assert st["retention_days"] == 30 and "pinned" in st and "expiring_soon" in st
    # expirando em ≤ 7 dias
    with client.app.state.db.session() as db:  # type: ignore[attr-defined]
        db.get(SolveRow, s["id"]).last_used_at = now_utc() - timedelta(days=25)
    assert client.get("/api/v1/storage").json()["expiring_soon"] == 1
    # consulta de nó atualiza last_used_at no máximo 1×/min
    client.get(f"/api/v1/solves/{s['id']}/nodes")
    t1 = client.get(f"/api/v1/solves/{s['id']}").json()["last_used_at"]
    client.get(f"/api/v1/solves/{s['id']}/nodes")
    assert client.get(f"/api/v1/solves/{s['id']}").json()["last_used_at"] == t1
    assert client.get("/api/v1/storage").json()["expiring_soon"] == 0


def test_fixar_sem_solucao_409(client: TestClient) -> None:
    a = client.post(
        "/api/v1/solves",
        json=small_request(pot=13, params={"target_exploitability_pct": 1e-9, "time_limit_s": 60}),
    ).json()
    assert client.patch(f"/api/v1/solves/{a['id']}", json={"pinned": True}).status_code == 409
    client.delete(f"/api/v1/solves/{a['id']}")


def test_cleanup_remove_equity_com_mais_de_24h(client: TestClient) -> None:
    from gto_api.db.models import EquityJobRow

    with client.app.state.db.session() as db:  # type: ignore[attr-defined]
        db.add(
            EquityJobRow(
                id="old",
                status="completed",
                request_json={},
                finished_at=now_utc() - timedelta(hours=25),
            )
        )
        db.add(EquityJobRow(id="new", status="completed", request_json={}, finished_at=now_utc()))
    run_cleanup(client)
    with client.app.state.db.session() as db:  # type: ignore[attr-defined]
        assert db.get(EquityJobRow, "old") is None and db.get(EquityJobRow, "new") is not None
