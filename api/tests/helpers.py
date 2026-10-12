from __future__ import annotations

import time
from typing import Any

from fastapi.testclient import TestClient


def sizes(v: list[float]) -> dict[str, dict[str, list[float]]]:
    return {s: {"oop": v, "ip": v} for s in ("flop", "turn", "river")}


def small_request(**over: Any) -> dict[str, Any]:
    req: dict[str, Any] = {
        "spot": {
            "oop_range": {"notation": "AA, KK, 77, AK, KQs, QJs, T9s"},
            "ip_range": {"notation": "QQ+, AK, KJ, 76s"},
            "board": ["Ks", "7d", "2c", "Jh", "3s"],
            "pot": 10,
            "effective_stack": 30,
        },
        "tree": {
            "bet_sizes": sizes([0.5, 1.0]),
            "raise_sizes": sizes([1.0]),
            "max_raises_per_street": 2,
            "allin_threshold": 0.67,
        },
        "params": {"target_exploitability_pct": 0.5, "time_limit_s": 30},
    }
    for k, v in over.items():
        if k in ("board", "pot", "effective_stack", "oop_range", "ip_range"):
            req["spot"][k] = v
        else:
            req[k] = v
    return req


def wait_solve(
    client: TestClient, solve_id: str, statuses: tuple[str, ...], timeout: float = 30
) -> dict[str, Any]:
    t0 = time.monotonic()
    while True:
        body: dict[str, Any] = client.get(f"/api/v1/solves/{solve_id}").json()
        if body["status"] in statuses:
            return body
        assert time.monotonic() - t0 < timeout, body
        time.sleep(0.05)
