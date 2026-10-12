"""T014 — estimate_tree (research R3): contagem analítica, precisão no river e sem isomorfismo."""

import pytest

from gto_engine.cards import parse_card
from gto_engine.game.builder import build_tree
from gto_engine.game.config import TreeConfig, default_tree_config
from gto_engine.game.estimate import estimate_tree
from gto_engine.game.tree import Spot
from gto_engine.ranges import parse_range
from gto_engine.solver.arrays import allocate_solver_arrays

OOP_REF = (
    "22-TT, A2s-AQs, K5s+, Q7s+, J7s+, T7s+, 96s+, 85s+, 74s+, 63s+, 53s+, 43s, "
    "A8o-AQo, K9o+, Q9o+, J9o+, T9o, 98o"
)
IP_REF = (
    "22+, A2s+, K2s+, Q5s+, J7s+, T7s+, 96s+, 85s+, 74s+, 63s+, 53s+, 43s, "
    "A5o+, K9o+, Q9o+, J9o+, T9o, 98o"
)
RIVER = tuple(parse_card(c) for c in ("Ks", "7d", "2c", "Jh", "3s"))


@pytest.mark.parametrize("ranges", [("100", "100"), (OOP_REF, IP_REF)])
@pytest.mark.parametrize(
    "cfg",
    [
        TreeConfig.uniform(bets=(0.5, 1.0), raises=(1.0,), max_raises=3),
        default_tree_config(),
        TreeConfig.uniform(bets=(0.33,), raises=(0.5,), max_raises=1),
    ],
)
@pytest.mark.parametrize(("pot", "stack"), [(10.0, 50.0), (6.0, 97.0)])
def test_river_contagem_e_bytes(
    ranges: tuple[str, str], cfg: TreeConfig, pot: float, stack: float
) -> None:
    oop = (
        parse_range("22+, A2+, K2+, Q2+, J2+, T2+, 92+, 82+, 72+, 62+, 52+, 42+, 32")
        if ranges[0] == "100"
        else parse_range(ranges[0])
    )
    ip = oop if ranges[1] == "100" else parse_range(ranges[1])
    spot = Spot(oop, ip, RIVER, pot, stack)
    est = estimate_tree(spot, cfg)
    tree = build_tree(spot, cfg)
    assert est.decision_nodes == tree.n_decision_nodes
    alocado = allocate_solver_arrays(tree).nbytes
    tabelas = sum(a.nbytes for a in (*tree.strengths, *tree.orders))
    assert est.estimated_bytes == pytest.approx(alocado * 1.2 + tabelas, rel=0.15)
    assert est.isomorphism_factor == 1.0
    combos = [tree.n_hands(p) for p in ("oop", "ip")]
    sol = sum(a * combos[pl] * 4 + combos[pl] * 8 for a, pl in tree.decision_shapes())
    arrays, _ = tree.to_arrays()
    tree_bytes = sum(a.nbytes for a in arrays.values()) - sum(
        arrays[k].nbytes
        for k in ("hands0", "hands1", "hand_cards0", "hand_cards1", "weights0", "weights1")
    )
    assert est.estimated_solution_bytes == pytest.approx(sol + tree_bytes, rel=0.15)
