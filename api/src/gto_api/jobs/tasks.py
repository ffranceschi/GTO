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
    size = save_solution_dir(sol, directory)
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
