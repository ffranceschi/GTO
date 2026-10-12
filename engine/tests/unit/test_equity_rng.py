"""T003 — PRNG xoshiro256** com sementes derivadas por splitmix64 (Princípio VI)."""

from __future__ import annotations

import numpy as np
from numba import njit

from gto_engine.equity.rng import derive_state, next_u64, randint


@njit(cache=True)
def _draws(seed: int, block: int, sl: int, n: int, k: int) -> np.ndarray:
    st = derive_state(seed, block, sl)
    out = np.empty(n, dtype=np.int64)
    for i in range(n):
        out[i] = randint(st, k)
    return out


@njit(cache=True)
def _raw(seed: int, n: int) -> np.ndarray:
    st = derive_state(seed, 0, 0)
    out = np.empty(n, dtype=np.uint64)
    for i in range(n):
        out[i] = next_u64(st)
    return out


def test_reprodutivel_e_sementes_distintas() -> None:
    a = _raw(42, 1000)
    assert np.array_equal(a, _raw(42, 1000))
    assert not np.array_equal(a, _raw(43, 1000))
    assert not np.array_equal(_draws(42, 0, 0, 100, 1000), _draws(42, 0, 1, 100, 1000))
    assert not np.array_equal(_draws(42, 0, 0, 100, 1000), _draws(42, 1, 0, 100, 1000))


def test_uniforme_qui_quadrado() -> None:
    k = 52
    x = _draws(7, 3, 5, 1_000_000, k)
    assert x.min() == 0 and x.max() == k - 1
    obs = np.bincount(x, minlength=k)
    exp = len(x) / k
    chi2 = float(((obs - exp) ** 2 / exp).sum())
    assert chi2 < 77.4  # quantil 99% da qui-quadrado com 51 g.l.
