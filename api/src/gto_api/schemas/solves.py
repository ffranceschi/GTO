"""Schemas Pydantic v2 espelhando contracts/openapi.yaml (US1)."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Any, Literal

from gto_engine.cards import N_COMBOS, parse_card
from gto_engine.game.config import TreeConfig as EngineTreeConfig
from gto_engine.game.tree import Spot as EngineSpot
from gto_engine.ranges import Range, parse_range
from gto_engine.solver.params import SolveParams as EngineParams
from pydantic import BaseModel, ConfigDict, Field

Card = Annotated[str, Field(pattern=r"^[AKQJT2-9][shdc]$")]
Size = Annotated[float, Field(gt=0, le=10)]


class Problem(BaseModel):
    type: str = "about:blank"
    title: str
    status: int
    code: str
    detail: str
    errors: list[dict[str, str]] | None = None


class NotationRange(BaseModel):
    model_config = ConfigDict(title="NotationRange")
    notation: str


class WeightsRange(BaseModel):
    model_config = ConfigDict(title="WeightsRange")
    weights: Annotated[
        list[Annotated[float, Field(ge=0, le=1)]], Field(min_length=N_COMBOS, max_length=N_COMBOS)
    ]


RangeInput = NotationRange | WeightsRange


def to_range(r: NotationRange | WeightsRange) -> Range:
    if isinstance(r, NotationRange):
        return parse_range(r.notation)
    return Range(r.weights)


class Spot(BaseModel):
    oop_range: RangeInput
    ip_range: RangeInput
    board: Annotated[list[Card], Field(min_length=3, max_length=5)]
    pot: Annotated[float, Field(gt=0, le=10_000)]
    effective_stack: Annotated[float, Field(ge=0, le=10_000)]

    def to_engine(self) -> EngineSpot:
        return EngineSpot(
            to_range(self.oop_range),
            to_range(self.ip_range),
            tuple(parse_card(c) for c in self.board),
            self.pot,
            self.effective_stack,
        )


class SizesByPosition(BaseModel):
    oop: Annotated[list[Size], Field(max_length=5)] = []
    ip: Annotated[list[Size], Field(max_length=5)] = []


Street = Literal["flop", "turn", "river"]


class TreeConfig(BaseModel):
    bet_sizes: dict[Street, SizesByPosition]
    raise_sizes: dict[Street, SizesByPosition]
    max_raises_per_street: Annotated[int, Field(ge=0, le=6)] = 3
    allin_threshold: Annotated[float, Field(gt=0, le=1)] = 0.67
    add_allin_action: bool = False
    allow_donk: bool = False

    def to_engine(self, name: str | None = None) -> EngineTreeConfig:
        return EngineTreeConfig.from_dict(self.model_dump(), name=name)


class SolveParams(BaseModel):
    algorithm: Literal["dcfr", "cfr_plus", "linear_cfr"] = "dcfr"
    target_exploitability_pct: Annotated[float, Field(gt=0, le=100)] = 0.5
    time_limit_s: Annotated[
        float | None,
        Field(
            gt=0,
            le=86_400,
            description="Se omitido: river 60, turn 120, flop 900 (por street do board)",
        ),
    ] = None
    max_iterations: Annotated[int | None, Field(ge=1)] = None
    seed: Annotated[int, Field(ge=0)] = 0

    def to_engine(self) -> EngineParams:
        return EngineParams(
            algorithm=self.algorithm,
            target_exploitability_pct=self.target_exploitability_pct,
            time_limit_s=self.time_limit_s,
            max_iterations=self.max_iterations,
            seed=self.seed,
        )


class SpotWithTree(BaseModel):
    spot: Spot
    tree: TreeConfig


class SolveRequest(SpotWithTree):
    params: SolveParams = SolveParams()
    force: bool = Field(False, description="Resolver mesmo se houver solução com o mesmo hash")


SolveStatus = Literal[
    "queued",
    "running",
    "paused",
    "stopping",
    "finalizing",
    "completed",
    "stopped",
    "cancelled",
    "failed",
    "expired",
]


class Solve(BaseModel):
    id: str
    status: SolveStatus
    origin: Literal["solve", "import"]
    input_hash: str
    spot: dict[str, Any] | None = None
    tree: dict[str, Any] | None = None
    params: dict[str, Any] | None = None
    estimated_bytes: int | None = None
    iterations: int
    exploitability_pct: float | None = None
    stop_reason: Literal["target_reached", "time_limit", "user_stopped"] | None = None
    queue_position: int | None = None
    pinned: bool = False
    size_bytes: int | None = None
    last_used_at: datetime | None = None
    expires_at: datetime | None = None
    error: Problem | None = None
    created_at: datetime
    started_at: datetime | None = None
    finished_at: datetime | None = None


class ActionView(BaseModel):
    id: str
    kind: Literal["check", "bet", "call", "raise", "fold", "allin"]
    label: str
    amount_bb: float
    pot_fraction: float | None = None
    aggregate_frequency: float
    combos: float


class HandView(BaseModel):
    hand: str
    combos: float
    frequencies: dict[str, float]
    ev_bb: float
    equity: float


class ComboView(BaseModel):
    combo: str
    reach_weight: float
    frequencies: dict[str, float]
    ev_bb: float
    equity: float


class RangeAtNode(BaseModel):
    player: Literal["oop", "ip"]
    combos: float
    weights: list[float]


class Terminal(BaseModel):
    kind: Literal["fold", "showdown"]


class SolutionSummary(BaseModel):
    exploitability_pct: float | None
    iterations: int
    stop_reason: str | None


class NodeView(BaseModel):
    path: list[str]
    breadcrumb: list[str] = []
    kind: Literal["decision", "chance", "terminal"]
    player: Literal["oop", "ip"] | None = None
    pot: float
    stacks: dict[str, float]
    actions: list[ActionView] = []
    hands: list[HandView] = []
    combos: list[ComboView] = []
    ranges: list[RangeAtNode]
    next_cards: list[str] = []
    terminal: Terminal | None = None
    solution: SolutionSummary | None = None
