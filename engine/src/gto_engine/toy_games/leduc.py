"""Leduc Hold'em com as regras de Lanctot et al. (2017) — ver tests/reference/REFERENCES.md.

Baralho J, J, Q, Q, K, K (cartas 0..5; rank = carta // 2); ante 1; 1ª rodada aposta fixa 2;
carta pública; 2ª rodada aposta fixa 4; no máximo 2 apostas (bet + raise) por rodada.
"""

from __future__ import annotations

import numpy as np

from gto_engine.game.tree import (
    NODE_CHANCE,
    NODE_DECISION,
    NODE_FOLD,
    NODE_SHOWDOWN,
    Action,
    GameTree,
    Players,
    TreeAssembler,
    _Node,
)

NAMES = ("Js", "Jh", "Qs", "Qh", "Ks", "Kh")
MAX_BETS = 2


def leduc_tree() -> GameTree:
    asm = TreeAssembler()

    def betting(
        round_: int, inv: tuple[float, float], to_act: int, bets: int, checked: bool, board: int
    ) -> int:
        size = 2.0 if round_ == 0 else 4.0
        boards = tuple(range(6)) if round_ == 0 else (board,)
        node = asm.add(_Node(NODE_DECISION, to_act, inv, boards=boards))
        o = 1 - to_act
        facing = inv[o] > inv[to_act]

        def end_round(new_inv: tuple[float, float]) -> int:
            if round_ == 0:
                return deal(new_inv)
            return asm.add(_Node(NODE_SHOWDOWN, inv=new_inv, board_id=board))

        if facing:
            asm.link(
                node, Action("fold", "f", 0.0, None, "Fold"), asm.add(_Node(NODE_FOLD, to_act, inv))
            )
            called = (max(inv), max(inv))
            asm.link(
                node, Action("call", "c", inv[o] - inv[to_act], None, "Call"), end_round(called)
            )
            if bets < MAX_BETS:
                new = list(inv)
                new[to_act] = inv[o] + size
                asm.link(
                    node,
                    Action("raise", "r", size, None, f"Raise ({size:g})"),
                    betting(round_, (new[0], new[1]), o, bets + 1, checked, board),
                )
        else:
            if checked:
                asm.link(node, Action("check", "x", 0.0, None, "Check"), end_round(inv))
            else:
                asm.link(
                    node,
                    Action("check", "x", 0.0, None, "Check"),
                    betting(round_, inv, o, bets, True, board),
                )
            new = list(inv)
            new[to_act] = inv[to_act] + size
            asm.link(
                node,
                Action("bet", "b", size, None, f"Bet ({size:g})"),
                betting(round_, (new[0], new[1]), o, bets + 1, checked, board),
            )
        return node

    def deal(inv: tuple[float, float]) -> int:
        node = asm.add(_Node(NODE_CHANCE, inv=inv, chance_factor=1.0 / 4.0))
        for card in range(6):
            child = betting(1, inv, 0, 0, False, card)
            asm.nodes[child].chance_card = card
            asm.link(node, Action("card", NAMES[card], 0.0, None, NAMES[card]), child)
        return node

    betting(0, (0.0, 0.0), 0, 0, False, -1)

    hands = np.arange(6, dtype=np.int64)
    cards = hands.reshape(6, 1)
    w = np.ones(6)
    players = Players((hands, hands.copy()), (cards, cards.copy()), (w, w.copy()), 6)
    strength = np.empty((6, 6), dtype=np.int32)
    for b in range(6):
        for h in range(6):
            if h == b:
                strength[b, h] = -1
            elif h // 2 == b // 2:
                strength[b, h] = 100 + h // 2
            else:
                strength[b, h] = h // 2
    boards: list[tuple[int, ...]] = [(b,) for b in range(6)]
    return GameTree(
        asm, players, 2.0, boards, (strength, strength.copy()), hand_label=lambda p, i: NAMES[i]
    )
