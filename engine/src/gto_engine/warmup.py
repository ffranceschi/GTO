"""Compila os kernels Numba (python -m gto_engine.warmup) — research R8."""

from __future__ import annotations

import time

from gto_engine.cards import parse_card
from gto_engine.game.builder import build_tree
from gto_engine.game.config import TreeConfig
from gto_engine.game.tree import Spot
from gto_engine.ranges import parse_range
from gto_engine.solver.dcfr import solve
from gto_engine.solver.params import SolveParams
from gto_engine.toy_games.kuhn import kuhn_tree


def warmup() -> float:
    t0 = time.perf_counter()
    solve(kuhn_tree(), SolveParams(max_iterations=2, target_exploitability_pct=0.0))
    board = tuple(parse_card(c) for c in ("Ks", "7d", "2c", "Jh", "3s"))
    spot = Spot(parse_range("AA, KK, AK"), parse_range("QQ, AQ"), board, 10.0, 20.0)
    tree = build_tree(spot, TreeConfig.uniform(bets=(0.5,), raises=(1.0,), max_raises=1))
    solve(tree, SolveParams(max_iterations=2, target_exploitability_pct=0.0))
    return time.perf_counter() - t0


if __name__ == "__main__":
    print(f"Warm-up concluído em {warmup():.1f} s")
