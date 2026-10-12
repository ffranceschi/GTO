"""Schemas dos jobs auxiliares e do uso de disco (US4)."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel

from gto_api.schemas.solves import Problem


class AuxJob(BaseModel):
    id: str
    kind: Literal["export", "import", "cleanup"]
    status: Literal["queued", "running", "completed", "failed", "cancelled"]
    solve_id: str | None = None
    progress: float
    download_url: str | None = None
    file_expires_at: datetime | None = None
    error: Problem | None = None
    created_at: datetime
    finished_at: datetime | None = None


class StorageUsage(BaseModel):
    total_bytes: int
    solutions: int
    pinned: int
    retention_days: int
    expiring_soon: int


class PinRequest(BaseModel):
    pinned: bool
