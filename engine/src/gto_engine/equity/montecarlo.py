"""Monte Carlo de equity (research R3).

Cada bloco tem `SLICES` fatias fixas; a fatia f do bloco b usa o PRNG semeado com
splitmix64(semente, b, f), e os acumuladores são somados em ordem fixa — o resultado independe
do número de threads. Combos sorteados por peso (soma acumulada + busca binária); tuplas com
cartas repetidas são rejeitadas, o que reproduz a distribuição conjunta correta.
"""

import numpy as np
from numba import njit, prange

from gto_engine.equity.rng import derive_state, random
from gto_engine.evaluator.kernels import _eval_cards

SLICES = 64


def samples_per_slice(block: int) -> int:
    """Calendário fixo (não depende do tempo): 256, 512, … até 16384 amostras por fatia."""
    return 256 << min(block, 6)


@njit(cache=True, nogil=True)
def _pick(cum, count, u):
    """Índice i com cum[i-1] <= u < cum[i] (cum é a soma acumulada dos pesos)."""
    lo = 0
    hi = count - 1
    target = u * cum[count - 1]
    while lo < hi:
        mid = (lo + hi) // 2
        if cum[mid] <= target:
            lo = mid + 1
        else:
            hi = mid
    return lo


@njit(cache=True, nogil=True, parallel=True)
def mc_block(base, cards, cum, counts, seed, block, per_slice):
    """Roda SLICES × per_slice amostras aceitas.

    Devolve (part (n, 5): [n, Σshare, Σshare², Σwin, Σtie], combo (n, maxn, 5): idem por combo,
    tentativas).
    """
    n = counts.shape[0]
    maxn = cards.shape[1]
    nb = base.shape[0]
    k = 5 - nb
    p_part = np.zeros((SLICES, n, 5))
    p_combo = np.zeros((SLICES, n, maxn, 5))
    p_tries = np.zeros(SLICES)
    for sl in prange(SLICES):
        st = derive_state(seed, block, sl)
        used = np.zeros(52, dtype=np.bool_)
        board = np.empty(7, dtype=np.int64)
        chosen = np.empty(n, dtype=np.int64)
        strength = np.empty(n, dtype=np.int64)
        extra = np.empty(5, dtype=np.int64)
        accepted = 0
        tries = 0
        while accepted < per_slice:
            tries += 1
            if tries > per_slice * 200:
                break  # taxa de rejeição alta demais: o chamador transforma em erro
            used[:] = False
            for j in range(nb):
                used[base[j]] = True
            ok = True
            for q in range(n):
                i = _pick(cum[q], counts[q], random(st))
                x = cards[q, i, 0]
                y = cards[q, i, 1]
                if used[x] or used[y]:
                    ok = False
                    break
                used[x] = True
                used[y] = True
                chosen[q] = i
            if not ok:
                continue
            for j in range(k):
                while True:
                    c = int(random(st) * 52)
                    if not used[c]:
                        break
                used[c] = True
                extra[j] = c
            for j in range(nb):
                board[2 + j] = base[j]
            for j in range(k):
                board[2 + nb + j] = extra[j]
            best = -1
            for q in range(n):
                board[0] = cards[q, chosen[q], 0]
                board[1] = cards[q, chosen[q], 1]
                strength[q] = _eval_cards(board)
                if strength[q] > best:
                    best = strength[q]
            m = 0
            for q in range(n):
                if strength[q] == best:
                    m += 1
            for q in range(n):
                share = 1.0 / m if strength[q] == best else 0.0
                w = 1.0 if (strength[q] == best and m == 1) else 0.0
                t = 1.0 if (strength[q] == best and m > 1) else 0.0
                a = p_part[sl, q]
                a[0] += 1.0
                a[1] += share
                a[2] += share * share
                a[3] += w
                a[4] += t
                b = p_combo[sl, q, chosen[q]]
                b[0] += 1.0
                b[1] += share
                b[2] += share * share
                b[3] += w
                b[4] += t
            accepted += 1
        p_tries[sl] = tries
    part = np.zeros((n, 5))
    combo = np.zeros((n, maxn, 5))
    tries_total = 0.0
    for sl in range(SLICES):
        part += p_part[sl]
        combo += p_combo[sl]
        tries_total += p_tries[sl]
    return part, combo, tries_total
