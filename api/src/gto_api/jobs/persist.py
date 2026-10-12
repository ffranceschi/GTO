"""Persistência dos eventos de jobs no banco e snapshots de jobs que não estão mais no runner."""

from __future__ import annotations

from typing import Any

from gto_api.db.models import AuxJobRow, EquityJobRow, SolveRow, now_utc
from gto_api.db.session import Database
from gto_api.jobs.runner import Job, JobEvent

SOLVE_FIELDS = ("iterations", "exploitability_pct", "stop_reason", "solution_dir", "size_bytes")


def make_event_hook(db: Database) -> Any:
    def on_event(job: Job, ev: JobEvent) -> None:
        if job.kind == "test":
            return
        t = ev["type"]
        if t not in ("status", "finished", "progress"):
            return
        if job.kind == "equity":
            _persist_equity(db, job, ev)
            return
        with db.session() as s:
            row: SolveRow | AuxJobRow | None
            row = s.get(SolveRow, job.id) if job.kind == "solve" else s.get(AuxJobRow, job.id)
            if row is None:
                return
            if t == "progress":
                if isinstance(row, SolveRow):
                    if ev.get("iteration") is not None:
                        row.iterations = int(ev["iteration"])
                    if ev.get("exploitability_pct") is not None:
                        row.exploitability_pct = float(ev["exploitability_pct"])
                elif ev.get("progress") is not None:
                    row.progress = float(ev["progress"])
                return
            status = ev["status"]
            row.status = status
            if status == "running" and isinstance(row, SolveRow) and row.started_at is None:
                row.started_at = now_utc()
            if t == "finished":
                row.finished_at = now_utc()
                err = ev.get("error") or {}
                row.error_code = err.get("code")
                row.error_detail = err.get("detail")
                if isinstance(row, SolveRow):
                    for f in SOLVE_FIELDS:
                        if f in ev and ev[f] is not None:
                            setattr(row, f, ev[f])
                    if ev.get("exploitability_pct") is not None:
                        row.exploitability_pct = float(ev["exploitability_pct"])
                    if status in ("completed", "stopped"):
                        row.last_used_at = now_utc()
                else:
                    if status == "completed":
                        row.progress = 1.0
                        _apply_aux_result(s, job, ev, row)

    return on_event


def _persist_equity(db: Database, job: Job, ev: JobEvent) -> None:
    """Equity: só mudanças de estado e o resultado final (o progresso fica no WebSocket)."""
    t = ev["type"]
    if t == "progress" or (t == "status" and ev["status"] not in ("queued", "running")):
        return  # "stopping" é transitório; o estado final chega no `finished`
    with db.session() as s:
        row = s.get(EquityJobRow, job.id)
        if row is None:
            return
        row.status = ev["status"]
        if t == "finished":
            row.finished_at = now_utc()
            err = ev.get("error") or {}
            row.error_code = err.get("code")
            row.error_detail = err.get("detail")
            # cancelado não guarda resultado (R6); concluído guarda o completo
            row.result_json = ev.get("_result") if ev["status"] == "completed" else None


def _apply_aux_result(s: Any, job: Job, ev: JobEvent, row: AuxJobRow) -> None:
    """Efeitos de um job auxiliar concluído: uso da solução, solve importado, expiração."""
    if job.kind == "export":
        row.result_path = ev.get("result_path")
        solve = s.get(SolveRow, job.payload["solve_id"])
        if solve is not None:
            solve.last_used_at = now_utc()  # exportar conta como uso (FR-028)
    elif job.kind == "import":
        meta = ev["meta"]
        spot = meta["spot"]
        s.add(
            SolveRow(
                id=job.payload["solve_id"],
                input_hash=meta["input_hash"],
                status="completed",
                origin="import",
                spot_json={
                    "oop_range": {"notation": spot["oop_range"]},
                    "ip_range": {"notation": spot["ip_range"]},
                    "board": spot["board"],
                    "pot": spot["pot"],
                    "effective_stack": spot["effective_stack"],
                },
                tree_config_json=meta["tree_config"],
                params_json=meta["solve_params"],
                iterations=meta["iterations"],
                exploitability_pct=meta["final_exploitability_pct"],
                stop_reason=meta["stop_reason"],
                solution_dir=ev["solution_dir"],
                size_bytes=ev["size_bytes"],
                last_used_at=now_utc(),
                finished_at=now_utc(),
            )
        )
        s.flush()
        row.solve_id = job.payload["solve_id"]
    elif job.kind == "cleanup":
        for solve_id in ev.get("removed", []):
            solve = s.get(SolveRow, solve_id)
            if solve is not None:
                solve.status = "expired"
                solve.solution_dir = None
                solve.size_bytes = None


def make_snapshot_lookup(db: Database) -> Any:
    def lookup(job_id: str) -> tuple[JobEvent, JobEvent | None] | None:
        with db.session() as s:
            solve = s.get(SolveRow, job_id)
            if solve is not None:
                snap: JobEvent = {
                    "type": "snapshot",
                    "job_id": job_id,
                    "job_kind": "solve",
                    "seq": 0,
                    "status": solve.status,
                    "queue_position": None,
                    "iteration": solve.iterations,
                    "exploitability_pct": solve.exploitability_pct,
                    "history": [],
                }
                fin = None
                if solve.status in ("completed", "stopped", "cancelled", "failed", "expired"):
                    fin = {
                        "type": "finished",
                        "job_id": job_id,
                        "job_kind": "solve",
                        "seq": 1,
                        "status": solve.status,
                        "stop_reason": solve.stop_reason,
                        "iterations": solve.iterations,
                        "exploitability_pct": solve.exploitability_pct,
                    }
                return snap, fin
            eq = s.get(EquityJobRow, job_id)
            if eq is not None:
                snap = {
                    "type": "snapshot",
                    "job_id": job_id,
                    "job_kind": "equity",
                    "seq": 0,
                    "status": eq.status,
                    "method": eq.method,
                }
                fin = None
                if eq.status in ("completed", "failed", "cancelled"):
                    fin = {
                        "type": "finished",
                        "job_id": job_id,
                        "job_kind": "equity",
                        "seq": 1,
                        "status": eq.status,
                        "stop_reason": (eq.result_json or {}).get("stop_reason"),
                    }
                return snap, fin
            aux = s.get(AuxJobRow, job_id)
            if aux is not None:
                snap = {
                    "type": "snapshot",
                    "job_id": job_id,
                    "job_kind": aux.kind,
                    "seq": 0,
                    "status": aux.status,
                    "progress": aux.progress,
                    "solve_id": aux.solve_id,
                }
                fin = None
                if aux.status in ("completed", "failed", "cancelled"):
                    fin = {
                        "type": "finished",
                        "job_id": job_id,
                        "job_kind": aux.kind,
                        "seq": 1,
                        "status": aux.status,
                        "solve_id": aux.solve_id,
                    }
                return snap, fin
        return None

    return lookup
