"""Enumeração exata de equity (research R2).

Os boards completos são pré-computados (`completions`) e processados em blocos; dentro de um
bloco, o trabalho é dividido em `SLICES` fatias fixas (paralelas com `prange`) cujos acumuladores
são somados em ordem fixa — o resultado independe do número de threads (Princípio VI).

Acumuladores por combo (sem o peso do próprio combo): [participação no pote, vitórias, empates,
total], todos ponderados pelos pesos dos adversários.
"""

import numpy as np
from numba import njit, prange

from gto_engine.evaluator.kernels import _eval_cards

SLICES = 32


@njit(cache=True, nogil=True)
def n_completions(m, k):
    if k == 0:
        return 1
    num = 1
    den = 1
    for i in range(k):
        num *= m - i
        den *= i + 1
    return num // den


@njit(cache=True, nogil=True)
def completions(avail, k):
    """Todas as combinações de k cartas de `avail` (ordem lexicográfica), como int64 (C, k)."""
    m = avail.shape[0]
    total = n_completions(m, k)
    out = np.empty((total, max(k, 1)), dtype=np.int64)
    if k == 0:
        out[0, 0] = -1
        return out
    idx = np.arange(k)
    for row in range(total):
        for j in range(k):
            out[row, j] = avail[idx[j]]
        # próxima combinação
        i = k - 1
        while i >= 0 and idx[i] == m - k + i:
            i -= 1
        if i < 0:
            break
        idx[i] += 1
        for j in range(i + 1, k):
            idx[j] = idx[j - 1] + 1
    return out


@njit(cache=True, nogil=True)
def _strengths(base, extra, k, hands, out):
    """Força de cada mão no board base + extra (−1 se a mão usa carta do board)."""
    cards = np.empty(7, dtype=np.int64)
    nb = base.shape[0]
    for j in range(nb):
        cards[2 + j] = base[j]
    for j in range(k):
        cards[2 + nb + j] = extra[j]
    for h in range(hands.shape[0]):
        a = hands[h, 0]
        b = hands[h, 1]
        blocked = False
        for j in range(5):
            if cards[2 + j] == a or cards[2 + j] == b:
                blocked = True
        if blocked:
            out[h] = -1
        else:
            cards[0] = a
            cards[1] = b
            out[h] = _eval_cards(cards)


@njit(cache=True, nogil=True)
def _sweep(s_t, s_o, hc_t, hc_o, w_o, same_t, acc):
    """Varredura ordenada com remoção de cartas: acumula [share, win, tie, total] por mão."""
    n_t = s_t.shape[0]
    n_o = s_o.shape[0]
    wo = np.empty(n_o)
    tot = 0.0
    cs = np.zeros(52)
    for j in range(n_o):
        wo[j] = w_o[j] if s_o[j] >= 0 else 0.0
        if wo[j] != 0.0:
            tot += wo[j]
            cs[hc_o[j, 0]] += wo[j]
            cs[hc_o[j, 1]] += wo[j]
    ord_t = np.argsort(s_t)
    ord_o = np.argsort(s_o)
    win = np.zeros(n_t)
    lose = np.zeros(n_t)
    cacc = np.zeros(52)
    acc_w = 0.0
    j = 0
    for ii in range(n_t):
        h = ord_t[ii]
        s = s_t[h]
        if s < 0:
            continue
        while j < n_o and s_o[ord_o[j]] < s:
            o = ord_o[j]
            if wo[o] != 0.0:
                acc_w += wo[o]
                cacc[hc_o[o, 0]] += wo[o]
                cacc[hc_o[o, 1]] += wo[o]
            j += 1
        win[h] = acc_w - cacc[hc_t[h, 0]] - cacc[hc_t[h, 1]]
    cacc[:] = 0.0
    acc_w = 0.0
    j = n_o - 1
    for ii in range(n_t - 1, -1, -1):
        h = ord_t[ii]
        s = s_t[h]
        if s < 0:
            continue
        while j >= 0 and s_o[ord_o[j]] > s:
            o = ord_o[j]
            if wo[o] != 0.0:
                acc_w += wo[o]
                cacc[hc_o[o, 0]] += wo[o]
                cacc[hc_o[o, 1]] += wo[o]
            j -= 1
        lose[h] = acc_w - cacc[hc_t[h, 0]] - cacc[hc_t[h, 1]]
    for h in range(n_t):
        if s_t[h] < 0:
            continue
        compat = tot - cs[hc_t[h, 0]] - cs[hc_t[h, 1]]
        if same_t[h] >= 0:
            compat += wo[same_t[h]]
        tie = compat - win[h] - lose[h]
        acc[h, 0] += win[h] + 0.5 * tie
        acc[h, 1] += win[h]
        acc[h, 2] += tie
        acc[h, 3] += compat


@njit(cache=True, nogil=True, parallel=True)
def hu_chunk(base, comps, lo, hi, c0, w0, c1, w1, same0, same1):
    """Heads-up: processa os boards comps[lo:hi]; devolve acumuladores (n0, 4) e (n1, 4)."""
    k = 5 - base.shape[0]
    n0 = c0.shape[0]
    n1 = c1.shape[0]
    part0 = np.zeros((SLICES, n0, 4))
    part1 = np.zeros((SLICES, n1, 4))
    span = hi - lo
    for sl in prange(SLICES):
        a = lo + span * sl // SLICES
        b = lo + span * (sl + 1) // SLICES
        s0 = np.empty(n0, dtype=np.int64)
        s1 = np.empty(n1, dtype=np.int64)
        for r in range(a, b):
            _strengths(base, comps[r], k, c0, s0)
            _strengths(base, comps[r], k, c1, s1)
            _sweep(s0, s1, c0, c1, w1, same0, part0[sl])
            _sweep(s1, s0, c1, c0, w0, same1, part1[sl])
    acc0 = np.zeros((n0, 4))
    acc1 = np.zeros((n1, 4))
    for sl in range(SLICES):
        acc0 += part0[sl]
        acc1 += part1[sl]
    return acc0, acc1


@njit(cache=True, nogil=True, parallel=True)
def mw_chunk(base, comps, cards, weights, counts, lo, hi):
    """Multiway: percorre as tuplas cujo combo do 1º participante está em [lo, hi).

    cards: (n, maxn, 2); weights: (n, maxn); counts: (n,). Devolve acc (n, maxn, 4).
    """
    n = counts.shape[0]
    maxn = cards.shape[1]
    k = 5 - base.shape[0]
    span = hi - lo
    part = np.zeros((SLICES, n, maxn, 4))
    for sl in prange(SLICES):
        a0 = lo + span * sl // SLICES
        b0 = lo + span * (sl + 1) // SLICES
        idx = np.zeros(n, dtype=np.int64)
        used = np.zeros(52, dtype=np.bool_)
        board = np.empty(7, dtype=np.int64)
        strength = np.empty(n, dtype=np.int64)
        for i0 in range(a0, b0):
            idx[:] = 0
            idx[0] = i0
            p = 1
            # odômetro sobre os participantes 1..n-1 (com verificação incremental de conflitos)
            while p >= 1:
                if p == n:
                    # tupla completa: verifica conflitos
                    used[:] = False
                    ok = True
                    wt = 1.0
                    for q in range(n):
                        x = cards[q, idx[q], 0]
                        y = cards[q, idx[q], 1]
                        if used[x] or used[y]:
                            ok = False
                            break
                        used[x] = True
                        used[y] = True
                        wt *= weights[q, idx[q]]
                    if ok:
                        for bi in range(base.shape[0]):
                            board[2 + bi] = base[bi]
                        for r in range(comps.shape[0]):
                            free = True
                            for j in range(k):
                                if used[comps[r, j]]:
                                    free = False
                            if not free:
                                continue
                            for j in range(k):
                                board[2 + base.shape[0] + j] = comps[r, j]
                            best = -1
                            for q in range(n):
                                board[0] = cards[q, idx[q], 0]
                                board[1] = cards[q, idx[q], 1]
                                strength[q] = _eval_cards(board)
                                if strength[q] > best:
                                    best = strength[q]
                            m = 0
                            for q in range(n):
                                if strength[q] == best:
                                    m += 1
                            for q in range(n):
                                wq = wt / weights[q, idx[q]]
                                acc = part[sl, q, idx[q]]
                                acc[3] += wq
                                if strength[q] == best:
                                    acc[0] += wq / m
                                    if m == 1:
                                        acc[1] += wq
                                    else:
                                        acc[2] += wq
                    p -= 1
                    idx[p] += 1
                    continue
                if idx[p] >= counts[p]:
                    idx[p] = 0
                    p -= 1
                    if p >= 1:
                        idx[p] += 1
                    continue
                p += 1
    acc = np.zeros((n, maxn, 4))
    for sl in range(SLICES):
        acc += part[sl]
    return acc
