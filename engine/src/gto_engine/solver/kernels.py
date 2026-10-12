"""Kernels Numba do CFR vetorizado (árvore pública × vetores de mãos privadas).

Utilidade de um jogador = fichas recebidas do pote − fichas investidas no spot; o pote inicial
`pot` é dinheiro morto, logo u_OOP + u_IP = pot (research R6).

Modos de travessia: 0 = atualização CFR do jogador `trav` (regrets + soma da estratégia);
1 = best response de `trav` contra `sigma`; 2 = avaliação com `sigma` para os dois.
"""

import numpy as np
from numba import njit

FOLD = 2
SHOWDOWN = 3
CHANCE = 1


@njit(cache=True, nogil=True)
def _card_sums(reach, hc, n_cards, k):
    cs = np.zeros(n_cards)
    tot = 0.0
    for j in range(reach.shape[0]):
        r = reach[j]
        if r != 0.0:
            tot += r
            for c in range(k):
                cs[hc[j, c]] += r
    return tot, cs


@njit(cache=True, nogil=True)
def compat_sums(reach_opp, hc_t, hc_o, same_t, n_cards, k):
    """Para cada mão do jogador, soma do reach do oponente compatível (sem cartas em comum)."""
    tot, cs = _card_sums(reach_opp, hc_o, n_cards, k)
    n = hc_t.shape[0]
    out = np.empty(n)
    for h in range(n):
        v = tot
        for c in range(k):
            v -= cs[hc_t[h, c]]
        if same_t[h] >= 0:
            v += (k - 1) * reach_opp[same_t[h]]
        out[h] = v
    return out


@njit(cache=True, nogil=True)
def showdown_sums(b, reach_opp, hc_t, hc_o, str_t, str_o, ord_t, ord_o, n_cards, k):
    """(win, lose) por mão: reach do oponente compatível com força menor / maior."""
    n_t = hc_t.shape[0]
    n_o = hc_o.shape[0]
    win = np.zeros(n_t)
    lose = np.zeros(n_t)
    acc = 0.0
    cacc = np.zeros(n_cards)
    j = 0
    for ii in range(n_t):
        h = ord_t[b, ii]
        s = str_t[b, h]
        if s < 0:
            continue
        while j < n_o and str_o[b, ord_o[b, j]] < s:
            o = ord_o[b, j]
            r = reach_opp[o]
            if r != 0.0:
                acc += r
                for c in range(k):
                    cacc[hc_o[o, c]] += r
            j += 1
        v = acc
        for c in range(k):
            v -= cacc[hc_t[h, c]]
        win[h] = v
    acc = 0.0
    cacc[:] = 0.0
    j = n_o - 1
    for ii in range(n_t - 1, -1, -1):
        h = ord_t[b, ii]
        s = str_t[b, h]
        if s < 0:
            continue
        while j >= 0 and str_o[b, ord_o[b, j]] > s:
            o = ord_o[b, j]
            r = reach_opp[o]
            if r != 0.0:
                acc += r
                for c in range(k):
                    cacc[hc_o[o, c]] += r
            j -= 1
        v = acc
        for c in range(k):
            v -= cacc[hc_t[h, c]]
        lose[h] = v
    return win, lose


@njit(cache=True, nogil=True)
def _terminal(T, node, trav, reach_opp):
    if trav == 0:
        hc_t, hc_o, same_t, str_t, str_o, ord_t, ord_o = (
            T.hc0,
            T.hc1,
            T.same0,
            T.str0,
            T.str1,
            T.ord0,
            T.ord1,
        )
    else:
        hc_t, hc_o, same_t, str_t, str_o, ord_t, ord_o = (
            T.hc1,
            T.hc0,
            T.same1,
            T.str1,
            T.str0,
            T.ord1,
            T.ord0,
        )
    c_t = T.inv[node, trav]
    c_o = T.inv[node, 1 - trav]
    P = T.pot
    compat = compat_sums(reach_opp, hc_t, hc_o, same_t, T.n_cards, T.k)
    n = hc_t.shape[0]
    out = np.empty(n)
    if T.node_type[node] == FOLD:
        folder = T.node_player[node]
        pay = -c_t if folder == trav else P + c_o
        for h in range(n):
            out[h] = pay * compat[h]
        return out
    b = T.board_id[node]
    win, lose = showdown_sums(b, reach_opp, hc_t, hc_o, str_t, str_o, ord_t, ord_o, T.n_cards, T.k)
    tie_pay = 0.5 * P + 0.5 * (c_o - c_t)
    for h in range(n):
        if str_t[b, h] < 0:
            out[h] = 0.0
        else:
            tie = compat[h] - win[h] - lose[h]
            out[h] = win[h] * (P + c_o) - lose[h] * c_t + tie * tie_pay
    return out


@njit(cache=True, nogil=True)
def add_isomorphic(T, ch, trav, f, vc, v):
    """Soma em `v` os valores das cartas isomorfas à carta canônica do filho `ch` (R5)."""
    hc_t = T.hc0 if trav == 0 else T.hc1
    perm = T.perm0 if trav == 0 else T.perm1
    n_t = v.shape[0]
    for m in range(T.iso_start[ch], T.iso_start[ch + 1]):
        y = T.iso_card[m]
        k = T.iso_perm[m]
        for h in range(n_t):
            blocked = False
            for c in range(T.k):
                if hc_t[h, c] == y:
                    blocked = True
            if not blocked:
                v[h] += f * vc[perm[k, h]]


@njit(cache=True, nogil=True)
def current_strategy(regrets, off, A, n):
    sig = np.empty((A, n))
    for h in range(n):
        tot = 0.0
        for a in range(A):
            r = regrets[off + a * n + h]
            if r > 0:
                tot += r
        for a in range(A):
            r = regrets[off + a * n + h]
            sig[a, h] = (r if r > 0 else 0.0) / tot if tot > 0 else 1.0 / A
    return sig


@njit(cache=True, nogil=True)
def _fixed_strategy(sigma, off, A, n):
    """Lê a estratégia do nó normalizando por mão (aceita somas acumuladas ou já normalizada)."""
    sig = np.empty((A, n))
    for h in range(n):
        tot = 0.0
        for a in range(A):
            tot += sigma[off + a * n + h]
        for a in range(A):
            sig[a, h] = sigma[off + a * n + h] / tot if tot > 0 else 1.0 / A
    return sig


# sem cache: Numba não cacheia com segurança funções recursivas nem quem as chama
@njit(nogil=True)
def traverse(
    T,
    node,
    trav,
    reach_trav,
    reach_opp,
    mode,
    sigma,
    regrets,
    ssum,
    pos_d,
    neg_d,
    strat_d,
    strat_w,
    plus,
):
    t = T.node_type[node]
    if t in (FOLD, SHOWDOWN):
        return _terminal(T, node, trav, reach_opp)
    n_t = reach_trav.shape[0]
    if reach_opp.sum() == 0.0:
        return np.zeros(n_t)
    cs = T.child_start[node]
    nc = T.child_count[node]
    if t == CHANCE:
        hc_t = T.hc0 if trav == 0 else T.hc1
        hc_o = T.hc1 if trav == 0 else T.hc0
        f = T.chance_factor[node]
        v = np.zeros(n_t)
        for i in range(nc):
            ch = T.children[cs + i]
            x = T.chance_card[ch]
            rt = reach_trav.copy()
            ok = np.ones(n_t, dtype=np.bool_)
            for h in range(n_t):
                for c in range(T.k):
                    if hc_t[h, c] == x:
                        ok[h] = False
                if not ok[h]:
                    rt[h] = 0.0
            ro = reach_opp.copy()
            for j in range(ro.shape[0]):
                for c in range(T.k):
                    if hc_o[j, c] == x:
                        ro[j] = 0.0
            vc = traverse(
                T,
                ch,
                trav,
                rt,
                ro,
                mode,
                sigma,
                regrets,
                ssum,
                pos_d,
                neg_d,
                strat_d,
                strat_w,
                plus,
            )
            for h in range(n_t):
                if ok[h]:
                    v[h] += f * vc[h]
            add_isomorphic(T, ch, trav, f, vc, v)
        return v
    # nó de decisão
    p = T.node_player[node]
    d = T.dec_index[node]
    off = T.dec_offset[d]
    n_p = T.w0.shape[0] if p == 0 else T.w1.shape[0]
    if mode == 0:
        sig = current_strategy(regrets, off, nc, n_p)
    else:
        sig = _fixed_strategy(sigma, off, nc, n_p)
    if p == trav:
        vals = np.empty((nc, n_t))
        for a in range(nc):
            vals[a] = traverse(
                T,
                T.children[cs + a],
                trav,
                reach_trav * sig[a],
                reach_opp,
                mode,
                sigma,
                regrets,
                ssum,
                pos_d,
                neg_d,
                strat_d,
                strat_w,
                plus,
            )
        v = np.zeros(n_t)
        if mode == 1:
            for h in range(n_t):
                best = vals[0, h]
                for a in range(1, nc):
                    if vals[a, h] > best:
                        best = vals[a, h]
                v[h] = best
            return v
        for a in range(nc):
            v += sig[a] * vals[a]
        if mode == 0:
            for a in range(nc):
                for h in range(n_t):
                    i = off + a * n_t + h
                    inst = vals[a, h] - v[h]
                    r = regrets[i]
                    if plus:
                        r = r + inst
                        regrets[i] = r if r > 0 else 0.0
                    else:
                        regrets[i] = r * (pos_d if r > 0 else neg_d) + inst
                    ssum[i] = ssum[i] * strat_d + strat_w * reach_trav[h] * sig[a, h]
        return v
    v = np.zeros(n_t)
    for a in range(nc):
        v += traverse(
            T,
            T.children[cs + a],
            trav,
            reach_trav,
            reach_opp * sig[a],
            mode,
            sigma,
            regrets,
            ssum,
            pos_d,
            neg_d,
            strat_d,
            strat_w,
            plus,
        )
    return v


# sem cache: Numba não cacheia com segurança funções recursivas nem quem as chama
@njit(nogil=True)
def run_iterations(T, regrets, ssum, t_start, k, alpha, beta, gamma, algo):
    """Executa k iterações (atualizações alternadas). algo: 0 = DCFR/LCFR, 1 = CFR+."""
    dummy = np.zeros(1, dtype=np.float32)
    for t in range(t_start, t_start + k):
        tf = float(t)
        plus = algo == 1
        if plus:
            pos_d, neg_d, strat_d, strat_w = 1.0, 1.0, 1.0, tf
        else:
            ta = tf**alpha
            tb = tf**beta
            pos_d = ta / (ta + 1.0)
            neg_d = tb / (tb + 1.0)
            strat_d = (tf / (tf + 1.0)) ** gamma
            strat_w = 1.0
        for trav in range(2):
            rt = T.w0.copy() if trav == 0 else T.w1.copy()
            ro = T.w1.copy() if trav == 0 else T.w0.copy()
            traverse(
                T, 0, trav, rt, ro, 0, dummy, regrets, ssum, pos_d, neg_d, strat_d, strat_w, plus
            )


@njit(cache=True, nogil=True)
def average_strategy(T, ssum):
    out = np.empty(ssum.shape[0], dtype=np.float32)
    n_dec = T.dec_offset.shape[0] - 1
    for d in range(n_dec):
        off = T.dec_offset[d]
        size = T.dec_offset[d + 1] - off
        p = T.node_player[T.dec_node[d]]
        n = T.w0.shape[0] if p == 0 else T.w1.shape[0]
        A = size // n if n > 0 else 0
        for h in range(n):
            tot = 0.0
            for a in range(A):
                tot += ssum[off + a * n + h]
            for a in range(A):
                out[off + a * n + h] = ssum[off + a * n + h] / tot if tot > 0 else 1.0 / A
    return out


# sem cache: Numba não cacheia com segurança funções recursivas nem quem as chama
@njit(nogil=True)
def root_values(T, sigma, trav, mode):
    """Valores contrafactuais na raiz para `trav` (mode 1 = best response, 2 = avaliação)."""
    rt = T.w0.copy() if trav == 0 else T.w1.copy()
    ro = T.w1.copy() if trav == 0 else T.w0.copy()
    dummy = np.zeros(1, dtype=np.float32)
    return traverse(T, 0, trav, rt, ro, mode, sigma, dummy, dummy, 1.0, 1.0, 1.0, 1.0, False)


@njit(cache=True, nogil=True)
def total_pair_weight(T):
    c = compat_sums(T.w1, T.hc0, T.hc1, T.same0, T.n_cards, T.k)
    return (T.w0 * c).sum()


@njit(cache=True, nogil=True)
def normalize_inplace(T, ssum):
    """Converte as somas acumuladas em estratégia média normalizada, no mesmo buffer."""
    n_dec = T.dec_offset.shape[0] - 1
    for d in range(n_dec):
        off = T.dec_offset[d]
        size = T.dec_offset[d + 1] - off
        p = T.node_player[T.dec_node[d]]
        n = T.w0.shape[0] if p == 0 else T.w1.shape[0]
        A = size // n if n > 0 else 0
        for h in range(n):
            tot = 0.0
            for a in range(A):
                tot += ssum[off + a * n + h]
            for a in range(A):
                ssum[off + a * n + h] = ssum[off + a * n + h] / tot if tot > 0 else 1.0 / A


@njit(cache=True, nogil=True)
def record_decision(T, node, trav, v, reach_opp, ev, eq):
    """Grava EV (bb) e equity (all-in sobre os boards finais possíveis) do jogador da vez no nó."""
    if trav == 0:
        hc_t, hc_o, same_t, str_t, str_o, ord_t, ord_o = (
            T.hc0,
            T.hc1,
            T.same0,
            T.str0,
            T.str1,
            T.ord0,
            T.ord1,
        )
    else:
        hc_t, hc_o, same_t, str_t, str_o, ord_t, ord_o = (
            T.hc1,
            T.hc0,
            T.same1,
            T.str1,
            T.str0,
            T.ord1,
            T.ord0,
        )
    d = T.dec_index[node]
    co = T.dec_combo_offset[d]
    n = hc_t.shape[0]
    norm = compat_sums(reach_opp, hc_t, hc_o, same_t, T.n_cards, T.k)
    num = np.zeros(n)
    den = np.zeros(n)
    for bi in range(T.dec_board_start[d], T.dec_board_start[d + 1]):
        b = T.dec_boards[bi]
        ro = reach_opp.copy()
        for j in range(ro.shape[0]):
            if str_o[b, j] < 0:
                ro[j] = 0.0
        win, lose = showdown_sums(b, ro, hc_t, hc_o, str_t, str_o, ord_t, ord_o, T.n_cards, T.k)
        cb = compat_sums(ro, hc_t, hc_o, same_t, T.n_cards, T.k)
        for h in range(n):
            if str_t[b, h] >= 0:
                num[h] += win[h] + 0.5 * (cb[h] - win[h] - lose[h])
                den[h] += cb[h]
    for h in range(n):
        ev[co + h] = v[h] / norm[h] if norm[h] > 0 else 0.0
        eq[co + h] = num[h] / den[h] if den[h] > 0 else 0.0


# sem cache: recursiva
@njit(nogil=True)
def finalize_traverse(T, node, trav, reach_trav, reach_opp, sigma, ev, eq):
    """Avalia a estratégia média (modo 2) gravando EV e equity nos nós de decisão de `trav`."""
    t = T.node_type[node]
    if t in (FOLD, SHOWDOWN):
        return _terminal(T, node, trav, reach_opp)
    n_t = reach_trav.shape[0]
    cs = T.child_start[node]
    nc = T.child_count[node]
    if t == CHANCE:
        hc_t = T.hc0 if trav == 0 else T.hc1
        hc_o = T.hc1 if trav == 0 else T.hc0
        f = T.chance_factor[node]
        v = np.zeros(n_t)
        for i in range(nc):
            ch = T.children[cs + i]
            x = T.chance_card[ch]
            rt = reach_trav.copy()
            ok = np.ones(n_t, dtype=np.bool_)
            for h in range(n_t):
                for c in range(T.k):
                    if hc_t[h, c] == x:
                        ok[h] = False
                if not ok[h]:
                    rt[h] = 0.0
            ro = reach_opp.copy()
            for j in range(ro.shape[0]):
                for c in range(T.k):
                    if hc_o[j, c] == x:
                        ro[j] = 0.0
            vc = finalize_traverse(T, ch, trav, rt, ro, sigma, ev, eq)
            for h in range(n_t):
                if ok[h]:
                    v[h] += f * vc[h]
            add_isomorphic(T, ch, trav, f, vc, v)
        return v
    p = T.node_player[node]
    d = T.dec_index[node]
    off = T.dec_offset[d]
    n_p = T.w0.shape[0] if p == 0 else T.w1.shape[0]
    sig = _fixed_strategy(sigma, off, nc, n_p)
    v = np.zeros(n_t)
    if p == trav:
        for a in range(nc):
            v += sig[a] * finalize_traverse(
                T, T.children[cs + a], trav, reach_trav * sig[a], reach_opp, sigma, ev, eq
            )
        record_decision(T, node, trav, v, reach_opp, ev, eq)
        return v
    for a in range(nc):
        v += finalize_traverse(
            T, T.children[cs + a], trav, reach_trav, reach_opp * sig[a], sigma, ev, eq
        )
    return v
