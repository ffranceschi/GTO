"""T013 — cálculo leve na requisição: validação + estimativa ≤ 200 ms no pior caso (Princípio V)."""

from __future__ import annotations

import time

from gto_engine.equity.estimate import estimate_equity
from gto_engine.equity.request import EquityRequest
from gto_engine.ranges import parse_range

FULL = "22+, A2+, K2+, Q2+, J2+, T2+, 92+, 82+, 72+, 62+, 52+, 42+, 32"


def _pior_caso() -> str:
    r = EquityRequest(tuple(parse_range(FULL) for _ in range(6)), ())
    return estimate_equity(r).method


def test_estimativa_200ms(benchmark) -> None:  # type: ignore[no-untyped-def]
    _pior_caso()
    t0 = time.perf_counter()
    assert _pior_caso() == "monte_carlo"
    assert time.perf_counter() - t0 <= 0.2
    benchmark(_pior_caso)
