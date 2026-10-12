"""Parâmetros do solve (data-model SolveParams)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from gto_engine.game.config import Street

Algorithm = Literal["dcfr", "cfr_plus", "linear_cfr"]

_DEFAULT_TIME = {Street.RIVER: 60.0, Street.TURN: 120.0, Street.FLOP: 900.0}


def default_time_limit(street: Street) -> float:
    """Padrão por street do board (spec FR-012): river 60 s, turn 120 s, flop 900 s."""
    return _DEFAULT_TIME[street]


@dataclass(frozen=True)
class SolveParams:
    algorithm: Algorithm = "dcfr"
    alpha: float = 1.5
    beta: float = 0.0
    gamma: float = 2.0
    target_exploitability_pct: float = 0.5
    time_limit_s: float | None = None  # None ⇒ padrão pela street
    max_iterations: int | None = None
    seed: int = 0

    def __post_init__(self) -> None:
        if self.algorithm not in ("dcfr", "cfr_plus", "linear_cfr"):
            raise ValueError(f"Algoritmo desconhecido: {self.algorithm}.")
        if not (0 <= self.target_exploitability_pct <= 100):
            raise ValueError("A explotabilidade alvo deve estar entre 0 e 100% do pote.")
        if self.time_limit_s is not None and not (0 < self.time_limit_s <= 86_400):
            raise ValueError("O tempo-limite deve estar em (0, 86.400] segundos.")
        if self.max_iterations is not None and self.max_iterations < 0:
            raise ValueError("O número máximo de iterações não pode ser negativo.")
        if not (0 <= self.seed < 2**64):
            raise ValueError("A semente deve estar entre 0 e 2^64 − 1.")

    def to_dict(self) -> dict[str, object]:
        return {
            "algorithm": self.algorithm,
            "alpha": self.alpha,
            "beta": self.beta,
            "gamma": self.gamma,
            "target_exploitability_pct": self.target_exploitability_pct,
            "time_limit_s": self.time_limit_s,
            "max_iterations": self.max_iterations,
            "seed": self.seed,
        }
