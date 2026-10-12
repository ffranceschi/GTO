"""Schemas Pydantic v2 da calculadora de equity (specs/001-…/contracts/openapi.yaml)."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Any, Literal

from gto_engine.cards import parse_card
from gto_engine.equity.request import EquityRequest as EngineRequest
from gto_engine.equity.result import EquityResult as EngineResult
from pydantic import BaseModel, Field

from gto_api.schemas.solves import Card, NotationRange, Problem, WeightsRange, to_range

ParticipantInput = NotationRange | WeightsRange
Method = Literal["exact", "monte_carlo"]
StopReason = Literal["exact", "target_reached", "time_limit", "user_stopped"]
EquityJobStatus = Literal["queued", "running", "completed", "cancelled", "failed"]


class EquityRequest(BaseModel):
    # 2 a 6 participantes e 0/3/4/5 cartas: validados pelo motor, com mensagem pt-BR específica
    participants: Annotated[list[ParticipantInput], Field(max_length=6)]
    board: Annotated[list[Card], Field(max_length=5)] = []
    method: Literal["auto", "exact", "monte_carlo"] = "auto"
    target_margin_pp: Annotated[float, Field(ge=0.05, le=1)] = 0.1
    time_limit_s: Annotated[float, Field(gt=0, le=3600)] = 60.0
    seed: Annotated[int, Field(ge=0, lt=2**64)] = 0

    def to_engine(self, method: str | None = None) -> EngineRequest:
        return EngineRequest(
            tuple(to_range(p) for p in self.participants),
            tuple(parse_card(c) for c in self.board),
            method=method or self.method,  # type: ignore[arg-type]
            target_margin_pp=self.target_margin_pp,
            time_limit_s=self.time_limit_s,
            seed=self.seed,
        )


class EquityEstimate(BaseModel):
    method: Method
    exact_evaluations: int
    estimated_exact_s: float


class ComboResult(BaseModel):
    combo: str
    weight: float
    equity: float
    win: float
    tie: float
    margin: float
    samples: float


class HandResult(BaseModel):
    hand: str
    combos: float
    equity: float
    win: float
    tie: float
    margin: float
    samples: float


class ParticipantResult(BaseModel):
    equity: float
    win: float
    tie: float
    margin: float
    hands: list[HandResult]
    combos: list[ComboResult]


class EquityResult(BaseModel):
    method: Method
    stop_reason: StopReason
    samples: float
    seed: int
    elapsed_s: float
    participants: list[ParticipantResult]

    @classmethod
    def from_engine(cls, r: EngineResult) -> EquityResult:
        return cls(
            method=r.method,
            stop_reason=r.stop_reason,
            samples=r.samples,
            seed=r.seed,
            elapsed_s=r.elapsed_s,
            participants=[
                ParticipantResult(
                    equity=p.equity,
                    win=p.win,
                    tie=p.tie,
                    margin=p.margin,
                    hands=[HandResult(**h.__dict__) for h in p.hands],
                    combos=[
                        ComboResult(
                            combo=c.name,
                            weight=c.weight,
                            equity=c.equity,
                            win=c.win,
                            tie=c.tie,
                            margin=c.margin,
                            samples=c.samples,
                        )
                        for c in p.combos
                    ],
                )
                for p in r.participants
            ],
        )


class EquityJob(BaseModel):
    id: str
    status: EquityJobStatus
    method: Method
    estimate: EquityEstimate | None = None
    result: EquityResult | None = None
    error: Problem | None = None
    created_at: datetime
    finished_at: datetime | None = None


def result_json(r: EngineResult) -> dict[str, Any]:
    return EquityResult.from_engine(r).model_dump(mode="json")
