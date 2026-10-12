"""Parse e formatação de ranges (cálculo leve na requisição, ≤ 200 ms — Princípio V)."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter
from gto_engine.cards import N_COMBOS, parse_card
from gto_engine.ranges import Range, format_range, parse_range
from pydantic import BaseModel, Field

from gto_api.schemas.solves import Card, Problem

router = APIRouter(prefix="/api/v1", tags=["ranges"])


Weights = Annotated[
    list[Annotated[float, Field(ge=0, le=1)]], Field(min_length=N_COMBOS, max_length=N_COMBOS)
]
DeadCards = Annotated[
    list[Card],
    Field(
        max_length=15,
        description="Cartas mortas além do board (mãos específicas dos outros participantes)",
    ),
]


class RangeParseRequest(BaseModel):
    notation: str
    board: Annotated[list[Card], Field(max_length=5)] = []
    dead_cards: DeadCards = []


class RangeFormatRequest(BaseModel):
    weights: Weights
    dead_cards: DeadCards = []


class RangeParseResult(BaseModel):
    canonical: str
    weights: Annotated[list[float], Field(min_length=N_COMBOS, max_length=N_COMBOS)]
    combos: float
    combos_after_board: float
    pct_of_total: float


@router.post(
    "/ranges/parse",
    operation_id="parseRange",
    response_model=RangeParseResult,
    responses={422: {"model": Problem}},
)
def parse(req: RangeParseRequest) -> RangeParseResult:
    return _result(parse_range(req.notation), [*req.board, *req.dead_cards])


@router.post(
    "/ranges/format",
    operation_id="formatRange",
    response_model=RangeParseResult,
    responses={422: {"model": Problem}},
)
def format_(req: RangeFormatRequest) -> RangeParseResult:
    """Pesos (1326) → notação canônica compacta (grade → texto, research R8 da 001)."""
    return _result(Range(req.weights), req.dead_cards)


def _result(r: Range, dead_cards: list[str]) -> RangeParseResult:
    dead = sorted({parse_card(c) for c in dead_cards})
    after = r.combo_count(dead)
    return RangeParseResult(
        canonical=format_range(r),
        weights=r.weights.tolist(),
        combos=r.combo_count(),
        combos_after_board=after,
        pct_of_total=after / N_COMBOS,
    )
