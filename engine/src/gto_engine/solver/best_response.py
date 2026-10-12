"""Explotabilidade por best response exata e valor do jogo (research R6)."""

from __future__ import annotations

import numpy as np

from gto_engine.game.tree import GameTree
from gto_engine.solver.kernels import root_values, total_pair_weight


def _value(tree: GameTree, strategy: np.ndarray, player: int, mode: int) -> float:
    T = tree.kernel
    cfv = root_values(T, np.ascontiguousarray(strategy, dtype=np.float32), player, mode)
    w = T.w0 if player == 0 else T.w1
    return float((w * cfv).sum() / total_pair_weight(T))


def game_value(tree: GameTree, strategy: np.ndarray) -> tuple[float, float]:
    """(valor OOP, valor IP) em fichas, na convenção u_OOP + u_IP = pote inicial."""
    return _value(tree, strategy, 0, 2), _value(tree, strategy, 1, 2)


def exploitability(tree: GameTree, strategy: np.ndarray) -> float:
    """Explotabilidade em % do pote inicial: 100 × (BR_OOP + BR_IP − P) / 2 / P."""
    br0 = _value(tree, strategy, 0, 1)
    br1 = _value(tree, strategy, 1, 1)
    return 100.0 * ((br0 + br1 - tree.pot) / 2.0) / tree.pot
