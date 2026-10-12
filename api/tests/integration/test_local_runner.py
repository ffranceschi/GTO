"""T036 — runner local (R4, FR-027): raias, fila, controle < 1 s, watchdog e reconciliação."""

from __future__ import annotations

import asyncio
import time
from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import Any

import pytest

from gto_api.db.models import AuxJobRow, SolveRow
from gto_api.db.session import Database
from gto_api.jobs.local_process import LaneJobRunner
from gto_api.jobs.runner import Job, JobStateError

LOOP = "tests.jobs_for_tests:loop_job"
HANG = "tests.jobs_for_tests:hang_job"


def run(coro_fn: Callable[[LaneJobRunner], Awaitable[Any]], **kw: Any) -> Any:
    async def main() -> Any:
        r = LaneJobRunner(backend=kw.pop("backend", "process"), warm=False, **kw)
        await r.start()
        try:
            return await coro_fn(r)
        finally:
            await r.shutdown()

    return asyncio.run(main())


async def wait_status(r: LaneJobRunner, job_id: str, status: str, timeout: float = 5.0) -> float:
    t0 = time.monotonic()
    while r.status(job_id) != status:
        if time.monotonic() - t0 > timeout:
            raise AssertionError(f"{job_id}: esperado {status}, está {r.status(job_id)}")
        await asyncio.sleep(0.01)
    return time.monotonic() - t0


def job(i: str, func: str = LOOP, **payload: Any) -> Job:
    return Job(i, "test", func, payload)


@pytest.mark.parametrize("backend", ["process", "thread"])
def test_fila_fifo_e_posicoes(backend: str) -> None:
    async def body(r: LaneJobRunner) -> None:
        await r.submit(job("a"), "solve")
        await r.submit(job("b"), "solve")
        await r.submit(job("c"), "solve")
        await wait_status(r, "a", "running")
        assert r.queue_position("b") == 1 and r.queue_position("c") == 2
        await r.control("b", "cancel")
        assert r.status("b") == "cancelled" and r.queue_position("c") == 1
        await r.control("a", "stop")
        await wait_status(r, "a", "stopped")
        await wait_status(r, "c", "running")

    run(body, backend=backend)


def test_pausado_mantem_a_raia_e_aux_roda_em_paralelo() -> None:
    async def body(r: LaneJobRunner) -> None:
        await r.submit(job("a"), "solve")
        await wait_status(r, "a", "running")
        await r.control("a", "pause")
        assert await wait_status(r, "a", "paused") < 1.0
        await r.submit(job("b"), "solve")
        await r.submit(job("x", blocks=3), "aux")
        await wait_status(r, "x", "completed")
        await asyncio.sleep(0.3)
        assert r.status("b") == "queued" and r.queue_position("b") == 1
        await r.control("a", "resume")
        assert await wait_status(r, "a", "running") < 1.0
        await r.control("a", "cancel")
        assert await wait_status(r, "a", "cancelled") < 1.0
        await wait_status(r, "b", "running")

    run(body)


def test_comandos_em_estado_incompativel() -> None:
    async def body(r: LaneJobRunner) -> None:
        await r.submit(job("a", blocks=2), "solve")
        await r.submit(job("b"), "solve")
        with pytest.raises(JobStateError):
            await r.control("b", "pause")
        await wait_status(r, "a", "completed")
        with pytest.raises(JobStateError):
            await r.control("a", "stop")

    run(body)


def test_worker_sem_resposta_e_encerrado() -> None:
    async def body(r: LaneJobRunner) -> None:
        await r.submit(job("h", HANG, seconds=30), "solve")
        await wait_status(r, "h", "running")
        await r.control("h", "stop")
        await wait_status(r, "h", "failed", timeout=4)
        assert r.snapshot("h")["status"] == "failed"
        # a raia volta a funcionar com um worker novo
        await r.submit(job("n", blocks=2), "solve")
        await wait_status(r, "n", "completed", timeout=10)

    run(body, command_timeout_s=1.0)


def test_eventos_snapshot_seq_e_finished() -> None:
    async def body(r: LaneJobRunner) -> list[dict[str, Any]]:
        await r.submit(job("a", blocks=12), "solve")
        msgs = [m async for m in r.events("a")]
        return msgs

    msgs = run(body)
    assert msgs[0]["type"] == "snapshot"
    assert msgs[-1]["type"] == "finished" and msgs[-1]["status"] == "completed"
    seqs = [m["seq"] for m in msgs[1:]]
    assert seqs == sorted(seqs) and len(set(seqs)) == len(seqs)
    assert all({"type", "job_id", "job_kind", "seq"} <= m.keys() for m in msgs)


def test_reconciliacao_ao_reiniciar(tmp_path: Path) -> None:
    db = Database(f"sqlite:///{tmp_path / 'x.sqlite3'}")
    db.create_all()
    with db.session() as s:
        for st in ("queued", "running", "paused", "stopping", "finalizing", "completed"):
            s.add(
                SolveRow(
                    id=st,
                    input_hash="0" * 64,
                    status=st,
                    spot_json={},
                    tree_config_json={},
                    params_json={},
                )
            )
        s.add(AuxJobRow(id="aux", kind="export", status="running"))
    assert db.reconcile_after_restart() == 6
    with db.session() as s:
        rows = {r.id: r for r in s.query(SolveRow)}
        assert rows["completed"].status == "completed"
        for st in ("queued", "running", "paused", "stopping", "finalizing"):
            assert rows[st].status == "failed" and rows[st].error_code == "servidor_reiniciado"
        assert s.get(AuxJobRow, "aux").status == "failed"  # type: ignore[union-attr]
