"""T068 — orçamentos de turn e flop (research R3/R9), no hardware de referência."""

from __future__ import annotations

import resource
import time

import pytest

from gto_engine.analysis.node_view import node_view
from gto_engine.game.builder import build_tree
from gto_engine.io.solution_dir import solution_from_result
from gto_engine.solver.dcfr import solve
from gto_engine.solver.params import SolveParams
from tests.conftest import load_spot

GIB = 1024**3


def _rss_bytes() -> int:
    r = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return int(r if r > 10**9 else r * 1024)  # macOS em bytes, Linux em KiB


@pytest.mark.benchmark_ref
def test_turn_referencia_60s() -> None:
    spot, cfg = load_spot("turn_reference.json")
    tree = build_tree(spot, cfg)
    t0 = time.perf_counter()
    r = solve(tree, SolveParams(target_exploitability_pct=1.0, time_limit_s=60))
    dt = time.perf_counter() - t0
    print(f"turn: {r.exploitability_pct:.3f}% em {dt:.1f} s ({r.iterations} iterações)")
    assert r.stop_reason == "target_reached" and dt < 60


@pytest.mark.benchmark_ref
def test_flop_referencia_10min_4gib() -> None:
    spot, cfg = load_spot("flop_reference.json")
    tb = time.perf_counter()
    tree = build_tree(spot, cfg)
    print(
        f"flop: árvore em {time.perf_counter() - tb:.1f} s ({tree.n_decision_nodes} nós de decisão)"
    )
    t0 = time.perf_counter()
    params = SolveParams(target_exploitability_pct=1.0, time_limit_s=600)
    r = solve(tree, params)
    dt = time.perf_counter() - t0
    peak = _rss_bytes()
    print(
        f"flop: {r.exploitability_pct:.3f}% em {dt:.0f} s ({r.iterations} it.), "
        f"pico RSS {peak / GIB:.2f} GiB"
    )
    assert r.stop_reason == "target_reached" and dt < 600 and peak <= 4 * GIB
    sol = solution_from_result(tree, spot, cfg, params, r)
    for path in ([], ["x"], ["x", "x"], ["x", "x", "As"], ["x", "x", "As", "x", "x", "2h"]):
        n0 = time.perf_counter()
        node_view(tree, sol, path)
        assert time.perf_counter() - n0 <= 0.2, path
