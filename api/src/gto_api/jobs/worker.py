"""Lado do worker: controle cooperativo e envelope de execução dos jobs."""

from __future__ import annotations

import importlib
import time
import traceback
from collections.abc import Callable
from typing import Any

POLL_S = 0.05


class JobCancelled(Exception):
    """Levantada pelo job ao detectar cancelamento (remove saídas parciais antes)."""


class WorkerControl:
    """Implementa o `SolveControl` do motor sobre Events (multiprocessing ou threading)."""

    def __init__(
        self,
        job_id: str,
        emit: Callable[[dict[str, Any]], None],
        pause: Any,
        stop: Any,
        cancel: Any,
    ) -> None:
        self.job_id = job_id
        self._emit = emit
        self._pause = pause
        self._stop = stop
        self._cancel = cancel

    @property
    def cancelled(self) -> bool:
        return bool(self._cancel.is_set())

    def should_stop(self) -> bool:
        return bool(self._stop.is_set() or self._cancel.is_set())

    def is_cancelled(self) -> bool:
        return self.cancelled

    def check_cancel(self) -> None:
        if self.cancelled:
            raise JobCancelled()

    def wait_if_paused(self) -> None:
        if self._pause.is_set() and not self.should_stop():
            self._emit({"type": "status", "status": "paused"})
            while self._pause.is_set() and not self.should_stop():
                time.sleep(POLL_S)
            if not self.should_stop():
                self._emit({"type": "status", "status": "running"})


def resolve(func: str) -> Callable[..., dict[str, Any]]:
    mod, name = func.split(":")
    fn: Callable[..., dict[str, Any]] = getattr(importlib.import_module(mod), name)
    return fn


def worker_main(
    job_id: str, func: str, payload: dict[str, Any], events: Any, pause: Any, stop: Any, cancel: Any
) -> None:
    def emit(ev: dict[str, Any]) -> None:
        events.put({"job_id": job_id, "ts": time.time(), **ev})

    ctl = WorkerControl(job_id, emit, pause, stop, cancel)
    emit({"type": "status", "status": "running"})
    try:
        result = resolve(func)(payload, ctl, emit)
        status = result.pop("status", "completed")
        emit({"type": "result", "status": status, **result})
    except JobCancelled:
        emit({"type": "result", "status": "cancelled"})
    except MemoryError:
        emit(
            {
                "type": "error",
                "code": "memoria_insuficiente",
                "detail": "Memória insuficiente durante o job.",
            }
        )
    except Exception as exc:  # erro inesperado vira failed com detalhe
        emit(
            {
                "type": "error",
                "code": getattr(exc, "code", "erro_interno"),
                "detail": str(exc) or "Erro interno no job.",
                "trace": traceback.format_exc(limit=5),
            }
        )


def init_worker(warm: bool) -> None:
    if warm:
        from gto_engine.warmup import warmup

        warmup()
