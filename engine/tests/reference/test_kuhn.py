"""T015 — Kuhn (REFERENCES.md: Kuhn 1950, valor −1/18 ± 0,001; família de equilíbrio ± 0,01)."""

import pytest

from gto_engine.solver.best_response import exploitability, game_value
from gto_engine.solver.dcfr import solve
from gto_engine.solver.params import SolveParams
from gto_engine.solver.strategy import node_strategy
from gto_engine.toy_games.kuhn import kuhn_tree

J, Q, K = 0, 1, 2


@pytest.mark.parametrize(
    ("algorithm", "iters"), [("dcfr", 3000), ("cfr_plus", 3000), ("linear_cfr", 5000)]
)
def test_kuhn_equilibrio(algorithm: str, iters: int) -> None:
    tree = kuhn_tree()
    res = solve(
        tree, SolveParams(algorithm=algorithm, max_iterations=iters, target_exploitability_pct=0.0)
    )  # type: ignore[arg-type]
    v1, v2 = game_value(tree, res.strategy)
    assert v1 + v2 == pytest.approx(tree.pot)
    assert v1 - tree.pot / 2 == pytest.approx(-1 / 18, abs=0.001)
    assert exploitability(tree, res.strategy) < 0.1  # % do pote

    raiz = node_strategy(tree, res.strategy, tree.root)  # (ações, mãos); ações: x, b
    bet = [tree.actions(tree.root)[i].id for i in range(2)].index("b")
    alpha = raiz[bet, J]
    assert 0.0 - 0.01 <= alpha <= 1 / 3 + 0.01
    assert raiz[bet, K] == pytest.approx(3 * alpha, abs=0.01)
    assert raiz[bet, Q] == pytest.approx(0.0, abs=0.01)
