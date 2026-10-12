"""T005 — raia `equity` no runner: independente das raias solve e aux; FIFO; cancelamento ≤ 1 s."""

from __future__ import annotations

import asyncio
import time

from gto_api.jobs.local_process import LaneJobRunner
from gto_api.jobs.runner import Job

LOOP = "tests.jobs_for_tests:loop_job"


async def wait(r: LaneJobRunner, jid: str, status: str, timeout: float = 5) -> float:
    t0 = time.monotonic()
    while r.status(jid) != status:
        assert time.monotonic() - t0 < timeout, (jid, r.status(jid))
        await asyncio.sleep(0.01)
    return time.monotonic() - t0


def test_raia_equity_independente() -> None:
    async def body() -> None:
        r = LaneJobRunner(backend="process", warm=False)
        await r.start()
        try:
            await r.submit(Job("s", "test", LOOP), "solve")
            await r.submit(Job("a", "test", LOOP), "aux")
            await r.submit(Job("e1", "test", LOOP, {"blocks": 3}), "equity")
            await r.submit(Job("e2", "test", LOOP), "equity")
            await wait(r, "e1", "completed")
            assert r.status("s") == "running" and r.status("a") == "running"
            await wait(r, "e2", "running")
            t = time.monotonic()
            await r.control("e2", "cancel")
            await wait(r, "e2", "cancelled")
            assert time.monotonic() - t < 1.0
            await r.submit(Job("e3", "test", LOOP), "equity")
            await r.submit(Job("e4", "test", LOOP), "equity")
            assert r.queue_position("e4") == 1
            for j in ("s", "a", "e3", "e4"):
                await r.control(j, "cancel")
        finally:
            await r.shutdown()

    asyncio.run(body())
