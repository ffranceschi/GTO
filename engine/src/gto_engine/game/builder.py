"""Builder da árvore No-Limit heads-up multi-street (FR-004 a FR-008; research R5)."""

from __future__ import annotations

from itertools import combinations

import numpy as np

from gto_engine.cards import COMBO_CARDS, N_CARDS, blocked_mask, card_str, combo_str
from gto_engine.evaluator import evaluate_board
from gto_engine.game.betting import StreetState, initial_state, r2, street_actions
from gto_engine.game.config import Street, TreeConfig
from gto_engine.game.isomorphism import (
    COMBO_PERM,
    SUIT_PERMS,
    chance_orbits,
    stabilizer,
    symmetry_group,
)
from gto_engine.game.tree import (
    NODE_CHANCE,
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

NEXT = {Street.FLOP: Street.TURN, Street.TURN: Street.RIVER}
HAND_SIZE = 2


class UnsupportedStreetError(ValueError):
    """Street não suportada pelo builder."""


def spot_players(spot: Spot) -> Players:
    blocked = blocked_mask(spot.board)
    hands, cards, weights = [], [], []
    for r in (spot.oop_range, spot.ip_range):
        idx = np.flatnonzero((r.weights > 0) & ~blocked).astype(np.int64)
        hands.append(idx)
        cards.append(np.ascontiguousarray(COMBO_CARDS[idx].astype(np.int64)))
        weights.append(r.weights[idx].astype(np.float64))
    return Players((hands[0], hands[1]), (cards[0], cards[1]), (weights[0], weights[1]), N_CARDS)


def _hand_perms(hands: np.ndarray, group: list[int]) -> np.ndarray:
    pos = -np.ones(1326, dtype=np.int64)
    pos[hands] = np.arange(len(hands))
    out = np.full((len(SUIT_PERMS), len(hands)), -1, dtype=np.int64)
    for k in group:
        out[k] = pos[COMBO_PERM[k][hands]]
    return out


def build_tree(spot: Spot, config: TreeConfig) -> GameTree:
    players = spot_players(spot)
    group = symmetry_group(spot.board, [spot.oop_range.weights, spot.ip_range.weights])
    rest = [c for c in range(N_CARDS) if c not in spot.board]
    finals = [
        tuple(sorted((*spot.board, *extra))) for extra in combinations(rest, 5 - len(spot.board))
    ]
    board_id = {frozenset(b): i for i, b in enumerate(finals)}
    strengths = tuple(
        np.ascontiguousarray(
            np.vstack([evaluate_board(b)[players.hands[p]] for b in finals]).astype(np.int32)
        )
        for p in (0, 1)
    )
    superset_cache: dict[frozenset[int], tuple[int, ...]] = {}

    def supersets(board: tuple[int, ...]) -> tuple[int, ...]:
        key = frozenset(board)
        if key not in superset_cache:
            superset_cache[key] = tuple(i for i, b in enumerate(finals) if key <= set(b))
        return superset_cache[key]

    asm = TreeAssembler()

    def factor(board: tuple[int, ...]) -> float:
        return 1.0 / (N_CARDS - len(board) - 2 * HAND_SIZE)

    def runout(st: Street, board: tuple[int, ...], inv: tuple[float, float], grp: list[int]) -> int:
        """Nó de chance que revela a carta de `st` sem decisões (all-in ou stack zero)."""
        node = asm.add(_Node(NODE_CHANCE, inv=inv, chance_factor=factor(board), street=st.value))
        for x, members in chance_orbits(board, grp):
            nb = (*board, x)
            if st == Street.RIVER:
                child = asm.add(
                    _Node(NODE_SHOWDOWN, inv=inv, board_id=board_id[frozenset(nb)], street=st.value)
                )
            else:
                child = runout(NEXT[st], nb, inv, stabilizer(grp, x))
            asm.nodes[child].chance_card = x
            asm.nodes[child].iso = members
            asm.link(node, Action("card", card_str(x), 0.0, None, card_str(x)), child)
        return node

    def deal(
        st: Street,
        board: tuple[int, ...],
        pot: float,
        stack: float,
        inv: tuple[float, float],
        grp: list[int],
        oop_can_bet: bool,
    ) -> int:
        node = asm.add(_Node(NODE_CHANCE, inv=inv, chance_factor=factor(board), street=st.value))
        for x, members in chance_orbits(board, grp):
            child = street(st, (*board, x), pot, stack, inv, stabilizer(grp, x), oop_can_bet)
            asm.nodes[child].chance_card = x
            asm.nodes[child].iso = members
            asm.link(node, Action("card", card_str(x), 0.0, None, card_str(x)), child)
        return node

    def street(
        st: Street,
        board: tuple[int, ...],
        pot: float,
        stack: float,
        inv_total: tuple[float, float],
        grp: list[int],
        oop_can_bet: bool,
    ) -> int:
        if stack <= 0:  # sem fichas: sem decisões, só o runout até o showdown
            if len(board) == 5:
                return asm.add(
                    _Node(
                        NODE_SHOWDOWN,
                        inv=inv_total,
                        board_id=board_id[frozenset(board)],
                        street=st.value,
                    )
                )
            return runout(Street.TURN if len(board) == 3 else Street.RIVER, board, inv_total, grp)

        def build(s: StreetState) -> int:
            inv = (r2(inv_total[0] + s.inv[0]), r2(inv_total[1] + s.inv[1]))
            node = asm.add(
                _Node(
                    NODE_DECISION,
                    player=s.to_act,
                    inv=inv,
                    boards=supersets(board),
                    street=st.value,
                )
            )
            for a in street_actions(config, st, s):
                if a.outcome == "fold":
                    child = asm.add(_Node(NODE_FOLD, player=s.to_act, inv=inv, street=st.value))
                elif a.outcome in ("street_end", "allin_called"):
                    sinv = (max(s.inv), max(s.inv)) if a.kind == "call" else s.inv
                    new_inv = (r2(inv_total[0] + sinv[0]), r2(inv_total[1] + sinv[1]))
                    new_pot = r2(s.pot + sinv[0] + sinv[1])
                    new_stack = r2(s.stack - sinv[0])
                    if st == Street.RIVER:
                        child = asm.add(
                            _Node(
                                NODE_SHOWDOWN,
                                inv=new_inv,
                                board_id=board_id[frozenset(board)],
                                street=st.value,
                            )
                        )
                    elif a.outcome == "allin_called" or new_stack <= 0:
                        child = runout(NEXT[st], board, new_inv, grp)
                    else:
                        aggressor_ip = a.kind == "call" and s.to_act == 0  # OOP pagou aposta do IP
                        can_bet = config.allow_donk or not aggressor_ip
                        child = deal(NEXT[st], board, new_pot, new_stack, new_inv, grp, can_bet)
                else:
                    assert a.next_state is not None
                    child = build(a.next_state)
                asm.link(node, Action(a.kind, a.id, a.amount, a.pot_fraction, a.label), child)
            return node

        return build(initial_state(pot, stack, oop_can_bet))

    street(spot.street, tuple(spot.board), spot.pot, spot.effective_stack, (0.0, 0.0), group, True)
    perms = (_hand_perms(players.hands[0], group), _hand_perms(players.hands[1], group))
    tree = GameTree(
        asm,
        players,
        spot.pot,
        finals,
        (strengths[0], strengths[1]),
        spot.street,
        hand_label=lambda p, i: combo_str(int(players.hands[p][i])),
        hand_perms=perms,
    )
    tree.effective_stack = float(spot.effective_stack)
    tree.initial_board = tuple(spot.board)
    tree.group = group
    return tree
