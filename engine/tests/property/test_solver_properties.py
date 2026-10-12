"""T096 — propriedades do solver em spots de river pequenos e aleatórios (hypothesis)."""

from __future__ import annotations

import numpy as np
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from gto_engine.cards import RANKS
from gto_engine.game.builder import build_tree
from gto_engine.game.config import TreeConfig
from gto_engine.game.tree import InvalidSpotError, Spot
from gto_engine.ranges import parse_range
from gto_engine.solver.dcfr import solve
from gto_engine.solver.params import SolveParams
from gto_engine.solver.strategy import node_strategy

PAIRS = [r * 2 for r in RANKS]
BROADWAY = ["AK", "AQ", "AJ", "KQ", "KJ", "QJ", "JT", "T9", "98", "87", "76", "65"]
hands = st.lists(st.sampled_from(PAIRS + BROADWAY), min_size=2, max_size=6, unique=True)
boards = st.lists(st.integers(0, 51), min_size=5, max_size=5, unique=True)


@settings(max_examples=12, deadline=None, suppress_health_check=[HealthCheck.too_slow])
@given(hands, hands, boards, st.sampled_from([(0.5,), (0.75,), (0.5, 1.0)]), st.floats(5, 100))
def test_frequencias_somam_1_e_explotabilidade_cai(
    oop: list[str], ip: list[str], board: list[int], bets: tuple[float, ...], stack: float
) -> None:
    try:
        spot = Spot(
            parse_range(", ".join(oop)), parse_range(", ".join(ip)), tuple(board), 10, stack
        )
    except InvalidSpotError:
        return  # ranges totalmente bloqueados pelo board
    tree = build_tree(spot, TreeConfig.uniform(bets=bets, raises=(1.0,), max_raises=1))
    r = solve(tree, SolveParams(max_iterations=200, target_exploitability_pct=0.0), finalize=False)
    for node in tree.dec_node:
        sig = node_strategy(tree, r.strategy, int(node))
        np.testing.assert_allclose(sig.sum(axis=0), 1.0, atol=1e-4)
    history = r.history[:, 2]
    assert np.all(history >= -1e-9)
    assert history[-1] <= history[0] + 1e-6
