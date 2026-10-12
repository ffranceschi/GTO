"""Kuhn Poker (Kuhn, 1950): baralho J, Q, K; ante 1; aposta 1; uma rodada.

Valor do jogo para o 1º jogador: −1/18 (fonte e tolerância em tests/reference/REFERENCES.md).
"""

from __future__ import annotations

import numpy as np

from gto_engine.game.tree import (
    NODE_DECISION,
    NODE_FOLD,
    NODE_SHOWDOWN,
    Action,
    GameTree,
    Players,
    TreeAssembler,
    _Node,
)

NAMES = ("J", "Q", "K")


def kuhn_tree() -> GameTree:
    asm = TreeAssembler()
    x, b, c, f = (
        Action("check", "x", 0.0, None, "Check"),
        Action("bet", "b", 1.0, None, "Bet (1)"),
        Action("call", "c", 1.0, None, "Call (1)"),
        Action("fold", "f", 0.0, None, "Fold"),
    )
    root = asm.add(_Node(NODE_DECISION, 0, (0, 0), boards=(0,)))
    n_x = asm.add(_Node(NODE_DECISION, 1, (0, 0), boards=(0,)))
    asm.link(root, x, n_x)
    asm.link(n_x, x, asm.add(_Node(NODE_SHOWDOWN, inv=(0, 0), board_id=0)))
    n_xb = asm.add(_Node(NODE_DECISION, 0, (0, 1), boards=(0,)))
    asm.link(n_x, b, n_xb)
    asm.link(n_xb, f, asm.add(_Node(NODE_FOLD, 0, (0, 1))))
    asm.link(n_xb, c, asm.add(_Node(NODE_SHOWDOWN, inv=(1, 1), board_id=0)))
    n_b = asm.add(_Node(NODE_DECISION, 1, (1, 0), boards=(0,)))
    asm.link(root, b, n_b)
    asm.link(n_b, f, asm.add(_Node(NODE_FOLD, 1, (1, 0))))
    asm.link(n_b, c, asm.add(_Node(NODE_SHOWDOWN, inv=(1, 1), board_id=0)))

    hands = np.arange(3, dtype=np.int64)
    cards = hands.reshape(3, 1)
    w = np.ones(3)
    players = Players((hands, hands.copy()), (cards, cards.copy()), (w, w.copy()), 3)
    strength = np.arange(3, dtype=np.int32).reshape(1, 3)
    return GameTree(
        asm, players, 2.0, [()], (strength, strength.copy()), hand_label=lambda p, i: NAMES[i]
    )
