"""Router de solves (US1): criação, consulta, controle, exclusão e visão de nós."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Query, Request, Response
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import JSONResponse
from gto_engine.analysis.node_view import node_view
from gto_engine.game.estimate import estimate_tree
from gto_engine.game.hashing import input_hash
from gto_engine.game.tree import InvalidPathError
from sqlalchemy import select

from gto_api.db.models import SolveRow, new_id, now_utc
from gto_api.errors import ApiError, not_found
from gto_api.jobs.runner import Job, JobStateError, UnknownJobError
from gto_api.schemas.solves import (
    NodeView,
    Problem,
    SolutionSummary,
    Solve,
    SolveRequest,
    SolveStatus,
)
from gto_api.storage.solutions import SolutionStore

router = APIRouter(prefix="/api/v1", tags=["solves"])
GIB = 1024**3
FINAL = ("completed", "stopped", "cancelled", "failed", "expired")
WITH_SOLUTION = ("completed", "stopped")
PROBLEM = {"model": Problem}


def _store(request: Request) -> SolutionStore:
    store: SolutionStore | None = getattr(request.app.state, "solution_store", None)
    if store is None:
        store = SolutionStore(request.app.state.settings.solutions_dir)
        request.app.state.solution_store = store
    return store


def _aware(dt: datetime | None) -> datetime | None:
    if dt is None:
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=UTC)


def to_schema(request: Request, row: SolveRow) -> Solve:
    runner = request.app.state.runner
    days = request.app.state.settings.solution_retention_days
    last = _aware(row.last_used_at)
    expires = None
    if row.status in WITH_SOLUTION and not row.pinned and last is not None:
        expires = last + timedelta(days=days)
    error = None
    if row.error_code:
        error = Problem(
            title="Erro", status=500, code=row.error_code, detail=row.error_detail or ""
        )
    return Solve(
        id=row.id,
        status=row.status,  # type: ignore[arg-type]
        origin=row.origin,  # type: ignore[arg-type]
        input_hash=row.input_hash,
        spot=row.spot_json,
        tree=row.tree_config_json,
        params=row.params_json,
        estimated_bytes=row.estimated_bytes,
        iterations=row.iterations,
        exploitability_pct=row.exploitability_pct,
        stop_reason=row.stop_reason,  # type: ignore[arg-type]
        queue_position=runner.queue_position(row.id) if runner.has_job(row.id) else None,
        pinned=row.pinned,
        size_bytes=row.size_bytes,
        last_used_at=last,
        expires_at=expires,
        error=error,
        created_at=_aware(row.created_at),  # type: ignore[arg-type]
        started_at=_aware(row.started_at),
        finished_at=_aware(row.finished_at),
    )


def _get_row(request: Request, solve_id: str) -> SolveRow:
    with request.app.state.db.session() as s:
        row = s.get(SolveRow, solve_id)
        if row is None:
            raise not_found("Solve")
        return row  # type: ignore[no-any-return]


@router.post(
    "/solves",
    operation_id="createSolve",
    status_code=202,
    response_model=Solve,
    responses={
        200: {"model": Solve, "description": "Solução existente reaproveitada"},
        422: PROBLEM,
    },
)
async def create_solve(req: SolveRequest, request: Request) -> Any:
    settings = request.app.state.settings
    spot = req.spot.to_engine()
    cfg = req.tree.to_engine()
    params = req.params.to_engine()
    est = estimate_tree(spot, cfg)
    if est.estimated_bytes > settings.max_solve_memory_bytes:
        raise ApiError(
            422,
            "arvore_grande_demais",
            f"A árvore precisa de cerca de {est.estimated_bytes / GIB:.2f} GiB de memória e o "
            f"limite é {settings.max_solve_memory_bytes / GIB:.2f} GiB. Reduza os tamanhos de "
            "aposta, o limite de raises ou os ranges.",
        )
    h = input_hash(spot, cfg, params)
    db = request.app.state.db
    if not req.force:
        with db.session() as s:
            existing = s.scalars(
                select(SolveRow)
                .where(SolveRow.input_hash == h, SolveRow.status == "completed")
                .order_by(SolveRow.created_at.desc())
            ).first()
            if (
                existing is not None
                and existing.solution_dir
                and _store(request).path(existing.solution_dir).exists()
            ):
                return JSONResponse(
                    to_schema(request, existing).model_dump(mode="json"), status_code=200
                )
    payload = {
        "spot": req.spot.model_dump(mode="json"),
        "tree": req.tree.model_dump(mode="json"),
        "params": req.params.model_dump(mode="json"),
        "solutions_dir": str(settings.solutions_dir),
    }
    with db.session() as s:
        row = SolveRow(
            id=new_id(),
            input_hash=h,
            status="queued",
            origin="solve",
            spot_json=payload["spot"],
            tree_config_json=payload["tree"],
            params_json=payload["params"],
            estimated_bytes=est.estimated_bytes,
        )
        s.add(row)
    meta = {
        "target_exploitability_pct": params.target_exploitability_pct,
        "time_limit_s": params.time_limit_s,
    }
    await request.app.state.runner.submit(
        Job(row.id, "solve", "gto_api.jobs.tasks:solve_job", payload, meta), "solve"
    )
    return to_schema(request, _get_row(request, row.id))


@router.get("/solves", operation_id="listSolves", response_model=list[Solve])
def list_solves(
    request: Request, status: Annotated[SolveStatus | None, Query()] = None
) -> list[Solve]:
    with request.app.state.db.session() as s:
        q = select(SolveRow).order_by(SolveRow.created_at.desc())
        if status:
            q = q.where(SolveRow.status == status)
        return [to_schema(request, r) for r in s.scalars(q)]


@router.get(
    "/solves/{solve_id}", operation_id="getSolve", response_model=Solve, responses={404: PROBLEM}
)
def get_solve(solve_id: str, request: Request) -> Solve:
    return to_schema(request, _get_row(request, solve_id))


async def _control(
    request: Request, solve_id: str, command: Literal["pause", "resume", "stop", "cancel"]
) -> Response:
    row = _get_row(request, solve_id)
    if command == "stop" and row.status in ("stopped", "stopping", "finalizing"):
        return Response(status_code=202)  # idempotente
    try:
        await request.app.state.runner.control(solve_id, command)
    except UnknownJobError as exc:
        raise ApiError(409, "conflito", "O solve não está ativo neste servidor.") from exc
    except JobStateError as exc:
        raise ApiError(409, "conflito", str(exc)) from exc
    return Response(status_code=202)


@router.post(
    "/solves/{solve_id}/pause",
    operation_id="pauseSolve",
    status_code=202,
    responses={404: PROBLEM, 409: PROBLEM},
)
async def pause_solve(solve_id: str, request: Request) -> Response:
    return await _control(request, solve_id, "pause")


@router.post(
    "/solves/{solve_id}/resume",
    operation_id="resumeSolve",
    status_code=202,
    responses={404: PROBLEM, 409: PROBLEM},
)
async def resume_solve(solve_id: str, request: Request) -> Response:
    return await _control(request, solve_id, "resume")


@router.post(
    "/solves/{solve_id}/stop",
    operation_id="stopSolve",
    status_code=202,
    responses={404: PROBLEM, 409: PROBLEM},
)
async def stop_solve(solve_id: str, request: Request) -> Response:
    return await _control(request, solve_id, "stop")


@router.delete(
    "/solves/{solve_id}",
    operation_id="cancelSolve",
    status_code=204,
    responses={202: {"description": "Cancelamento solicitado"}, 404: PROBLEM},
)
async def cancel_solve(solve_id: str, request: Request) -> Response:
    row = _get_row(request, solve_id)
    if row.status not in FINAL:
        await _control(request, solve_id, "cancel")
        return Response(status_code=202)
    db = request.app.state.db
    with db.session() as s:
        r = s.get(SolveRow, solve_id)
        if r is not None:
            others = 0
            if r.solution_dir:
                others = len(
                    list(
                        s.scalars(
                            select(SolveRow.id).where(
                                SolveRow.solution_dir == r.solution_dir, SolveRow.id != solve_id
                            )
                        )
                    )
                )
            if r.solution_dir and others == 0:
                _store(request).delete(r.solution_dir)
            s.delete(r)
    return Response(status_code=204)


@router.get(
    "/solves/{solve_id}/nodes",
    operation_id="getNode",
    response_model=NodeView,
    responses={404: PROBLEM, 409: PROBLEM, 422: PROBLEM},
)
async def get_node(solve_id: str, request: Request, path: Annotated[str, Query()] = "") -> NodeView:
    row = _get_row(request, solve_id)
    if row.status not in WITH_SOLUTION or not row.solution_dir:
        raise ApiError(
            409, "solucao_indisponivel", "A solução ainda não está disponível para este solve."
        )
    steps = [p for p in path.split("/") if p]
    store = _store(request)

    def compute() -> NodeView:
        tree, sol = store.open(row.solution_dir)  # type: ignore[arg-type]
        v = node_view(tree, sol, steps)
        data = v.__dict__ | {
            "actions": [a.__dict__ | {"amount_bb": a.amount_bb} for a in v.actions],
            "hands": [h.__dict__ for h in v.hands],
            "combos": [c.__dict__ for c in v.combos],
            "ranges": [r.__dict__ for r in v.ranges],
            "terminal": {
                "kind": v.terminal,
                "results": [
                    {"player": r.player, "combos": [c.__dict__ for c in r.combos]}
                    for r in (v.terminal_results or [])
                ],
            }
            if v.terminal
            else None,
            "solution": SolutionSummary(
                exploitability_pct=row.exploitability_pct,
                iterations=row.iterations,
                stop_reason=row.stop_reason,
            ),
        }
        return NodeView.model_validate(data)

    try:
        view = await run_in_threadpool(compute)
    except InvalidPathError:
        raise
    if store.should_touch(solve_id):
        with request.app.state.db.session() as s:
            r = s.get(SolveRow, solve_id)
            if r is not None:
                r.last_used_at = now_utc()
    return view
