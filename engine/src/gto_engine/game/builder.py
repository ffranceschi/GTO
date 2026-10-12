"""Builder da árvore No-Limit heads-up (FR-004 a FR-008)."""

from __future__ import annotations

import numpy as np

from gto_engine.cards import COMBO_CARDS, N_CARDS, blocked_mask, combo_str
from gto_engine.evaluator import evaluate_board
from gto_engine.game.betting import StreetState, initial_state, street_actions
from gto_engine.game.config import Street, TreeConfig
from gto_engine.game.tree import (
    NODE_DECISION,
    NODE_FOLD,
    NODE_SHOWDOWN,
    Action,
    GameTree,
    Players,
    Spot,
    TreeAssembler,
    _Node,
)


class UnsupportedStreetError(ValueError):
    """Street ainda não suportada pelo builder."""


def spot_players(spot: Spot) -> Players:
    blocked = blocked_mask(spot.board)
    hands, cards, weights = [], [], []
    for r in (spot.oop_range, spot.ip_range):
        idx = np.flatnonzero((r.weights > 0) & ~blocked).astype(np.int64)
        hands.append(idx)
        cards.append(np.ascontiguousarray(COMBO_CARDS[idx].astype(np.int64)))
        weights.append(r.weights[idx].astype(np.float64))
    return Players((hands[0], hands[1]), (cards[0], cards[1]), (weights[0], weights[1]), N_CARDS)


def build_tree(spot: Spot, config: TreeConfig) -> GameTree:
    if spot.street != Street.RIVER:
        raise UnsupportedStreetError("Nesta versão só spots de river podem ser resolvidos.")
    players = spot_players(spot)
    strengths_all = evaluate_board(spot.board)
    strengths = tuple(
        strengths_all[players.hands[p]].astype(np.int32).reshape(1, -1) for p in (0, 1)
    )
    asm = TreeAssembler()

    def build(s: StreetState) -> int:
        node = asm.add(_Node(NODE_DECISION, player=s.to_act, inv=s.inv, boards=(0,)))
        for a in street_actions(config, Street.RIVER, s):
            if a.outcome == "fold":
                child = asm.add(_Node(NODE_FOLD, player=s.to_act, inv=s.inv))
            elif a.outcome in ("street_end", "allin_called"):
                inv = s.inv
                if a.kind == "call":
                    inv = (max(s.inv), max(s.inv))
                child = asm.add(_Node(NODE_SHOWDOWN, inv=inv, board_id=0))
            else:
                assert a.next_state is not None
                child = build(a.next_state)
            asm.link(node, Action(a.kind, a.id, a.amount, a.pot_fraction, a.label), child)
        return node

    build(initial_state(spot.pot, spot.effective_stack))
    tree = GameTree(
        asm,
        players,
        spot.pot,
        [spot.board],
        (strengths[0], strengths[1]),
        Street.RIVER,
        hand_label=lambda p, i: combo_str(int(players.hands[p][i])),
    )
    tree.effective_stack = float(spot.effective_stack)
    return tree
