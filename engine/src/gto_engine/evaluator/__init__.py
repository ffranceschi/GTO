"""Avaliador de mãos de 5 a 7 cartas (força maior = melhor)."""

import numpy as np

from gto_engine.evaluator.kernels import board_strengths, eval5, eval7

CATEGORIES = (
    "Carta alta",
    "Par",
    "Dois pares",
    "Trinca",
    "Sequência",
    "Flush",
    "Full house",
    "Quadra",
    "Straight flush",
)


def hand_category(strength: int) -> int:
    return strength >> 20


def evaluate_board(board: tuple[int, ...] | list[int]) -> np.ndarray:
    """Forças dos 1326 combos num board de 5 cartas (−1 = bloqueado)."""
    if len(board) != 5:
        raise ValueError("O board precisa ter 5 cartas para avaliar o showdown.")
    result: np.ndarray = board_strengths(np.asarray(board, dtype=np.int64))
    return result


__all__ = ["CATEGORIES", "eval5", "eval7", "evaluate_board", "hand_category"]
