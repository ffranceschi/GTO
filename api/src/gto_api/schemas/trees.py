"""Schemas de estimativa de árvore e configurações nomeadas (US3)."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, Field

from gto_api.schemas.solves import TreeConfig


class TreeEstimate(BaseModel):
    decision_nodes: int
    chance_nodes: int
    terminal_nodes: int
    estimated_bytes: int
    estimated_solution_bytes: int
    max_bytes: int
    within_limit: bool
    isomorphism_factor: float
    suggestions: list[str] = []


class NamedTreeConfigInput(BaseModel):
    name: Annotated[str, Field(min_length=1, max_length=60)]
    config: TreeConfig
    overwrite: bool = False


class NamedTreeConfig(NamedTreeConfigInput):
    id: str
    is_default: bool
    updated_at: datetime
