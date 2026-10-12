"""T014 — orçamentos de equity (research R12, SC-001/002/003/011) no hardware de referência."""

from __future__ import annotations

import time

import pytest

from gto_engine.cards import parse_card
from gto_engine.equity.request import EquityRequest
from gto_engine.equity.run import run_equity
from gto_engine.ranges import parse_range

FULL = "22+, A2+, K2+, Q2+, J2+, T2+, 92+, 82+, 72+, 62+, 52+, 42+, 32"


def req(ranges: list[str], board: str = "", **kw: object) -> EquityRequest:
    return EquityRequest(
        tuple(parse_range(r) for r in ranges), tuple(parse_card(c) for c in board.split()), **kw
    )  # type: ignore[arg-type]


def timed(r: EquityRequest):  # type: ignore[no-untyped-def]
    t0 = time.perf_counter()
    out = run_equity(r)
    return out, time.perf_counter() - t0


@pytest.mark.benchmark_ref
def test_sc001_sc002_sc003() -> None:
    run_equity(req(["AhKh", "QsQd"], "Jh Th 2c"))  # aquece
    r, dt = timed(req(["AA", "KK"]))
    print(f"SC-001 AA vs KK: {r.participants[0].equity:.4%} ({r.method}) em {dt:.2f} s")
    assert r.method == "exact"
    r, dt = timed(req([FULL, FULL], "Ks 7d 2c"))
    print(f"SC-002 100% vs 100% no flop: {r.method} em {dt:.2f} s")
    assert r.method == "exact" and dt < 2.0
    for b in ("", "Ks 7d 2c", "Ks 7d 2c Jh", "Ks 7d 2c Jh 3s"):
        r, dt = timed(req(["AhQh", "TsTd"], b))
        print(f"SC-003 mão vs mão ({len(b.split())} cartas): {dt:.2f} s")
        assert r.method == "exact" and dt < 1.0


@pytest.mark.benchmark_ref
def test_sc011_monte_carlo() -> None:
    r, dt = timed(
        req([FULL, FULL], "", method="monte_carlo", target_margin_pp=0.05, time_limit_s=3)
    )
    rate = r.samples / dt
    print(f"SC-011 MC heads-up: {rate / 1e6:.1f} M amostras/s")
    assert rate >= 5e6
    r, dt = timed(req([FULL] * 6, "", target_margin_pp=0.1, time_limit_s=60))
    print(f"SC-011 MC 6-way até ±0,1 pp: {dt:.1f} s ({r.samples / 1e6:.1f} M amostras)")
    assert r.stop_reason == "target_reached" and dt < 60


def test_bench_mc_relativo(benchmark) -> None:  # type: ignore[no-untyped-def]
    r = req(
        ["QQ+, AK", "JJ-88", "A2s+"], "Ks 7d 2c", method="monte_carlo", target_margin_pp=0.5, seed=3
    )
    run_equity(r)
    benchmark.pedantic(lambda: run_equity(r), rounds=3, iterations=1)
