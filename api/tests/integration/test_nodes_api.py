"""T069 — navegação via API (turn/flop liberados)."""

from __future__ import annotations

import time

from fastapi.testclient import TestClient

from tests.helpers import small_request, wait_solve


def test_turn_navegacao(client: TestClient) -> None:
    req = small_request(
        board=["Ks", "7d", "2c", "Jh"], params={"target_exploitability_pct": 1, "time_limit_s": 30}
    )
    req["tree"]["bet_sizes"] = {s: {"oop": [0.75], "ip": [0.75]} for s in ("flop", "turn", "river")}
    req["tree"]["max_raises_per_street"] = 1
    r = client.post("/api/v1/solves", json=req)
    assert r.status_code == 202, r.text
    s = wait_solve(client, r.json()["id"], ("completed",), timeout=60)
    base = f"/api/v1/solves/{s['id']}/nodes"
    ch = client.get(base, params={"path": "x/b75/c"}).json()
    assert ch["kind"] == "chance" and "Kh" in ch["next_cards"] and "Ks" not in ch["next_cards"]
    t0 = time.perf_counter()
    v = client.get(base, params={"path": "x/b75/c/Kh"})
    assert time.perf_counter() - t0 <= 0.2
    body = v.json()
    assert body["kind"] == "decision" and body["player"] == "oop"
    assert {"pot", "stacks", "ranges"} <= body.keys()
    term = client.get(base, params={"path": "b75/f"}).json()
    assert term["kind"] == "terminal" and term["terminal"]["kind"] == "fold"
    bad = client.get(base, params={"path": "x/b75/c/Ks"})
    assert bad.status_code == 422 and bad.json()["code"] == "caminho_invalido"


def test_flop_aceito(client: TestClient) -> None:
    req = small_request(
        board=["Ks", "7d", "2c"], params={"target_exploitability_pct": 5, "time_limit_s": 30}
    )
    req["tree"]["bet_sizes"] = {s: {"oop": [0.66], "ip": [0.66]} for s in ("flop", "turn", "river")}
    req["tree"]["max_raises_per_street"] = 0
    r = client.post("/api/v1/solves", json=req)
    assert r.status_code == 202, r.text
