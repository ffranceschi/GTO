"""Tabelas de lookup do avaliador (geradas uma vez e cacheadas em .npy).

- Flush: índice = máscara de 13 bits dos ranks do naipe do flush (8192 entradas).
- Não-flush: perfect hash mínimo do multiconjunto de ranks (contagens 0..4 por rank),
  ordenado pelo sistema numérico combinatório (`MULTISET_DP`), um bloco por tamanho 5, 6 ou 7.

Força: categoria << 20 | r1 << 16 | r2 << 12 | r3 << 8 | r4 << 4 | r5 (maior = melhor);
categorias 0 carta alta … 8 straight flush.
"""

from __future__ import annotations

import os
from pathlib import Path

import numpy as np

TABLE_VERSION = 1


def multiset_dp() -> np.ndarray:
    """dp[r, n] = nº de multiconjuntos de tamanho n sobre r ranks com no máximo 4 por rank."""
    dp = np.zeros((14, 8), dtype=np.int64)
    dp[0, 0] = 1
    for r in range(1, 14):
        for n in range(8):
            dp[r, n] = sum(dp[r - 1, n - k] for k in range(0, min(4, n) + 1))
    return dp


def _straight_top(mask: int) -> int:
    """Rank do topo da maior sequência (−1 se não há); A2345 conta com topo 3 (o 5)."""
    for top in range(12, 3, -1):
        need = 0b11111 << (top - 4)
        if mask & need == need:
            return top
    if mask & 0b1000000001111 == 0b1000000001111:
        return 3
    return -1


def _encode(cat: int, ranks: list[int]) -> int:
    v = cat << 20
    for i, r in enumerate(ranks[:5]):
        v |= r << (16 - 4 * i)
    return v


def strength_from_counts(counts: list[int]) -> int:
    """Melhor mão de 5 cartas (sem flush) a partir das contagens por rank."""
    mask = 0
    for r in range(13):
        if counts[r]:
            mask |= 1 << r
    quads = [r for r in range(12, -1, -1) if counts[r] >= 4]
    trips = [r for r in range(12, -1, -1) if counts[r] == 3]
    pairs = [r for r in range(12, -1, -1) if counts[r] == 2]
    singles_desc = [r for r in range(12, -1, -1) if counts[r] >= 1]
    if quads:
        q = quads[0]
        kick = [r for r in singles_desc if r != q][:1]
        return _encode(7, [q, *kick])
    if trips and (len(trips) >= 2 or pairs):
        t = trips[0]
        p = max([*trips[1:], *pairs])
        return _encode(6, [t, p])
    top = _straight_top(mask)
    if top >= 0:
        return _encode(4, [top])
    if trips:
        t = trips[0]
        return _encode(3, [t, *[r for r in singles_desc if r != t][:2]])
    if len(pairs) >= 2:
        p1, p2 = pairs[0], pairs[1]
        return _encode(2, [p1, p2, *[r for r in singles_desc if r not in (p1, p2)][:1]])
    if pairs:
        p = pairs[0]
        return _encode(1, [p, *[r for r in singles_desc if r != p][:3]])
    return _encode(0, singles_desc[:5])


def flush_strength(mask: int) -> int:
    top = _straight_top(mask)
    if top >= 0:
        return _encode(8, [top])
    ranks = [r for r in range(12, -1, -1) if mask >> r & 1][:5]
    return _encode(5, ranks)


def _rank_multiset(counts: list[int], dp: np.ndarray) -> int:
    n = sum(counts)
    idx = 0
    for r in range(13):
        rest = 12 - r
        for v in range(counts[r]):
            idx += int(dp[rest, n - v]) if n - v >= 0 else 0
        n -= counts[r]
    return idx


def generate() -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    dp = multiset_dp()
    offsets = np.zeros(8, dtype=np.int64)
    total = 0
    for n in range(8):
        offsets[n] = total
        total += int(dp[13, n])
    noflush = np.full(total, -1, dtype=np.int32)

    def rec(r: int, left: int, counts: list[int]) -> None:
        if r == 13:
            if left == 0:
                n = sum(counts)
                noflush[offsets[n] + _rank_multiset(counts, dp)] = strength_from_counts(counts)
            return
        for k in range(0, min(4, left) + 1):
            counts.append(k)
            rec(r + 1, left - k, counts)
            counts.pop()

    for n in (5, 6, 7):
        rec(0, n, [])
    flush = np.zeros(1 << 13, dtype=np.int32)
    for m in range(1 << 13):
        if bin(m).count("1") >= 5:
            flush[m] = flush_strength(m)
    return flush, noflush, offsets


def _cache_dir() -> Path:
    base = os.environ.get("GTO_TABLES_DIR") or os.environ.get("NUMBA_CACHE_DIR")
    if base:
        return Path(base)
    return Path(__file__).resolve().parent / "_cache"


def load_tables() -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Carrega (ou gera e cacheia) as tabelas: flush, noflush, offsets, dp."""
    d = _cache_dir()
    path = d / f"evaluator_tables_v{TABLE_VERSION}.npz"
    if path.exists():
        with np.load(path, allow_pickle=False) as z:
            return z["flush"], z["noflush"], z["offsets"], z["dp"]
    flush, noflush, offsets = generate()
    dp = multiset_dp()
    try:
        d.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".tmp.npz")
        np.savez(tmp, flush=flush, noflush=noflush, offsets=offsets, dp=dp)
        tmp.replace(path)
    except OSError:
        pass  # diretório somente leitura: segue sem cache
    return flush, noflush, offsets, dp
