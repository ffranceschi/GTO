"""CRUD de ranges salvos com nome (feature 001, US4 — FR-025 a FR-027, research R7)."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated, Any

from fastapi import APIRouter, Request, Response
from gto_engine.ranges import format_range, parse_range
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from gto_api.db.models import SavedRangeRow, new_id, now_utc
from gto_api.errors import ApiError, not_found
from gto_api.schemas.solves import Problem

router = APIRouter(prefix="/api/v1", tags=["saved-ranges"])
PROBLEM: dict[int | str, dict[str, Any]] = {
    404: {"model": Problem},
    409: {"model": Problem},
    422: {"model": Problem},
}


class SavedRangeInput(BaseModel):
    name: Annotated[str, Field(min_length=1, max_length=60)]
    notation: str
    overwrite: bool = False


class SavedRange(BaseModel):
    id: str
    name: str
    notation: str = Field(description="Notação canônica")
    combos: float
    updated_at: datetime


def _schema(r: SavedRangeRow) -> SavedRange:
    updated = r.updated_at if r.updated_at.tzinfo else r.updated_at.replace(tzinfo=UTC)
    return SavedRange(
        id=r.id, name=r.name, notation=r.notation, combos=r.combos, updated_at=updated
    )


def _normalize(body: SavedRangeInput) -> tuple[str, str, float]:
    """Nome sem espaços nas pontas; notação validada e convertida para a canônica (ida e volta)."""
    name = body.name.strip()
    if not name:
        raise ApiError(422, "nome_invalido", "O nome deve ter de 1 a 60 caracteres.")
    r = parse_range(body.notation)  # RangeNotationError → 422 range_invalido
    combos = r.combo_count()
    if combos <= 0:
        raise ApiError(422, "range_vazio", "O range está vazio: não há o que salvar.")
    return name, format_range(r), float(combos)


def _name_taken(name: str) -> ApiError:
    return ApiError(
        409, "nome_em_uso", f"Já existe um range chamado '{name}'. Confirme para sobrescrever."
    )


@router.get("/saved-ranges", operation_id="listSavedRanges", response_model=list[SavedRange])
def list_ranges(request: Request) -> list[SavedRange]:
    with request.app.state.db.session() as s:
        return [_schema(r) for r in s.scalars(select(SavedRangeRow).order_by(SavedRangeRow.name))]


@router.post(
    "/saved-ranges",
    operation_id="createSavedRange",
    status_code=201,
    response_model=SavedRange,
    responses=PROBLEM,
)
def create_range(body: SavedRangeInput, request: Request) -> SavedRange:
    name, notation, combos = _normalize(body)
    try:
        with request.app.state.db.session() as s:
            existing = s.scalars(select(SavedRangeRow).where(SavedRangeRow.name == name)).first()
            if existing is not None:
                if not body.overwrite:
                    raise _name_taken(name)
                existing.notation = notation
                existing.combos = combos
                existing.updated_at = now_utc()
                return _schema(existing)
            row = SavedRangeRow(id=new_id(), name=name, notation=notation, combos=combos)
            s.add(row)
            s.flush()
            return _schema(row)
    except IntegrityError as exc:  # outro pedido criou o mesmo nome entre a consulta e o insert
        raise _name_taken(name) from exc


@router.put(
    "/saved-ranges/{range_id}",
    operation_id="updateSavedRange",
    response_model=SavedRange,
    responses=PROBLEM,
)
def update_range(range_id: str, body: SavedRangeInput, request: Request) -> SavedRange:
    name, notation, combos = _normalize(body)
    try:
        with request.app.state.db.session() as s:
            row = s.get(SavedRangeRow, range_id)
            if row is None:
                raise not_found("Range salvo")
            other = s.scalars(
                select(SavedRangeRow).where(
                    SavedRangeRow.name == name, SavedRangeRow.id != range_id
                )
            ).first()
            if other is not None:
                raise ApiError(409, "nome_em_uso", f"Já existe um range chamado '{name}'.")
            row.name = name
            row.notation = notation
            row.combos = combos
            row.updated_at = now_utc()
            return _schema(row)
    except IntegrityError as exc:
        raise ApiError(409, "nome_em_uso", f"Já existe um range chamado '{name}'.") from exc


@router.delete(
    "/saved-ranges/{range_id}", operation_id="deleteSavedRange", status_code=204, responses=PROBLEM
)
def delete_range(range_id: str, request: Request) -> Response:
    with request.app.state.db.session() as s:
        row = s.get(SavedRangeRow, range_id)
        if row is None:
            raise not_found("Range salvo")
        s.delete(row)
    return Response(status_code=204)
