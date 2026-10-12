"""Parse de notação de ranges (cálculo leve na requisição, ≤ 200 ms — Princípio V)."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter
from gto_engine.cards import N_COMBOS, parse_card
from gto_engine.ranges import format_range, parse_range
from pydantic import BaseModel, Field

from gto_api.schemas.solves import Card, Problem

router = APIRouter(prefix="/api/v1", tags=["ranges"])


class RangeParseRequest(BaseModel):
    notation: str
    board: Annotated[list[Card], Field(max_length=5)] = []


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
    r = parse_range(req.notation)
    dead = [parse_card(c) for c in req.board]
    after = r.combo_count(dead)
    return RangeParseResult(
        canonical=format_range(r),
        weights=r.weights.tolist(),
        combos=r.combo_count(),
        combos_after_board=after,
        pct_of_total=after / N_COMBOS,
    )
