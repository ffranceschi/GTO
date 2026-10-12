"""T016 — WebSocket para job_kind = "equity" (specs/001-…/contracts/websocket.md)."""

from __future__ import annotations

from typing import Any

from fastapi.testclient import TestClient

FULL = "22+, A2+, K2+, Q2+, J2+, T2+, 92+, 82+, 72+, 62+, 52+, 42+, 32"


def collect(client: TestClient, payload: dict[str, Any]) -> list[dict[str, Any]]:
    job = client.post("/api/v1/equity-jobs", json=payload).json()
    msgs: list[dict[str, Any]] = []
    with client.websocket_connect(f"/api/v1/jobs/{job['id']}/events") as ws:
        while True:
            m = ws.receive_json()
            msgs.append(m)
            if m["type"] == "finished":
                return msgs


def test_progresso_monte_carlo(client: TestClient) -> None:
    parts = [{"notation": FULL}] * 3 + [{"notation": "QQ+"}]
    msgs = collect(
        client,
        {
            "participants": parts,
            "method": "monte_carlo",
            "target_margin_pp": 0.05,
            "time_limit_s": 0.2,
        },
    )
    assert msgs[0]["type"] == "snapshot" and all(m["job_kind"] == "equity" for m in msgs)
    prog = [m for m in msgs if m["type"] == "progress"]
    assert (
        prog and {"samples", "equities", "margins", "target_margin", "elapsed_s"} <= prog[-1].keys()
    )
    assert msgs[-1]["status"] == "completed" and msgs[-1]["stop_reason"] == "time_limit"


def test_progresso_exato(client: TestClient) -> None:
    msgs = collect(client, {"participants": [{"notation": "AA"}, {"notation": "KK"}]})
    prog = [m for m in msgs if m["type"] == "progress"]
    assert prog and "fraction" in prog[-1] and prog[-1]["method"] == "exact"
    assert msgs[-1]["stop_reason"] == "exact"
