"""T097 — latência de controle (SC-008) com o runner de processos real (com warm-up)."""

from __future__ import annotations

import json
import os
import time
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from gto_api.main import create_app
from gto_api.settings import Settings
from tests.helpers import wait_solve

FIXTURES = Path(__file__).resolve().parents[3] / "engine/tests/fixtures"


@pytest.fixture(scope="module")
def proc_client(tmp_path_factory: pytest.TempPathFactory) -> Iterator[TestClient]:
    os.environ["GTO_EXCHANGE_CHUNK_BYTES"] = (
        "512"  # exportação lenta o bastante para cancelar no meio
    )
    app = create_app(
        Settings(
            data_dir=tmp_path_factory.mktemp("lat"), use_processes=True, periodic_cleanup=False
        )
    )
    with TestClient(app) as c:
        t0 = time.monotonic()
        while c.get("/api/v1/health").status_code != 200:
            assert time.monotonic() - t0 < 120
            time.sleep(0.1)
        yield c
    os.environ.pop("GTO_EXCHANGE_CHUNK_BYTES", None)


def turn_request(**params: Any) -> dict[str, Any]:
    d = json.loads((FIXTURES / "turn_reference.json").read_text())
    return {
        "spot": d["spot"],
        "tree": d["tree"],
        "params": {"target_exploitability_pct": 1e-9, "time_limit_s": 120, **params},
    }


def wait_ws(ws: Any, pred: Any, t0: float, limit: float) -> float:
    while True:
        m = ws.receive_json()
        if pred(m):
            dt = time.monotonic() - t0
            assert dt < limit, (m, dt)
            return dt
        assert m["type"] != "finished" or pred(m), m


def test_pause_resume_stop_cancel_em_menos_de_1s(proc_client: TestClient) -> None:
    c = proc_client
    c.post("/api/v1/solves", json=turn_request(seed=1))  # aquece o caminho HTTP
    t0 = time.perf_counter()
    r = c.post("/api/v1/solves", json=turn_request(seed=2))
    assert r.status_code == 202 and time.perf_counter() - t0 <= 0.2
    first = c.get("/api/v1/solves").json()[-1]["id"]
    c.delete(f"/api/v1/solves/{first}")
    sid = r.json()["id"]
    wait_solve(c, sid, ("running",), timeout=30)
    with c.websocket_connect(f"/api/v1/jobs/{sid}/events") as ws:
        ws.receive_json()
        wait_ws(ws, lambda m: m["type"] == "progress", time.monotonic(), 5)
        t = time.monotonic()
        c.post(f"/api/v1/solves/{sid}/pause")
        wait_ws(ws, lambda m: m.get("status") == "paused", t, 1.0)
        t = time.monotonic()
        c.post(f"/api/v1/solves/{sid}/resume")
        wait_ws(ws, lambda m: m.get("status") == "running", t, 1.0)
        t = time.monotonic()
        c.post(f"/api/v1/solves/{sid}/stop")
        wait_ws(ws, lambda m: m.get("status") == "stopping", t, 1.0)
        # cancelar durante a finalização
        wait_ws(ws, lambda m: m.get("status") == "finalizing", time.monotonic(), 30)
        t = time.monotonic()
        c.delete(f"/api/v1/solves/{sid}")
        wait_ws(ws, lambda m: m["type"] == "finished" and m["status"] == "cancelled", t, 1.0)


def test_cancelar_exportacao_em_menos_de_1s(proc_client: TestClient) -> None:
    c = proc_client
    s = c.post(
        "/api/v1/solves", json=turn_request(target_exploitability_pct=5, time_limit_s=60)
    ).json()
    done = wait_solve(c, s["id"], ("completed",), timeout=120)
    job = c.post(f"/api/v1/solves/{done['id']}/exports").json()
    with c.websocket_connect(f"/api/v1/jobs/{job['id']}/events") as ws:
        ws.receive_json()
        wait_ws(
            ws,
            lambda m: m["type"] == "progress" and (m.get("progress") or 0) > 0,
            time.monotonic(),
            10,
        )
        t = time.monotonic()
        assert c.delete(f"/api/v1/aux-jobs/{job['id']}").status_code == 202
        wait_ws(ws, lambda m: m["type"] == "finished" and m["status"] == "cancelled", t, 1.0)
    exports = c.app.state.settings.exports_dir  # type: ignore[attr-defined]
    assert not list(Path(exports).glob(f"{job['id']}*"))
