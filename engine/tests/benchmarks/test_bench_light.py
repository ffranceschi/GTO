"""T014 — benchmark de cálculo leve (Princípio V, research R3 item 6): ≤ 200 ms no pior caso."""

import time

from gto_engine.cards import parse_card
from gto_engine.game.config import default_tree_config
from gto_engine.game.estimate import estimate_tree
from gto_engine.game.hashing import input_hash
from gto_engine.game.tree import Spot
from gto_engine.ranges import parse_range
from gto_engine.solver.params import SolveParams

FULL = "22+, A2+, K2+, Q2+, J2+, T2+, 92+, 82+, 72+, 62+, 52+, 42+, 32"
FLOP = tuple(parse_card(c) for c in ("Ks", "7d", "2c"))


def _pior_caso() -> int:
    spot = Spot(parse_range(FULL), parse_range(FULL), FLOP, 6.0, 97.0)
    cfg = default_tree_config()
    est = estimate_tree(spot, cfg)
    input_hash(spot, cfg, SolveParams())
    return est.decision_nodes


def test_calculo_leve_200ms(benchmark) -> None:  # type: ignore[no-untyped-def]
    _pior_caso()  # aquece
    t0 = time.perf_counter()
    n = _pior_caso()
    dt = time.perf_counter() - t0
    assert n > 1_000_000  # flop padrão tem ≈ 1,76 milhão de nós de decisão
    assert dt <= 0.200, f"{dt * 1000:.0f} ms > 200 ms"
    benchmark(_pior_caso)
