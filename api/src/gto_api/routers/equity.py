"""Router da calculadora de equity (US1): estimativa e jobs na raia `equity`."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Literal

from fastapi import APIRouter, Request, Response
from fastapi.concurrency import run_in_threadpool
from gto_engine.equity.estimate import DEFAULT_RATE, estimate_equity

from gto_api.db.models import EquityJobRow, new_id
from gto_api.errors import ApiError, not_found
from gto_api.jobs.runner import Job, JobStateError, UnknownJobError
from gto_api.schemas.equity import EquityEstimate, EquityJob, EquityRequest
from gto_api.schemas.solves import Problem

router = APIRouter(prefix="/api/v1", tags=["equity"])
PROBLEM = {"model": Problem}
FINAL = ("completed", "cancelled", "failed")


def _estimate(req: EquityRequest, request: Request) -> EquityEstimate:
    rate = getattr(request.app.state.runner, "equity_rate", None) or DEFAULT_RATE
    e = estimate_equity(req.to_engine(), rate)
    return EquityEstimate(
        method=e.method,
        exact_evaluations=e.exact_evaluations,
        estimated_exact_s=round(e.estimated_exact_s, 3),
    )


def _aware(dt: datetime | None) -> datetime | None:
    if dt is None:
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=UTC)


def to_schema(row: EquityJobRow) -> EquityJob:
    error = None
    if row.error_code:
        error = Problem(
            title="Erro", status=500, code=row.error_code, detail=row.error_detail or ""
        )
    return EquityJob(
        id=row.id,
        status=row.status,  # type: ignore[arg-type]
        method=row.method,  # type: ignore[arg-type]
        estimate=EquityEstimate.model_validate(row.estimate_json) if row.estimate_json else None,
        result=row.result_json,  # type: ignore[arg-type]
        error=error,
        created_at=_aware(row.created_at),  # type: ignore[arg-type]
        finished_at=_aware(row.finished_at),
    )


def _get_row(request: Request, job_id: str) -> EquityJobRow:
    with request.app.state.db.session() as s:
        row = s.get(EquityJobRow, job_id)
        if row is None:
            raise not_found("Job de equity")
        return row  # type: ignore[no-any-return]


@router.post(
    "/equity/estimate",
    operation_id="estimateEquity",
    response_model=EquityEstimate,
    responses={422: PROBLEM},
)
def estimate(req: EquityRequest, request: Request) -> EquityEstimate:
    return _estimate(req, request)


@router.post(
    "/equity-jobs",
    operation_id="createEquityJob",
    status_code=202,
    response_model=EquityJob,
    responses={422: PROBLEM},
)
async def create_equity_job(req: EquityRequest, request: Request) -> EquityJob:
    est = await run_in_threadpool(_estimate, req, request)
    payload = {"request": req.model_dump(mode="json"), "method": est.method}
    with request.app.state.db.session() as s:
        row = EquityJobRow(
            id=new_id(),
            status="queued",
            request_json=payload["request"],
            method=est.method,
            estimate_json=est.model_dump(mode="json"),
        )
        s.add(row)
    meta = {"method": est.method, "target_margin": req.target_margin_pp / 100}
    await request.app.state.runner.submit(
        Job(row.id, "equity", "gto_api.jobs.tasks:equity_job", payload, meta), "equity"
    )
    return to_schema(_get_row(request, row.id))


@router.get(
    "/equity-jobs/{job_id}",
    operation_id="getEquityJob",
    response_model=EquityJob,
    responses={404: PROBLEM},
)
def get_equity_job(job_id: str, request: Request) -> EquityJob:
    return to_schema(_get_row(request, job_id))


async def _control(request: Request, job_id: str, command: Literal["stop", "cancel"]) -> Response:
    row = _get_row(request, job_id)
    if row.status in FINAL:
        raise ApiError(409, "conflito", "O cálculo já terminou.")
    try:
        await request.app.state.runner.control(job_id, command)
    except UnknownJobError as exc:
        raise ApiError(409, "conflito", "O cálculo não está ativo neste servidor.") from exc
    except JobStateError as exc:
        raise ApiError(409, "conflito", str(exc)) from exc
    return Response(status_code=202)


@router.delete(
    "/equity-jobs/{job_id}",
    operation_id="cancelEquityJob",
    status_code=202,
    responses={404: PROBLEM, 409: PROBLEM},
)
async def cancel_equity_job(job_id: str, request: Request) -> Response:
    return await _control(request, job_id, "cancel")


@router.post(
    "/equity-jobs/{job_id}/stop",
    operation_id="stopEquityJob",
    status_code=202,
    responses={404: PROBLEM, 409: PROBLEM},
)
async def stop_equity_job(job_id: str, request: Request) -> Response:
    return await _control(request, job_id, "stop")
