"""T050 — benchmarks do river (SC-001 e consulta de nó ≤ 200 ms)."""

from __future__ import annotations

import time

import pytest

from gto_engine.analysis.node_view import node_view
from gto_engine.game.builder import build_tree
from gto_engine.io.solution_dir import solution_from_result
from gto_engine.solver.dcfr import solve
from gto_engine.solver.params import SolveParams
from tests.conftest import load_spot


@pytest.mark.benchmark_ref
def test_sc001_river_abaixo_de_1pct_em_30s() -> None:
    spot, cfg = load_spot("river_reference.json")
    tree = build_tree(spot, cfg)
    solve(tree, SolveParams(max_iterations=2, target_exploitability_pct=0.0))  # aquece o JIT
    t0 = time.perf_counter()
    r = solve(tree, SolveParams(target_exploitability_pct=1.0, time_limit_s=30))
    dt = time.perf_counter() - t0
    print(f"SC-001: {r.exploitability_pct:.3f}% em {dt:.2f} s ({r.iterations} iterações)")
    assert r.stop_reason == "target_reached" and dt < 30


def test_node_view_raiz_200ms() -> None:
    spot, cfg = load_spot("river_reference.json")
    tree = build_tree(spot, cfg)
    params = SolveParams(max_iterations=20, target_exploitability_pct=0.0)
    sol = solution_from_result(tree, spot, cfg, params, solve(tree, params))
    node_view(tree, sol, [])
    t0 = time.perf_counter()
    node_view(tree, sol, ["x", "b100"])
    assert time.perf_counter() - t0 <= 0.200


def test_bench_100_iteracoes_river(benchmark) -> None:  # type: ignore[no-untyped-def]
    spot, cfg = load_spot("river_reference.json")
    tree = build_tree(spot, cfg)
    p = SolveParams(max_iterations=100, target_exploitability_pct=0.0)
    solve(tree, SolveParams(max_iterations=1, target_exploitability_pct=0.0), finalize=False)
    benchmark.pedantic(lambda: solve(tree, p, finalize=False), rounds=3, iterations=1)
