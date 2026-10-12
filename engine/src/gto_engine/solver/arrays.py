"""Arrays planos do solver e a forma da árvore consumida pelos kernels Numba."""

from __future__ import annotations

from collections import namedtuple
from dataclasses import dataclass
from typing import TYPE_CHECKING

import numpy as np

if TYPE_CHECKING:
    from gto_engine.game.tree import GameTree

KTree = namedtuple(
    "KTree",
    [
        "node_type",
        "node_player",
        "child_start",
        "child_count",
        "children",
        "inv",
        "dec_index",
        "dec_offset",
        "chance_factor",
        "chance_card",
        "board_id",
        "pot",
        "k",
        "n_cards",
        "w0",
        "w1",
        "hc0",
        "hc1",
        "same0",
        "same1",
        "str0",
        "str1",
        "ord0",
        "ord1",
        "dec_node",
        "dec_combo_offset",
        "dec_board_start",
        "dec_boards",
    ],
)


def _same_index(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    """Para cada mão de `a`, índice da mão idêntica (mesmas cartas) em `b`, ou -1."""
    pos = {tuple(sorted(int(x) for x in row)): j for j, row in enumerate(b)}
    return np.array([pos.get(tuple(sorted(int(x) for x in row)), -1) for row in a], dtype=np.int64)


def kernel_tree(tree: GameTree) -> KTree:
    p = tree.players
    hc0 = np.ascontiguousarray(p.hand_cards[0], dtype=np.int64)
    hc1 = np.ascontiguousarray(p.hand_cards[1], dtype=np.int64)
    return KTree(
        tree.node_type,
        tree.node_player,
        tree.child_start,
        tree.child_count,
        tree.children_arr,
        tree.inv,
        tree.dec_index,
        tree.dec_offset,
        tree.chance_factor,
        tree.chance_card,
        tree.board_id,
        float(tree.pot),
        int(hc0.shape[1]),
        int(p.n_cards),
        np.ascontiguousarray(p.weights[0], dtype=np.float64),
        np.ascontiguousarray(p.weights[1], dtype=np.float64),
        hc0,
        hc1,
        _same_index(hc0, hc1),
        _same_index(hc1, hc0),
        np.ascontiguousarray(tree.strengths[0], dtype=np.int64),
        np.ascontiguousarray(tree.strengths[1], dtype=np.int64),
        np.ascontiguousarray(tree.orders[0]),
        np.ascontiguousarray(tree.orders[1]),
        tree.dec_node,
        tree.dec_combo_offset,
        tree.dec_board_start,
        tree.dec_boards,
    )


@dataclass
class SolverArrays:
    regrets: np.ndarray  # float32, layout [nó de decisão][ação][mão]
    strategy_sum: np.ndarray  # float32, mesmo layout

    @property
    def nbytes(self) -> int:
        return int(self.regrets.nbytes + self.strategy_sum.nbytes)


def allocate_solver_arrays(tree: GameTree) -> SolverArrays:
    return SolverArrays(
        np.zeros(tree.strategy_size, dtype=np.float32),
        np.zeros(tree.strategy_size, dtype=np.float32),
    )
