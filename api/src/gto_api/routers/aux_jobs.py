"""Exportação, importação, jobs auxiliares e uso de disco (US4, FR-024/025/028–030)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Request, Response, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy import select

from gto_api.db.models import AuxJobRow, SolveRow, new_id, now_utc
from gto_api.errors import ApiError, fmt_num, not_found
from gto_api.jobs.runner import Job, JobStateError, UnknownJobError
from gto_api.schemas.aux import AuxJob, StorageUsage
from gto_api.schemas.solves import Problem

router = APIRouter(prefix="/api/v1", tags=["solutions"])
EXPORT_TTL = timedelta(hours=24)
UPLOAD_CHUNK = 1024 * 1024
PROBLEM: dict[int | str, dict[str, Any]] = {
    404: {"model": Problem},
    409: {"model": Problem},
    410: {"model": Problem},
    413: {"model": Problem},
}


def _aware(dt: datetime | None) -> datetime | None:
    return None if dt is None else (dt if dt.tzinfo else dt.replace(tzinfo=UTC))


def aux_schema(r: AuxJobRow) -> AuxJob:
    finished = _aware(r.finished_at)
    url = expires = None
    if r.kind == "export" and r.status == "completed" and finished is not None:
        expires = finished + EXPORT_TTL
        url = f"/api/v1/aux-jobs/{r.id}/file"
    err = (
        Problem(title="Erro", status=422, code=r.error_code, detail=r.error_detail or "")
        if r.error_code
        else None
    )
    return AuxJob(
        id=r.id,
        kind=r.kind,  # type: ignore[arg-type]
        status=r.status,  # type: ignore[arg-type]
        solve_id=r.solve_id,
        progress=r.progress,
        download_url=url,
        file_expires_at=expires,
        error=err,
        created_at=_aware(r.created_at) or now_utc(),
        finished_at=finished,
    )


def _get(request: Request, job_id: str) -> AuxJobRow:
    with request.app.state.db.session() as s:
        row = s.get(AuxJobRow, job_id)
        if row is None:
            raise not_found("Job")
        return row  # type: ignore[no-any-return]


async def _submit(request: Request, row: AuxJobRow, func: str, payload: dict[str, Any]) -> AuxJob:
    with request.app.state.db.session() as s:
        s.add(row)
    meta = {"solve_id": row.solve_id} if row.solve_id else {}
    await request.app.state.runner.submit(Job(row.id, row.kind, func, payload, meta), "aux")  # type: ignore[arg-type]
    return aux_schema(_get(request, row.id))


@router.post(
    "/solves/{solve_id}/exports",
    operation_id="createExport",
    status_code=202,
    response_model=AuxJob,
    responses=PROBLEM,
)
async def create_export(solve_id: str, request: Request) -> AuxJob:
    st = request.app.state.settings
    with request.app.state.db.session() as s:
        solve = s.get(SolveRow, solve_id)
        if solve is None:
            raise not_found("Solve")
        if solve.status not in ("completed", "stopped") or not solve.solution_dir:
            raise ApiError(
                409,
                "solucao_indisponivel",
                "Só soluções concluídas ou paradas podem ser exportadas.",
            )
        solution_dir = solve.solution_dir
    row = AuxJobRow(id=new_id(), kind="export", status="queued", solve_id=solve_id, progress=0.0)
    payload = {
        "job_id": row.id,
        "solve_id": solve_id,
        "solution_dir": solution_dir,
        "solutions_dir": str(st.solutions_dir),
        "exports_dir": str(st.exports_dir),
    }
    return await _submit(request, row, "gto_api.jobs.tasks:export_job", payload)


@router.post(
    "/solutions/import",
    operation_id="importSolution",
    status_code=202,
    response_model=AuxJob,
    responses=PROBLEM,
)
async def import_solution(file: UploadFile, request: Request) -> AuxJob:
    st = request.app.state.settings
    job_id = new_id()
    dest = Path(st.imports_dir) / f"{job_id}.npz"
    size = 0
    try:
        with open(dest, "wb") as out:
            while chunk := await file.read(UPLOAD_CHUNK):
                size += len(chunk)
                if size > st.max_import_bytes:
                    raise ApiError(
                        413,
                        "arquivo_grande_demais",
                        "O arquivo passa do limite de "
                        f"{fmt_num(st.max_import_bytes / 1024**3)} GiB "
                        "para importação.",
                    )
                out.write(chunk)
    except ApiError:
        dest.unlink(missing_ok=True)
        raise
    row = AuxJobRow(id=job_id, kind="import", status="queued", progress=0.0)
    payload = {
        "job_id": job_id,
        "source": str(dest),
        "solutions_dir": str(st.solutions_dir),
        "solve_id": new_id(),
    }
    return await _submit(request, row, "gto_api.jobs.tasks:import_job", payload)


@router.get(
    "/aux-jobs/{job_id}", operation_id="getAuxJob", response_model=AuxJob, responses=PROBLEM
)
def get_aux_job(job_id: str, request: Request) -> AuxJob:
    return aux_schema(_get(request, job_id))


@router.delete(
    "/aux-jobs/{job_id}", operation_id="cancelAuxJob", status_code=202, responses=PROBLEM
)
async def cancel_aux_job(job_id: str, request: Request) -> Response:
    _get(request, job_id)
    try:
        await request.app.state.runner.control(job_id, "cancel")
    except (UnknownJobError, JobStateError) as exc:
        raise ApiError(409, "conflito", "O job já terminou.") from exc
    return Response(status_code=202)


@router.get(
    "/aux-jobs/{job_id}/file",
    operation_id="downloadExport",
    response_class=FileResponse,
    responses={200: {"content": {"application/octet-stream": {}}}, **PROBLEM},
)
def download_export(job_id: str, request: Request) -> FileResponse:
    row = _get(request, job_id)
    if row.kind != "export" or row.status != "completed" or not row.result_path:
        raise ApiError(409, "arquivo_indisponivel", "A exportação ainda não terminou.")
    path = Path(request.app.state.settings.exports_dir) / row.result_path
    finished = _aware(row.finished_at)
    if finished is None or now_utc() - finished > EXPORT_TTL or not path.exists():
        raise ApiError(
            410, "arquivo_expirado", "O arquivo exportado expirou (24 h). Exporte de novo."
        )
    return FileResponse(
        path, media_type="application/octet-stream", filename=f"solucao-{row.solve_id}.npz"
    )


@router.get("/storage", operation_id="getStorageUsage", response_model=StorageUsage)
def storage(request: Request) -> StorageUsage:
    days = request.app.state.settings.solution_retention_days
    now = now_utc()
    total = n = pinned = soon = 0
    with request.app.state.db.session() as s:
        for r in s.scalars(select(SolveRow).where(SolveRow.status.in_(("completed", "stopped")))):
            n += 1
            total += r.size_bytes or 0
            if r.pinned:
                pinned += 1
            elif r.last_used_at is not None:
                left = _aware(r.last_used_at) + timedelta(days=days) - now  # type: ignore[operator]
                if left <= timedelta(days=7):
                    soon += 1
    return StorageUsage(
        total_bytes=total, solutions=n, pinned=pinned, retention_days=int(days), expiring_soon=soon
    )


async def schedule_cleanup(app: Any) -> str:
    """Escolhe as soluções expiradas e as exportações vencidas e cria o job `cleanup` (R14)."""
    st = app.state.settings
    now = now_utc()
    cutoff = now - timedelta(days=st.solution_retention_days)
    with app.state.db.session() as s:
        exporting = set(
            s.scalars(
                select(AuxJobRow.solve_id).where(
                    AuxJobRow.kind == "export", AuxJobRow.status.in_(("queued", "running"))
                )
            )
        )
        with_solution = list(
            s.scalars(
                select(SolveRow).where(
                    SolveRow.status.in_(("completed", "stopped")),
                    SolveRow.solution_dir.is_not(None),
                )
            )
        )
        keep_dirs = set()
        candidates: list[list[str]] = []
        for r in with_solution:
            last = _aware(r.last_used_at) or _aware(r.finished_at) or now
            expired = not r.pinned and r.id not in exporting and last < cutoff
            if expired:
                candidates.append([r.id, str(r.solution_dir)])
            else:
                keep_dirs.add(r.solution_dir)
        candidates = [c for c in candidates if c[1] not in keep_dirs]
        old_exports = [
            r.result_path
            for r in s.scalars(
                select(AuxJobRow).where(
                    AuxJobRow.kind == "export",
                    AuxJobRow.status == "completed",
                    AuxJobRow.result_path.is_not(None),
                )
            )
            if _aware(r.finished_at) is not None and now - _aware(r.finished_at) > EXPORT_TTL  # type: ignore[operator]
        ]
        row = AuxJobRow(id=new_id(), kind="cleanup", status="queued", progress=0.0)
        s.add(row)
        job_id = row.id
    store = getattr(app.state, "solution_store", None)
    if store is not None:
        for _, d in candidates:
            store.forget(d)
    payload = {
        "candidates": candidates,
        "expired_exports": old_exports,
        "solutions_dir": str(st.solutions_dir),
        "exports_dir": str(st.exports_dir),
    }
    await app.state.runner.submit(
        Job(job_id, "cleanup", "gto_api.jobs.tasks:cleanup_job", payload), "aux"
    )
    return job_id
