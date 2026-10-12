"""T052 — fila de solves (FR-027)."""

from __future__ import annotations

from fastapi.testclient import TestClient

from tests.helpers import small_request, wait_solve

LONG = {"target_exploitability_pct": 1e-9, "time_limit_s": 60}


def test_fila_posicao_inicio_automatico_e_cancelamento(client: TestClient) -> None:
    a = client.post("/api/v1/solves", json=small_request(params=LONG)).json()
    wait_solve(client, a["id"], ("running",))
    b = client.post("/api/v1/solves", json=small_request(pot=11)).json()
    c = client.post("/api/v1/solves", json=small_request(pot=12)).json()
    assert b["status"] == "queued" and b["queue_position"] == 1
    assert client.get(f"/api/v1/solves/{c['id']}").json()["queue_position"] == 2

    with client.websocket_connect(f"/api/v1/jobs/{c['id']}/events") as ws:
        snap = ws.receive_json()
        assert snap["type"] == "snapshot" and snap["queue_position"] == 2
        assert client.delete(f"/api/v1/solves/{b['id']}").status_code == 202  # cancela da fila
        while True:
            m = ws.receive_json()
            if m["type"] == "status" and m.get("queue_position") == 1:
                break
    assert client.get(f"/api/v1/solves/{b['id']}").json()["status"] == "cancelled"

    # pausado mantém a vez
    assert client.post(f"/api/v1/solves/{a['id']}/pause").status_code == 202
    wait_solve(client, a["id"], ("paused",), timeout=2)
    assert client.get(f"/api/v1/solves/{c['id']}").json()["status"] == "queued"
    assert client.post(f"/api/v1/solves/{a['id']}/stop").status_code == 202
    wait_solve(client, a["id"], ("stopped",), timeout=5)
    wait_solve(client, c["id"], ("running", "completed"), timeout=5)
