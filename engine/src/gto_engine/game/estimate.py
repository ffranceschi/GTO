"""Estimativa de nós, memória e disco sem construir a árvore (research R3).

Contagem analítica: enumera as linhas de aposta de cada street (poucas dezenas), agrupa as
continuações por (street, pote, stack) com memoização e multiplica pelos ramos de chance
canônicos (isomorfismo de naipes, R5).
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from functools import cache
from math import comb

import numpy as np

from gto_engine.cards import N_CARDS, blocked_mask
from gto_engine.game.betting import StreetState, initial_state, r2, street_actions
from gto_engine.game.config import Street, TreeConfig
from gto_engine.game.isomorphism import chance_orbits, stabilizer, symmetry_group
from gto_engine.game.tree import Spot

OVERHEAD = 1.2
_NEXT = {Street.FLOP: Street.TURN, Street.TURN: Street.RIVER}


@dataclass(frozen=True)
class TreeEstimate:
    decision_nodes: int
    chance_nodes: int
    terminal_nodes: int
    estimated_bytes: int
    estimated_solution_bytes: int
    isomorphism_factor: float


@dataclass(frozen=True)
class _Count:
    dec: int = 0
    chance: int = 0
    term: int = 0
    acts: tuple[int, int] = (0, 0)
    decs: tuple[int, int] = (0, 0)

    def __add__(self, o: _Count) -> _Count:
        return _Count(
            self.dec + o.dec,
            self.chance + o.chance,
            self.term + o.term,
            (self.acts[0] + o.acts[0], self.acts[1] + o.acts[1]),
            (self.decs[0] + o.decs[0], self.decs[1] + o.decs[1]),
        )

    def times(self, k: int) -> _Count:
        return _Count(
            self.dec * k,
            self.chance * k,
            self.term * k,
            (self.acts[0] * k, self.acts[1] * k),
            (self.decs[0] * k, self.decs[1] * k),
        )


def _branching(board: tuple[int, ...], group: list[int]) -> tuple[int, ...]:
    """Ramos canônicos do próximo nó de chance e, para o turn, os do river sob cada carta.

    Retorna (nº de cartas canônicas do próximo street, *nº de ramos do river por carta canônica).
    """
    orbits = chance_orbits(board, group)
    if len(board) == 4:
        return (len(orbits),)
    rivers = tuple(len(chance_orbits((*board, x), stabilizer(group, x))) for x, _ in orbits)
    return (len(orbits), *rivers)


def _count(
    config: TreeConfig, street: Street, pot: float, stack: float, branches: tuple[int, ...]
) -> _Count:
    turn_branches = branches[0] if branches else 0
    river_by_turn = Counter(branches[1:]) if street == Street.FLOP else Counter()
    river_branches_turn_spot = branches[0] if street == Street.TURN and branches else 0

    @cache
    def street_subtree(
        st: Street, pot_c: int, stack_c: int, oop_can_bet: bool, river_br: int
    ) -> _Count:
        cont: Counter[tuple[int, int, bool, bool]] = Counter()

        def walk(s: StreetState) -> _Count:
            acts = street_actions(config, st, s)
            p = s.to_act
            c = _Count(
                dec=1,
                acts=(len(acts), 0) if p == 0 else (0, len(acts)),
                decs=(1, 0) if p == 0 else (0, 1),
            )
            for a in acts:
                if a.outcome == "fold":
                    c = c + _Count(term=1)
                elif a.outcome in ("street_end", "allin_called"):
                    sinv = max(s.inv) if a.kind == "call" else s.inv[0]
                    new_pot = r2(s.pot + 2 * sinv)
                    new_stack = r2(s.stack - sinv)
                    allin = a.outcome == "allin_called" or new_stack <= 0
                    can_bet = config.allow_donk or not (a.kind == "call" and s.to_act == 0)
                    cont[(round(new_pot * 100), round(new_stack * 100), allin, can_bet)] += 1
                else:
                    assert a.next_state is not None
                    c = c + walk(a.next_state)
            return c

        total = walk(initial_state(pot_c / 100, stack_c / 100, oop_can_bet))
        for (np_c, ns_c, allin, can_bet), mult in cont.items():
            total = total + continuation(st, np_c, ns_c, allin, can_bet, river_br).times(mult)
        return total

    @cache
    def continuation(
        st: Street, pot_c: int, stack_c: int, allin: bool, can_bet: bool, river_br: int
    ) -> _Count:
        if st == Street.RIVER:
            return _Count(term=1)
        if st == Street.TURN:  # → river (river_br ramos canônicos)
            sub = (
                _Count(term=1)
                if allin
                else street_subtree(Street.RIVER, pot_c, stack_c, can_bet, 0)
            )
            return _Count(chance=1) + sub.times(river_br)
        # flop → turn: soma sobre as cartas canônicas do turn (cada uma com seus ramos de river)
        total = _Count(chance=1)
        for rb, n in river_by_turn.items():
            if allin:
                sub = _Count(chance=1) + _Count(term=1).times(rb)
            else:
                sub = street_subtree(Street.TURN, pot_c, stack_c, can_bet, rb)
            total = total + sub.times(n)
        return total

    if stack <= 0:
        return _Count(chance=1, term=1)
    rb = river_branches_turn_spot if street == Street.TURN else 0
    del turn_branches
    return street_subtree(street, round(pot * 100), round(stack * 100), True, rb)


def estimate_tree(spot: Spot, config: TreeConfig) -> TreeEstimate:
    blocked = blocked_mask(spot.board)
    combos = [
        int(np.count_nonzero((r.weights > 0) & ~blocked)) for r in (spot.oop_range, spot.ip_range)
    ]
    group = symmetry_group(spot.board, [spot.oop_range.weights, spot.ip_range.weights])
    branches = _branching(tuple(spot.board), group) if len(spot.board) < 5 else ()
    c = _count(config, spot.street, spot.pot, spot.effective_stack, branches)
    train = 8 * (c.acts[0] * combos[0] + c.acts[1] * combos[1])
    boards = comb(N_CARDS - len(spot.board), 5 - len(spot.board))
    tables = boards * (combos[0] + combos[1]) * 12  # força int32 + ordem int64
    nodes = c.dec + c.chance + c.term
    tree_bytes = (
        nodes * 73  # tipo, jogador, filhos, investimentos, board, chance, street, subárvore…
        + (nodes - 1) * 25  # arestas: tipo, valor, fração, id e rótulo
        + tables  # forças (int32) e ordens (int64) por board
        + 24 * (combos[0] + combos[1]) * 8  # permutações de mãos do isomorfismo
    )
    solution = (
        4 * (c.acts[0] * combos[0] + c.acts[1] * combos[1])
        + 8 * (c.decs[0] * combos[0] + c.decs[1] * combos[1])
        + tree_bytes  # árvore gravada junto (T101)
    )
    raw = {3: (N_CARDS - 3) * (N_CARDS - 4), 4: N_CARDS - 4, 5: 1}[len(spot.board)]
    canonical = {3: sum(branches[1:]), 4: branches[0] if branches else 1, 5: 1}[len(spot.board)]
    return TreeEstimate(
        decision_nodes=c.dec,
        chance_nodes=c.chance,
        terminal_nodes=c.term,
        estimated_bytes=int(OVERHEAD * train + tables),
        estimated_solution_bytes=int(solution),
        isomorphism_factor=raw / canonical if canonical else 1.0,
    )
