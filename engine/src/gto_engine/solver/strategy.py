"""Acesso à estratégia plana (layout [nó de decisão][ação][mão])."""

from __future__ import annotations

import numpy as np

from gto_engine.game.tree import GameTree


def uniform_strategy(tree: GameTree) -> np.ndarray:
    s = np.empty(tree.strategy_size, dtype=np.float32)
    for d, node in enumerate(tree.dec_node):
        a = tree.child_count[node]
        s[tree.dec_offset[d] : tree.dec_offset[d + 1]] = 1.0 / a
    return s


def node_strategy(tree: GameTree, strategy: np.ndarray, node: int) -> np.ndarray:
    """Estratégia do nó como matriz (ações, mãos do jogador da vez)."""
    sl = tree.strategy_slice(node)
    a = int(tree.child_count[node])
    return np.asarray(strategy[sl], dtype=np.float64).reshape(a, -1)


def set_node_strategy(tree: GameTree, strategy: np.ndarray, node: int, probs: np.ndarray) -> None:
    sl = tree.strategy_slice(node)
    a = int(tree.child_count[node])
    m = np.asarray(probs, dtype=np.float64)
    if m.shape[0] != a:
        raise ValueError("A matriz de probabilidades precisa ter uma linha por ação.")
    strategy[sl] = m.reshape(-1)
