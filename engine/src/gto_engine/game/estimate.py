"""Estimativa de nós, memória e disco sem construir a árvore (research R3).

Contagem analítica: enumera as linhas de aposta de cada street (poucas dezenas), agrupa as
continuações por (street, pote, stack) com memoização e multiplica pelos ramos de chance.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import cache
from math import comb

import numpy as np

from gto_engine.cards import N_CARDS, blocked_mask
from gto_engine.game.betting import StreetState, initial_state, r2, street_actions
from gto_engine.game.config import Street, TreeConfig
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
    acts: tuple[int, int] = (0, 0)  # Σ ações por jogador
    decs: tuple[int, int] = (0, 0)  # nós de decisão por jogador

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


def _count(config: TreeConfig, street: Street, pot: float, stack: float, n_board: int) -> _Count:
    @cache
    def street_subtree(st: Street, pot_c: int, stack_c: int, nb: int) -> _Count:
        total = _Count()
        cont: dict[tuple[int, int, bool], int] = {}

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
                    inv = max(s.inv) if a.kind == "call" else s.inv[0]
                    new_pot = r2(s.pot + 2 * inv)
                    new_stack = r2(s.stack - inv)
                    key = (
                        round(new_pot * 100),
                        round(new_stack * 100),
                        a.outcome == "allin_called" or new_stack <= 0,
                    )
                    cont[key] = cont.get(key, 0) + 1
                else:
                    assert a.next_state is not None
                    c = c + walk(a.next_state)
            return c

        total = walk(initial_state(pot_c / 100, stack_c / 100, True))
        for (np_c, ns_c, allin), mult in cont.items():
            total = total + _continuation(st, np_c, ns_c, nb, allin).times(mult)
        return total

    @cache
    def _continuation(st: Street, pot_c: int, stack_c: int, nb: int, allin: bool) -> _Count:
        if st == Street.RIVER:
            return _Count(term=1)
        branches = N_CARDS - nb
        nxt = _NEXT[st]
        if allin:
            # runout sem decisões: nós de chance até o river, depois showdown
            sub = _continuation(nxt, pot_c, stack_c, nb + 1, True)
        else:
            sub = street_subtree(nxt, pot_c, stack_c, nb + 1)
        return _Count(chance=1) + sub.times(branches)

    return street_subtree(street, round(pot * 100), round(stack * 100), n_board)


def estimate_tree(spot: Spot, config: TreeConfig) -> TreeEstimate:
    blocked = blocked_mask(spot.board)
    combos = [
        int(np.count_nonzero((r.weights > 0) & ~blocked)) for r in (spot.oop_range, spot.ip_range)
    ]
    c = _count(config, spot.street, spot.pot, spot.effective_stack, len(spot.board))
    train = 8 * (c.acts[0] * combos[0] + c.acts[1] * combos[1])
    boards = comb(N_CARDS - len(spot.board), 5 - len(spot.board))
    tables = boards * (combos[0] + combos[1]) * 8
    solution = 4 * (c.acts[0] * combos[0] + c.acts[1] * combos[1]) + 8 * (
        c.decs[0] * combos[0] + c.decs[1] * combos[1]
    )
    return TreeEstimate(
        decision_nodes=c.dec,
        chance_nodes=c.chance,
        terminal_nodes=c.term,
        estimated_bytes=int(OVERHEAD * train + tables),
        estimated_solution_bytes=int(solution),
        isomorphism_factor=1.0,
    )
