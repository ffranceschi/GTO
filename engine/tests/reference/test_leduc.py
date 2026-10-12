"""T016 — Leduc (REFERENCES.md: Lanctot et al. 2017, LP na forma sequencial; regras em R7)."""

from gto_engine.solver.best_response import exploitability, game_value
from gto_engine.solver.dcfr import solve
from gto_engine.solver.params import SolveParams
from gto_engine.toy_games.leduc import leduc_tree

LEDUC_VALUE = -0.085606424078


def test_leduc_valor_e_explotabilidade() -> None:
    tree = leduc_tree()
    res = solve(tree, SolveParams(max_iterations=4000, target_exploitability_pct=0.0))
    v1, _ = game_value(tree, res.strategy)
    valor = v1 - tree.pot / 2
    expl = exploitability(tree, res.strategy)
    mbb = expl / 100 * tree.pot * 1000  # mbb/mão (1 ficha = 1 "bb")
    print(f"Leduc: valor={valor:.6f}, explotabilidade={expl:.4f}% do pote ({mbb:.2f} mbb/mão)")
    assert abs(valor - LEDUC_VALUE) <= 0.005
    assert expl < 0.1
