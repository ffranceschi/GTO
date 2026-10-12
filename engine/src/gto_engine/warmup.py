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

RATE_CASE = (("22+, A2+, K2+", "22+, A2+"), ("Ks", "7d", "2c"))


def measure_equity_rate() -> float:
    """Avaliações/s do kernel exato (research R4), medidas num HU range vs range no flop."""
    from gto_engine.equity.estimate import exact_evaluations
    from gto_engine.equity.request import EquityRequest
    from gto_engine.equity.run import run_equity

    ranges, board = RATE_CASE
    req = EquityRequest(
        tuple(parse_range(r) for r in ranges), tuple(parse_card(c) for c in board), method="exact"
    )
    run_equity(req)  # compila / aquece
    t0 = time.perf_counter()
    run_equity(req)
    return exact_evaluations(req) / max(time.perf_counter() - t0, 1e-6)


def warmup_equity() -> None:
    from gto_engine.equity.request import EquityRequest
    from gto_engine.equity.run import run_equity

    flop = tuple(parse_card(c) for c in ("Ks", "7d", "2c"))
    hu = (parse_range("AA, KK"), parse_range("QQ"))
    mw = (*hu, parse_range("JJ"))
    run_equity(EquityRequest(hu, flop, method="exact"))
    run_equity(EquityRequest(mw, flop, method="exact"))
    run_equity(EquityRequest(hu, flop, method="monte_carlo", target_margin_pp=1.0))


def warmup() -> float:
    t0 = time.perf_counter()
    warmup_equity()
    solve(kuhn_tree(), SolveParams(max_iterations=2, target_exploitability_pct=0.0))
    board = tuple(parse_card(c) for c in ("Ks", "7d", "2c", "Jh", "3s"))
    spot = Spot(parse_range("AA, KK, AK"), parse_range("QQ, AQ"), board, 10.0, 20.0)
    tree = build_tree(spot, TreeConfig.uniform(bets=(0.5,), raises=(1.0,), max_raises=1))
    solve(tree, SolveParams(max_iterations=2, target_exploitability_pct=0.0))
    return time.perf_counter() - t0


if __name__ == "__main__":
    print(f"Warm-up concluído em {warmup():.1f} s")
    print(f"Taxa do kernel exato de equity: {measure_equity_rate() / 1e6:.1f} M avaliações/s")
