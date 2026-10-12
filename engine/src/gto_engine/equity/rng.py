"""PRNG xoshiro256** em Numba, com estado derivado por splitmix64 de (semente, bloco, fatia).

Cada fatia de cada bloco tem a sua sequência: o resultado do Monte Carlo independe do número de
threads (Princípio VI, research R3).
"""

import numpy as np
from numba import njit, uint64

_MASK = 0xFFFFFFFFFFFFFFFF


@njit(cache=True, nogil=True)
def _rotl(x, k):
    return (x << uint64(k)) | (x >> uint64(64 - k))


@njit(cache=True, nogil=True)
def splitmix64(x):
    x = uint64(x) + uint64(0x9E3779B97F4A7C15)
    z = x
    z = (z ^ (z >> uint64(30))) * uint64(0xBF58476D1CE4E5B9)
    z = (z ^ (z >> uint64(27))) * uint64(0x94D049BB133111EB)
    return x, z ^ (z >> uint64(31))


@njit(cache=True, nogil=True)
def derive_state(seed, block, sl):
    """Estado de 4 palavras para (semente, bloco, fatia)."""
    x = (
        uint64(seed)
        ^ (uint64(block) * uint64(0xD1342543DE82EF95))
        ^ (uint64(sl) * uint64(0x9E6C63D0676A9A99))
    )
    st = np.empty(4, dtype=np.uint64)
    for i in range(4):
        x, z = splitmix64(x)
        st[i] = z
    if st[0] == 0 and st[1] == 0 and st[2] == 0 and st[3] == 0:
        st[0] = uint64(1)
    return st


@njit(cache=True, nogil=True)
def next_u64(st):
    result = _rotl(st[1] * uint64(5), 7) * uint64(9)
    t = st[1] << uint64(17)
    st[2] ^= st[0]
    st[3] ^= st[1]
    st[1] ^= st[2]
    st[0] ^= st[3]
    st[2] ^= t
    st[3] = _rotl(st[3], 45)
    return result


@njit(cache=True, nogil=True)
def random(st):
    """Uniforme em [0, 1) com 53 bits."""
    return float(next_u64(st) >> uint64(11)) * (1.0 / 9007199254740992.0)


@njit(cache=True, nogil=True)
def randint(st, n):
    """Inteiro uniforme em [0, n)."""
    return int(random(st) * n)


__all__ = ["_MASK", "derive_state", "next_u64", "randint", "random", "splitmix64"]
