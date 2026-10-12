"""Jobs de teste do runner (executados no worker)."""

from __future__ import annotations

import time
from collections.abc import Callable
from typing import Any

from gto_api.jobs.worker import JobCancelled, WorkerControl


def loop_job(
    payload: dict[str, Any], ctl: WorkerControl, emit: Callable[[dict[str, Any]], None]
) -> dict[str, Any]:
    blocks = int(payload.get("blocks", 10_000))
    for i in range(blocks):
        ctl.wait_if_paused()
        if ctl.cancelled:
            raise JobCancelled()
        if ctl.should_stop():
            return {"status": "stopped", "stop_reason": "user_stopped", "iterations": i}
        time.sleep(float(payload.get("block_s", 0.05)))
        emit({"type": "progress", "iteration": i + 1, "elapsed_s": 0.0})
    return {"status": "completed", "stop_reason": "target_reached", "iterations": blocks}


def hang_job(
    payload: dict[str, Any], ctl: WorkerControl, emit: Callable[[dict[str, Any]], None]
) -> dict[str, Any]:
    time.sleep(float(payload.get("seconds", 30)))
    return {"status": "completed"}
