"""Finalização do solve: EV e equity por combo em cada nó de decisão (R3 item 3, R15).

A travessia é fatiada: os níveis de cima da árvore são percorridos em Python (operações
vetorizadas) até subárvores com no máximo `CHUNK_NODES` nós, cada uma resolvida por um kernel
Numba. Entre os kernels o controle é consultado (cancelamento ≤ 1 bloco) e o progresso publicado.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import numpy as np

from gto_engine.game.tree import NODE_CHANCE, NODE_DECISION, GameTree
from gto_engine.solver.kernels import finalize_traverse, record_decision

CHUNK_NODES = 2_000


class SolveCancelled(Exception):
    """O solve foi cancelado (nenhuma solução deve ser gravada)."""


def _cancelled(control: Any) -> bool:
    fn = getattr(control, "is_cancelled", None)
    return bool(fn()) if fn is not None else False


def finalize(
    tree: GameTree,
    strategy: np.ndarray,
    control: Any,
    on_fraction: Callable[[float], None],
) -> tuple[np.ndarray, np.ndarray]:
    T = tree.kernel
    ev = np.zeros(tree.combo_size, dtype=np.float32)
    eq = np.zeros(tree.combo_size, dtype=np.float32)
    total = 2 * int(tree.subtree_size[tree.root])
    done = 0
    on_fraction(0.0)

    def unit(node: int, trav: int, rt: np.ndarray, ro: np.ndarray) -> np.ndarray:
        nonlocal done
        if _cancelled(control):
            raise SolveCancelled()
        kind = int(tree.node_type[node])
        if tree.subtree_size[node] <= CHUNK_NODES or kind not in (NODE_DECISION, NODE_CHANCE):
            v: np.ndarray = finalize_traverse(T, node, trav, rt, ro, strategy, ev, eq)
            done += int(tree.subtree_size[node])
            on_fraction(min(1.0, done / total))
            return v
        kids = tree.children(node)
        done += 1
        if kind == NODE_CHANCE:
            hc_t = tree.players.hand_cards[trav]
            hc_o = tree.players.hand_cards[1 - trav]
            f = float(tree.chance_factor[node])
            v = np.zeros(rt.shape[0])
            for ch in kids:
                x = int(tree.chance_card[ch])
                ok = ~np.any(hc_t == x, axis=1)
                vc = unit(
                    ch, trav, np.where(ok, rt, 0.0), np.where(np.any(hc_o == x, axis=1), 0.0, ro)
                )
                v += np.where(ok, f * vc, 0.0)
            return v
        p = tree.player_index(node)
        sl = tree.strategy_slice(node)
        sig = np.asarray(strategy[sl], dtype=np.float64).reshape(len(kids), -1)
        tot = sig.sum(axis=0)
        sig = np.where(tot > 0, sig / np.where(tot > 0, tot, 1), 1.0 / len(kids))
        v = np.zeros(rt.shape[0])
        if p == trav:
            for a, ch in enumerate(kids):
                v += sig[a] * unit(ch, trav, rt * sig[a], ro)
            record_decision(T, node, trav, v, ro, ev, eq)
        else:
            for a, ch in enumerate(kids):
                v += unit(ch, trav, rt, ro * sig[a])
        return v

    for trav in (0, 1):
        w_t = T.w0 if trav == 0 else T.w1
        w_o = T.w1 if trav == 0 else T.w0
        unit(tree.root, trav, w_t.copy(), w_o.copy())
    on_fraction(1.0)
    return ev, eq
