"""Kernels Numba do avaliador de mãos (lookup tables; sem laços Python em hot loops)."""

import numpy as np
from numba import njit

from gto_engine.cards import COMBO_CARDS
from gto_engine.evaluator.tables import load_tables

FLUSH, NOFLUSH, OFFSETS, DP = load_tables()
_COMBO_CARDS = np.ascontiguousarray(COMBO_CARDS.astype(np.int64))


@njit(cache=True, nogil=True)
def _eval_cards(cards):
    counts = np.zeros(13, dtype=np.int64)
    suit_count = np.zeros(4, dtype=np.int64)
    suit_mask = np.zeros(4, dtype=np.int64)
    n = cards.shape[0]
    for i in range(n):
        c = cards[i]
        r = c // 4
        s = c % 4
        counts[r] += 1
        suit_count[s] += 1
        suit_mask[s] |= 1 << r
    best = -1
    for s in range(4):
        if suit_count[s] >= 5:
            best = FLUSH[suit_mask[s]]
    # perfect hash do multiconjunto de ranks
    idx = 0
    left = n
    for r in range(13):
        rest = 12 - r
        for v in range(counts[r]):
            idx += DP[rest, left - v]
        left -= counts[r]
    nf = NOFLUSH[OFFSETS[n] + idx]
    return nf if nf > best else best


@njit(cache=True, nogil=True)
def eval5(a, b, c, d, e):
    return _eval_cards(np.array([a, b, c, d, e], dtype=np.int64))


@njit(cache=True, nogil=True)
def eval7(a, b, c, d, e, f, g):
    return _eval_cards(np.array([a, b, c, d, e, f, g], dtype=np.int64))


@njit(cache=True, nogil=True)
def board_strengths(board):
    """Força de cada um dos 1326 combos num board de 5 cartas; −1 se o combo usa carta do board."""
    out = np.empty(1326, dtype=np.int32)
    cards = np.empty(7, dtype=np.int64)
    for k in range(5):
        cards[k + 2] = board[k]
    for i in range(1326):
        a = _COMBO_CARDS[i, 0]
        b = _COMBO_CARDS[i, 1]
        blocked = False
        for k in range(5):
            if board[k] == a or board[k] == b:
                blocked = True
        if blocked:
            out[i] = -1
        else:
            cards[0] = a
            cards[1] = b
            out[i] = _eval_cards(cards)
    return out
