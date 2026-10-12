"""Oráculo de equity por força bruta com phevaluator (independente do nosso avaliador)."""

from __future__ import annotations

import itertools

from phevaluator import evaluate_cards

from gto_engine.cards import COMBO_CARDS, card_str


def _cards(combo: int) -> tuple[int, int]:
    a, b = COMBO_CARDS[combo]
    return int(a), int(b)


def brute_force(
    participants: list[dict[int, float]], board: tuple[int, ...]
) -> list[tuple[float, float, float, dict[int, float]]]:
    """Por participante: (equity, win, tie, equity por combo); cada um é {combo: peso}."""
    n = len(participants)
    share = [0.0] * n
    win = [0.0] * n
    tie = [0.0] * n
    total = 0.0
    per_num = [dict.fromkeys(p, 0.0) for p in participants]
    per_den = [dict.fromkeys(p, 0.0) for p in participants]
    for tup in itertools.product(*[list(p.items()) for p in participants]):
        cards = [c for combo, _ in tup for c in _cards(combo)]
        if len(set(cards)) != len(cards) or set(cards) & set(board):
            continue
        weight = 1.0
        for _, w in tup:
            weight *= w
        rest = [c for c in range(52) if c not in cards and c not in board]
        for extra in itertools.combinations(rest, 5 - len(board)):
            full = [card_str(c) for c in (*board, *extra)]
            ranks = [
                evaluate_cards(*(card_str(c) for c in _cards(combo)), *full) for combo, _ in tup
            ]
            best = min(ranks)
            winners = [i for i, r in enumerate(ranks) if r == best]
            total += weight
            for i, (combo, _) in enumerate(tup):
                s = 1.0 / len(winners) if i in winners else 0.0
                share[i] += weight * s
                if i in winners:
                    if len(winners) == 1:
                        win[i] += weight
                    else:
                        tie[i] += weight
                per_num[i][combo] += weight * s
                per_den[i][combo] += weight
    out = []
    for i in range(n):
        per = {c: per_num[i][c] / per_den[i][c] for c in participants[i] if per_den[i][c] > 0}
        out.append((share[i] / total, win[i] / total, tie[i] / total, per))
    return out
