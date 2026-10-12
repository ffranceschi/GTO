"""Funções de job executadas nos workers (raia `solve`)."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

from gto_engine.game.builder import build_tree
from gto_engine.io.solution_dir import save_solution_dir, solution_from_result
from gto_engine.solver.dcfr import Progress, solve
from gto_engine.solver.finalize import SolveCancelled

from gto_api.jobs.worker import JobCancelled, WorkerControl

Emit = Callable[[dict[str, Any]], None]


def solve_job(payload: dict[str, Any], ctl: WorkerControl, emit: Emit) -> dict[str, Any]:
    from gto_api.schemas.solves import SolveParams, Spot, TreeConfig

    spot = Spot.model_validate(payload["spot"]).to_engine()
    cfg = TreeConfig.model_validate(payload["tree"]).to_engine()
    params = SolveParams.model_validate(payload["params"]).to_engine()
    tree = build_tree(spot, cfg)

    def on_progress(p: Progress) -> None:
        emit(
            {
                "type": "progress",
                "iteration": p.iteration,
                "exploitability_pct": p.exploitability_pct,
                "exploitability_iteration": p.exploitability_iteration,
                "elapsed_s": round(p.elapsed_s, 3),
                "iterations_per_s": round(p.iterations_per_s, 1),
                "phase": p.phase,
                "finalize_fraction": p.finalize_fraction,
            }
        )

    try:
        r = solve(tree, params, control=ctl, on_progress=on_progress)
    except SolveCancelled as exc:
        raise JobCancelled() from exc
    sol = solution_from_result(tree, spot, cfg, params, r)
    if ctl.cancelled:
        raise JobCancelled()
    directory = Path(payload["solutions_dir"]) / sol.meta.input_hash
    size = save_solution_dir(sol, directory, tree)
    return {
        "status": "stopped" if r.stop_reason == "user_stopped" else "completed",
        "stop_reason": r.stop_reason,
        "iterations": r.iterations,
        "exploitability_pct": r.exploitability_pct,
        "elapsed_s": round(r.elapsed_s, 3),
        "target_reached": r.target_reached,
        "solution_dir": sol.meta.input_hash,
        "size_bytes": size,
    }


def _progress(emit: Emit) -> Callable[[float], None]:
    return lambda f: emit({"type": "progress", "progress": round(float(f), 4)})


def export_job(payload: dict[str, Any], ctl: WorkerControl, emit: Emit) -> dict[str, Any]:
    from gto_engine.io.exchange import Cancelled, export_npz

    target = Path(payload["exports_dir"]) / f"{payload['job_id']}.npz"
    try:
        export_npz(
            Path(payload["solutions_dir"]) / payload["solution_dir"], target, ctl, _progress(emit)
        )
    except Cancelled as exc:
        raise JobCancelled() from exc
    return {"status": "completed", "result_path": target.name, "solve_id": payload["solve_id"]}


def import_job(payload: dict[str, Any], ctl: WorkerControl, emit: Emit) -> dict[str, Any]:
    from dataclasses import asdict

    from gto_engine.io.exchange import Cancelled, import_npz
    from gto_engine.io.solution_dir import dir_size

    source = Path(payload["source"])
    staging = Path(payload["solutions_dir"]) / f"import-{payload['job_id']}"
    try:
        meta = import_npz(source, staging, ctl, _progress(emit))
        name = f"{meta.input_hash}.{payload['job_id'][:8]}"
        final = staging.with_name(name)
        staging.rename(final)
    except Cancelled as exc:
        raise JobCancelled() from exc
    finally:
        source.unlink(missing_ok=True)
    return {
        "status": "completed",
        "solve_id": payload["solve_id"],
        "solution_dir": name,
        "size_bytes": dir_size(final),
        "meta": asdict(meta),
    }


def cleanup_job(payload: dict[str, Any], ctl: WorkerControl, emit: Emit) -> dict[str, Any]:
    import shutil

    candidates: list[list[str]] = payload["candidates"]
    exports: list[str] = payload["expired_exports"]
    total = len(candidates) + len(exports)
    removed: list[str] = []
    emit({"type": "progress", "progress": 0.0})
    for i, (solve_id, solution_dir) in enumerate(candidates):
        if ctl.should_stop():
            break
        shutil.rmtree(Path(payload["solutions_dir"]) / solution_dir, ignore_errors=True)
        removed.append(solve_id)
        emit({"type": "progress", "progress": round((i + 1) / total, 4)})
    for j, name in enumerate(exports):
        if ctl.should_stop():
            break
        (Path(payload["exports_dir"]) / name).unlink(missing_ok=True)
        emit({"type": "progress", "progress": round((len(candidates) + j + 1) / total, 4)})
    return {"status": "completed", "removed": removed}
