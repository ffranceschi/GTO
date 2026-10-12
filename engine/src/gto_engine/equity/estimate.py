"""Estimativa do custo da enumeração exata e escolha do método (research R4, FR-016).

Contagem pura (sem enumerar): cálculo leve, ≤ 200 ms com benchmark.
"""

from __future__ import annotations

from dataclasses import dataclass
from math import comb, prod
from typing import Literal

from gto_engine.cards import N_CARDS
from gto_engine.equity.request import EquityRequest

# avaliações de mão por segundo no hardware de referência (8 núcleos), valor conservador
# calibrado pelos benchmarks (test_bench_equity); o protótipo mediu ≈ 30 M/s no M1 Max
DEFAULT_RATE = 20e6
EXACT_LIMIT_S = 2.0


@dataclass(frozen=True)
class EquityEstimate:
    method: Literal["exact", "monte_carlo"]
    exact_evaluations: int
    estimated_exact_s: float
    rate: float


def exact_evaluations(req: EquityRequest) -> int:
    boards = comb(N_CARDS - len(req.board), 5 - len(req.board))
    sizes = [len(req.participant_combos(i)[0]) for i in range(len(req.participants))]
    if len(sizes) == 2:
        return boards * (sizes[0] + sizes[1])
    # multiway: limite superior (ignora conflitos entre mãos) × participantes
    return boards * prod(sizes) * len(sizes)


def estimate_equity(req: EquityRequest, rate: float = DEFAULT_RATE) -> EquityEstimate:
    evals = exact_evaluations(req)
    secs = evals / rate
    if req.method == "auto":
        method: Literal["exact", "monte_carlo"] = (
            "exact" if secs <= EXACT_LIMIT_S else "monte_carlo"
        )
    else:
        method = req.method
    return EquityEstimate(method, evals, secs, rate)
