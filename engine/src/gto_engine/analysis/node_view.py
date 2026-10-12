"""Visão de um nó: só leitura de fatias e agregação vetorizada (≤ 200 ms — research R15)."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

import numpy as np

from gto_engine.cards import N_COMBOS, combo_str
from gto_engine.game.tree import (
    NODE_CHANCE,
    NODE_DECISION,
    NODE_FOLD,
    PLAYERS,
    GameTree,
    InvalidPathError,
)
from gto_engine.io.solution_dir import Solution
from gto_engine.ranges.notation import HAND_COMBOS, hand_name

# índice de célula (0..168) de cada combo
_CELL = np.empty(N_COMBOS, dtype=np.int64)
_CELL_NAMES: list[str] = []
for _i, (_h, _idx) in enumerate(
    sorted(HAND_COMBOS.items(), key=lambda kv: (-kv[0][0], -kv[0][1], kv[0][2]))
):
    _CELL[_idx] = _i
    _CELL_NAMES.append(hand_name(_h))


@dataclass(frozen=True)
class ActionView:
    id: str
    kind: str
    label: str
    amount_bb: float
    pot_fraction: float | None
    aggregate_frequency: float
    combos: float


@dataclass(frozen=True)
class HandView:
    hand: str
    combos: float
    frequencies: dict[str, float]
    ev_bb: float
    equity: float


@dataclass(frozen=True)
class ComboView:
    combo: str
    reach_weight: float
    frequencies: dict[str, float]
    ev_bb: float
    equity: float


@dataclass(frozen=True)
class RangeAtNode:
    player: str
    combos: float
    weights: list[float]


@dataclass(frozen=True)
class NodeView:
    path: list[str]
    breadcrumb: list[str]
    kind: str  # decision | chance | terminal
    player: str | None
    pot: float
    stacks: dict[str, float]
    actions: list[ActionView]
    hands: list[HandView]
    combos: list[ComboView]
    ranges: list[RangeAtNode]
    next_cards: list[str]
    terminal: str | None  # fold | showdown


def _strategy(tree: GameTree, solution: Solution, node: int) -> np.ndarray:
    sl = tree.strategy_slice(node)
    return np.asarray(solution.strategy[sl], dtype=np.float64).reshape(
        int(tree.child_count[node]), -1
    )


def node_view(tree: GameTree, solution: Solution, path: Sequence[str]) -> NodeView:
    reach = [tree.players.weights[0].copy(), tree.players.weights[1].copy()]
    node = tree.root
    crumbs: list[str] = []
    for step in path:
        kind = int(tree.node_type[node])
        if kind not in (NODE_DECISION, NODE_CHANCE):
            raise InvalidPathError(f"O caminho continua depois de um nó terminal ('{step}').")
        acts = tree.actions(node)
        ids = [a.id for a in acts]
        if step not in ids:
            raise InvalidPathError(f"A ação '{step}' não existe neste nó.")
        a = ids.index(step)
        if kind == NODE_DECISION:
            p = tree.player_index(node)
            reach[p] = reach[p] * _strategy(tree, solution, node)[a]
        else:
            x = int(tree.chance_card[tree.children(node)[a]])
            for p in (0, 1):
                reach[p] = np.where(np.any(tree.players.hand_cards[p] == x, axis=1), 0.0, reach[p])
        crumbs.append(acts[a].label)
        node = tree.children(node)[a]

    inv = tree.investments(node)
    stack0 = _initial_stack(tree)
    ranges = []
    for p in (0, 1):
        w = np.zeros(N_COMBOS)
        w[tree.players.hands[p]] = reach[p]
        ranges.append(RangeAtNode(PLAYERS[p], float(reach[p].sum()), w.tolist()))
    kind = int(tree.node_type[node])
    pot = round(tree.pot_at(node), 2)
    stacks = {"oop": round(stack0 - inv[0], 2), "ip": round(stack0 - inv[1], 2)}

    def make(
        kind: str,
        player: str | None = None,
        actions: list[ActionView] | None = None,
        hands: list[HandView] | None = None,
        combos: list[ComboView] | None = None,
        next_cards: list[str] | None = None,
        terminal: str | None = None,
    ) -> NodeView:
        return NodeView(
            list(path),
            crumbs,
            kind,
            player,
            pot,
            stacks,
            actions or [],
            hands or [],
            combos or [],
            ranges,
            next_cards or [],
            terminal,
        )

    if kind == NODE_CHANCE:
        return make("chance", next_cards=[a.id for a in tree.actions(node)])
    if kind != NODE_DECISION:
        return make("terminal", terminal="fold" if kind == NODE_FOLD else "showdown")

    p = tree.player_index(node)
    acts = tree.actions(node)
    sig = _strategy(tree, solution, node)
    r = reach[p]
    tot = float(r.sum())
    csl = tree.combo_slice(node)
    ev = np.asarray(solution.ev[csl], dtype=np.float64)
    eq = np.asarray(solution.equity[csl], dtype=np.float64)
    weighted = sig * r  # (A, n)
    actions = [
        ActionView(
            a.id,
            a.kind,
            a.label,
            a.amount,
            a.pot_fraction,
            float(weighted[i].sum() / tot) if tot > 0 else 0.0,
            float(weighted[i].sum()),
        )
        for i, a in enumerate(acts)
    ]
    hands_idx = tree.players.hands[p]
    cells = _CELL[hands_idx]
    cw = np.bincount(cells, weights=r, minlength=169)
    cfreq = np.vstack(
        [np.bincount(cells, weights=weighted[i], minlength=169) for i in range(len(acts))]
    )
    cev = np.bincount(cells, weights=r * ev, minlength=169)
    ceq = np.bincount(cells, weights=r * eq, minlength=169)
    hands: list[HandView] = []
    for c in np.unique(cells):
        w = cw[c]
        if w > 0:
            freqs = {a.id: float(cfreq[i, c] / w) for i, a in enumerate(acts)}
            hands.append(
                HandView(_CELL_NAMES[c], float(w), freqs, float(cev[c] / w), float(ceq[c] / w))
            )
        else:
            hands.append(HandView(_CELL_NAMES[c], 0.0, {}, 0.0, 0.0))
    combos = [
        ComboView(
            combo_str(int(h)),
            float(r[i]),
            {a.id: float(sig[j, i]) for j, a in enumerate(acts)} if r[i] > 0 else {},
            float(ev[i]),
            float(eq[i]),
        )
        for i, h in enumerate(hands_idx)
    ]
    return make("decision", PLAYERS[p], actions, hands, combos)


def _initial_stack(tree: GameTree) -> float:
    return float(tree.effective_stack)
