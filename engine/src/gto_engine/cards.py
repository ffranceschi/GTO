"""Cartas e combos: 52 cartas, 1326 combos de duas cartas.

Carta = rank × 4 + naipe, com ranks 0..12 = 2..A e naipes na ordem s, h, d, c.
"""

from __future__ import annotations

import numpy as np

RANKS = "23456789TJQKA"
SUITS = "shdc"
N_CARDS = 52
N_COMBOS = 1326


class InvalidCardError(ValueError):
    """Carta ou combo em notação inválida."""


def card_rank(card: int) -> int:
    return card // 4


def card_suit(card: int) -> int:
    return card % 4


def parse_card(text: str) -> int:
    if len(text) != 2 or text[0].upper() not in RANKS or text[1].lower() not in SUITS:
        raise InvalidCardError(f"Carta inválida: '{text}' (use, por exemplo, 'Ah', 'Td', '2c').")
    return RANKS.index(text[0].upper()) * 4 + SUITS.index(text[1].lower())


def card_str(card: int) -> str:
    if not 0 <= card < N_CARDS:
        raise InvalidCardError(f"Índice de carta fora do intervalo: {card}.")
    return RANKS[card // 4] + SUITS[card % 4]


def _sort_key(card: int) -> tuple[int, int]:
    # maior rank primeiro; no mesmo rank, ordem de naipe s, h, d, c
    return (-card_rank(card), card_suit(card))


def _build_combos() -> tuple[np.ndarray, np.ndarray]:
    cards = np.empty((N_COMBOS, 2), dtype=np.int16)
    index = -np.ones((N_CARDS, N_CARDS), dtype=np.int32)
    k = 0
    for a in range(N_CARDS):
        for b in range(a + 1, N_CARDS):
            hi, lo = sorted((a, b), key=_sort_key)
            cards[k] = (hi, lo)
            index[a, b] = index[b, a] = k
            k += 1
    cards.setflags(write=False)
    index.setflags(write=False)
    return cards, index


COMBO_CARDS, COMBO_INDEX = _build_combos()
"""COMBO_CARDS[i] = (carta maior, carta menor); COMBO_INDEX[a, b] = índice do combo."""


def combo_index(a: int, b: int) -> int:
    if a == b:
        raise InvalidCardError("Um combo precisa de duas cartas distintas.")
    return int(COMBO_INDEX[a, b])


def parse_combo(text: str) -> int:
    t = text.strip()
    if len(t) != 4:
        raise InvalidCardError(f"Combo inválido: '{text}' (use, por exemplo, 'AhKh').")
    a, b = parse_card(t[:2]), parse_card(t[2:])
    if a == b:
        raise InvalidCardError(f"Combo inválido: '{text}' repete a mesma carta.")
    return combo_index(a, b)


def combo_str(index: int) -> str:
    a, b = COMBO_CARDS[index]
    return card_str(int(a)) + card_str(int(b))


def blocked_mask(dead_cards: list[int] | tuple[int, ...] | np.ndarray) -> np.ndarray:
    """Máscara booleana de combos que usam alguma carta morta."""
    dead = np.zeros(N_CARDS, dtype=bool)
    for c in dead_cards:
        dead[int(c)] = True
    mask: np.ndarray = dead[COMBO_CARDS[:, 0]] | dead[COMBO_CARDS[:, 1]]
    return mask


_CONFLICT: np.ndarray | None = None


def combo_conflicts() -> np.ndarray:
    """Matriz (1326, 1326) booleana: True quando dois combos compartilham carta."""
    global _CONFLICT
    if _CONFLICT is None:
        has = np.zeros((N_COMBOS, N_CARDS), dtype=bool)
        has[np.arange(N_COMBOS), COMBO_CARDS[:, 0]] = True
        has[np.arange(N_COMBOS), COMBO_CARDS[:, 1]] = True
        m = (has.astype(np.uint8) @ has.T.astype(np.uint8)) > 0
        m.setflags(write=False)
        _CONFLICT = m
    return _CONFLICT
