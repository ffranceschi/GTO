"""T046 — gate do river de referência (research R9): < 1% do pote com iterações fixas."""

import numpy as np

from gto_engine.game.builder import build_tree
from gto_engine.solver.dcfr import solve
from gto_engine.solver.params import SolveParams
from gto_engine.solver.strategy import node_strategy
from tests.conftest import load_spot

ITERATIONS = 300


def test_river_referencia_abaixo_de_1pct() -> None:
    spot, cfg = load_spot("river_reference.json")
    tree = build_tree(spot, cfg)
    r = solve(
        tree, SolveParams(max_iterations=ITERATIONS, target_exploitability_pct=0.0), finalize=False
    )
    print(f"river de referência: {r.exploitability_pct:.3f}% do pote em {r.iterations} iterações")
    assert r.exploitability_pct < 1.0
    for node in tree.dec_node:
        sig = node_strategy(tree, r.strategy, int(node))
        np.testing.assert_allclose(sig.sum(axis=0), 1.0, atol=1e-4)  # SC-005
