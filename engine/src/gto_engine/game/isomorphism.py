"""Isomorfismo de naipes (research R5).

Grupo = permutações de naipes que deixam o board (como conjunto) e os dois ranges invariantes.
Nos nós de chance só as cartas canônicas (menor carta de cada órbita) ganham subárvore; o valor
de uma carta isomorfa y é o da canônica x com as mãos permutadas por π⁻¹ (π(x) = y).
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from itertools import permutations

import numpy as np

from gto_engine.cards import COMBO_CARDS, COMBO_INDEX, N_CARDS, N_COMBOS

SUIT_PERMS: list[tuple[int, ...]] = list(permutations(range(4)))
IDENTITY = 0


def permute_card(card: int, k: int) -> int:
    return (card // 4) * 4 + SUIT_PERMS[k][card % 4]


def _card_table() -> np.ndarray:
    t = np.empty((len(SUIT_PERMS), N_CARDS), dtype=np.int64)
    for k in range(len(SUIT_PERMS)):
        for c in range(N_CARDS):
            t[k, c] = permute_card(c, k)
    return t


CARD_PERM = _card_table()


def _combo_table() -> np.ndarray:
    t = np.empty((len(SUIT_PERMS), N_COMBOS), dtype=np.int64)
    for k in range(len(SUIT_PERMS)):
        a = CARD_PERM[k][COMBO_CARDS[:, 0]]
        b = CARD_PERM[k][COMBO_CARDS[:, 1]]
        t[k] = COMBO_INDEX[a, b]
    return t


COMBO_PERM = _combo_table()


def permute_combo(combo: int, k: int) -> int:
    return int(COMBO_PERM[k, combo])


def inverse(k: int) -> int:
    p = SUIT_PERMS[k]
    inv = [0] * 4
    for i, j in enumerate(p):
        inv[j] = i
    return SUIT_PERMS.index(tuple(inv))


def compose(a: int, b: int) -> int:
    """Permutação "a depois de b"."""
    pa, pb = SUIT_PERMS[a], SUIT_PERMS[b]
    return SUIT_PERMS.index(tuple(pa[pb[i]] for i in range(4)))


def symmetry_group(board: Iterable[int], ranges: Sequence[np.ndarray]) -> list[int]:
    b = set(board)
    out = []
    for k in range(len(SUIT_PERMS)):
        if {permute_card(c, k) for c in b} != b:
            continue
        if all(np.array_equal(w[COMBO_PERM[k]], w) for w in ranges):
            out.append(k)
    return out


def stabilizer(group: Sequence[int], card: int) -> list[int]:
    return [k for k in group if permute_card(card, k) == card]


def chance_orbits(
    board: Iterable[int], group: Sequence[int]
) -> list[tuple[int, list[tuple[int, int]]]]:
    """[(carta canônica x, [(carta isomorfa y, k⁻¹ com π_k⁻¹(y) = x), …]), …] em ordem de x."""
    dealt = set(board)
    seen: set[int] = set()
    out: list[tuple[int, list[tuple[int, int]]]] = []
    for c in range(N_CARDS):
        if c in dealt or c in seen:
            continue
        members: dict[int, int] = {}
        for k in group:
            y = permute_card(c, k)
            if y not in members:
                members[y] = k
        seen |= set(members)
        x = min(members)
        # para cada y, uma permutação que leva x em y; guardamos a inversa (y → x)
        to_x = {y: compose(members[y], inverse(members[x])) for y in members}
        out.append((x, [(y, inverse(to_x[y])) for y in sorted(members) if y != x]))
    out.sort(key=lambda t: t[0])
    return out
