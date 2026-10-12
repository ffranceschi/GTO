"""Modelos SQLAlchemy 2 (data-model.md, seção Persistência)."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any, ClassVar

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

SOLVE_STATUSES = (
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
)
ACTIVE_SOLVE_STATUSES = ("queued", "running", "paused", "stopping", "finalizing")
AUX_STATUSES = ("queued", "running", "completed", "failed", "cancelled")


def now_utc() -> datetime:
    return datetime.now(UTC)


def new_id() -> str:
    return str(uuid.uuid4())


class Base(DeclarativeBase):
    type_annotation_map: ClassVar[dict[Any, Any]] = {dict[str, Any]: JSON}


class TreeConfigRow(Base):
    __tablename__ = "tree_configs"
    __table_args__ = (CheckConstraint("length(name) BETWEEN 1 AND 60", name="ck_tree_config_name"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    name: Mapped[str] = mapped_column(String(60), unique=True)
    config_json: Mapped[dict[str, Any]] = mapped_column(JSON)
    is_default: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=now_utc, onupdate=now_utc
    )


class SolveRow(Base):
    __tablename__ = "solves"
    __table_args__ = (
        CheckConstraint(f"status IN {SOLVE_STATUSES!r}", name="ck_solve_status"),
        CheckConstraint("origin IN ('solve', 'import')", name="ck_solve_origin"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    input_hash: Mapped[str] = mapped_column(String(64), index=True)
    status: Mapped[str] = mapped_column(String(16), default="queued")
    origin: Mapped[str] = mapped_column(String(8), default="solve")
    spot_json: Mapped[dict[str, Any]] = mapped_column(JSON)
    tree_config_json: Mapped[dict[str, Any]] = mapped_column(JSON)
    params_json: Mapped[dict[str, Any]] = mapped_column(JSON)
    estimated_bytes: Mapped[int] = mapped_column(Integer, default=0)
    iterations: Mapped[int] = mapped_column(Integer, default=0)
    exploitability_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    stop_reason: Mapped[str | None] = mapped_column(String(16), nullable=True)
    solution_dir: Mapped[str | None] = mapped_column(Text, nullable=True)
    size_bytes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    pinned: Mapped[bool] = mapped_column(Boolean, default=False)
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    error_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    error_detail: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class AuxJobRow(Base):
    __tablename__ = "aux_jobs"
    __table_args__ = (
        CheckConstraint("kind IN ('export', 'import', 'cleanup')", name="ck_aux_kind"),
        CheckConstraint(f"status IN {AUX_STATUSES!r}", name="ck_aux_status"),
        CheckConstraint("progress >= 0 AND progress <= 1", name="ck_aux_progress"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    kind: Mapped[str] = mapped_column(String(8))
    status: Mapped[str] = mapped_column(String(16), default="queued")
    solve_id: Mapped[str | None] = mapped_column(
        ForeignKey("solves.id", ondelete="SET NULL"), nullable=True
    )
    progress: Mapped[float] = mapped_column(Float, default=0.0)
    result_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    error_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    error_detail: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


EQUITY_STATUSES = ("queued", "running", "completed", "cancelled", "failed")


class SavedRangeRow(Base):
    """Range salvo com nome (feature 001, FR-025/026)."""

    __tablename__ = "saved_ranges"
    __table_args__ = (CheckConstraint("length(name) BETWEEN 1 AND 60", name="ck_saved_range_name"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    name: Mapped[str] = mapped_column(String(60), unique=True)
    notation: Mapped[str] = mapped_column(Text)
    combos: Mapped[float] = mapped_column(Float, default=0.0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=now_utc, onupdate=now_utc
    )


class EquityJobRow(Base):
    """Job de equity (feature 001); resultado guardado por 24 h (research R9)."""

    __tablename__ = "equity_jobs"
    __table_args__ = (CheckConstraint(f"status IN {EQUITY_STATUSES!r}", name="ck_equity_status"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    status: Mapped[str] = mapped_column(String(16), default="queued")
    request_json: Mapped[dict[str, Any]] = mapped_column(JSON)
    method: Mapped[str | None] = mapped_column(String(16), nullable=True)
    estimate_json: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    result_json: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    error_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    error_detail: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
