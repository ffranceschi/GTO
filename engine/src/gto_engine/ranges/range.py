"""Range = peso em [0, 1] para cada um dos 1326 combos."""

from __future__ import annotations

from collections.abc import Iterable

import numpy as np

from gto_engine.cards import N_COMBOS, blocked_mask


class Range:
    __slots__ = ("weights",)

    def __init__(self, weights: np.ndarray | Iterable[float] | None = None) -> None:
        w = np.zeros(N_COMBOS) if weights is None else np.asarray(weights, dtype=np.float64)
        if w.shape != (N_COMBOS,):
            raise ValueError(f"Um range precisa de exatamente {N_COMBOS} pesos.")
        if np.any(w < 0) or np.any(w > 1) or not np.all(np.isfinite(w)):
            raise ValueError("Os pesos de um range devem estar entre 0 e 1.")
        self.weights = w.copy()
        self.weights.setflags(write=False)

    def combo_count(self, dead_cards: Iterable[int] = ()) -> float:
        """Combos efetivos (soma dos pesos) descontando os que usam cartas mortas."""
        dead = list(dead_cards)
        w = self.weights
        if dead:
            w = np.where(blocked_mask(dead), 0.0, w)
        return float(w.sum())

    def __eq__(self, other: object) -> bool:
        return isinstance(other, Range) and np.array_equal(self.weights, other.weights)

    def __hash__(self) -> int:
        return hash(self.weights.tobytes())

    def __repr__(self) -> str:
        from gto_engine.ranges.notation import format_range

        return f"Range({format_range(self)!r})"
