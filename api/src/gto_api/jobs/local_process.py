"""Runner local: duas raias (solve, aux), 1 worker cada, fila FIFO e controle cooperativo (R4).

O mesmo núcleo serve a dois backends: processos (`ProcessPoolExecutor` + `multiprocessing.Manager`,
produção) e threads (testes da API, `FakeJobRunner`).
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import multiprocessing as mp
import queue as queue_mod
import threading
import time
from collections import deque
from collections.abc import AsyncIterator
from concurrent.futures import Executor, Future, ProcessPoolExecutor, ThreadPoolExecutor
from dataclasses import dataclass, field
from typing import Any, Literal

from gto_api.jobs.runner import (
    FINAL_STATUSES,
    Command,
    EventHook,
    Job,
    JobEvent,
    JobStateError,
    Lane,
    UnknownJobError,
)
from gto_api.jobs.worker import init_worker, worker_main

log = logging.getLogger(__name__)
MAX_RATE_S = 0.2  # ≤ 5 mensagens de progresso por segundo
LANES: tuple[Lane, ...] = ("solve", "aux")


@dataclass
class _State:
    job: Job
    lane: Lane
    status: str = "queued"
    seq: int = -1
    data: dict[str, Any] = field(default_factory=dict)  # último progresso (campos do snapshot)
    history: list[list[float]] = field(default_factory=list)
    subscribers: set[asyncio.Queue[JobEvent]] = field(default_factory=set)
    finished: JobEvent | None = None
    events: tuple[Any, Any, Any] | None = None  # (pause, stop, cancel)
    deadline: float | None = None  # watchdog: resposta esperada até este instante
    command_ts: float = (
        0.0  # relógio de parede do último comando (acks posteriores zeram o deadline)
    )
    last_sent: float = 0.0
    flush: asyncio.TimerHandle | None = None
    pending: JobEvent | None = None


class LaneJobRunner:
    def __init__(
        self,
        backend: Literal["process", "thread"] = "process",
        warm: bool = True,
        command_timeout_s: float = 10.0,
        on_event: EventHook | None = None,
    ) -> None:
        self.backend = backend
        self.warm = warm
        self.command_timeout_s = command_timeout_s
        self.on_event = on_event
        self._jobs: dict[str, _State] = {}
        self._queues: dict[Lane, deque[str]] = {lane: deque() for lane in LANES}
        self._running: dict[Lane, str | None] = {lane: None for lane in LANES}
        self._executors: dict[Lane, Executor] = {}
        self._loop: asyncio.AbstractEventLoop | None = None
        self._manager: Any = None
        self._events_q: Any = None
        self._pump: threading.Thread | None = None
        self._closing = False
        self._watchdog: asyncio.Task[None] | None = None
        self.ready: asyncio.Event | None = None  # definido em start()

    # ---------------- ciclo de vida ----------------
    async def start(self) -> None:
        self._loop = asyncio.get_running_loop()
        self.ready = asyncio.Event()
        if self.backend == "process":
            ctx = mp.get_context("spawn")
            self._manager = ctx.Manager()
            self._events_q = self._manager.Queue()
        else:
            self._events_q = queue_mod.Queue()
        for lane in LANES:
            self._executors[lane] = self._new_executor()
        self._pump = threading.Thread(target=self._pump_events, name="job-events", daemon=True)
        self._pump.start()
        self._watchdog = asyncio.create_task(self._watch())
        if self.warm and self.backend == "process":
            # força a criação e o aquecimento do worker de cada raia antes de aceitar jobs
            await asyncio.gather(
                *(self._loop.run_in_executor(self._executors[lane], _noop) for lane in LANES)
            )
        self.ready.set()

    def _new_executor(self) -> Executor:
        if self.backend == "process":
            return ProcessPoolExecutor(
                max_workers=1,
                mp_context=mp.get_context("spawn"),
                initializer=init_worker,
                initargs=(self.warm,),
            )
        return ThreadPoolExecutor(max_workers=1)

    async def shutdown(self) -> None:
        self._closing = True
        for st in self._jobs.values():
            if st.events and st.status not in FINAL_STATUSES:
                st.events[2].set()
        for ex in self._executors.values():
            ex.shutdown(wait=False, cancel_futures=True)
        if self._watchdog:
            self._watchdog.cancel()
        if self._events_q is not None:
            with contextlib.suppress(Exception):
                self._events_q.put(None)
        if self._pump:
            self._pump.join(timeout=2)
        if self._manager is not None:
            with contextlib.suppress(Exception):
                self._manager.shutdown()

    # ---------------- API ----------------
    async def submit(self, job: Job, lane: Lane) -> None:
        st = _State(job, lane)
        self._jobs[job.id] = st
        self._queues[lane].append(job.id)
        self._emit(
            st,
            {"type": "status", "status": "queued", "queue_position": self.queue_position(job.id)},
        )
        self._dispatch(lane)

    def status(self, job_id: str) -> str | None:
        st = self._jobs.get(job_id)
        return st.status if st else None

    def has_job(self, job_id: str) -> bool:
        return job_id in self._jobs

    def queue_position(self, job_id: str) -> int | None:
        st = self._jobs.get(job_id)
        if not st or st.status != "queued":
            return None
        try:
            return list(self._queues[st.lane]).index(job_id) + 1
        except ValueError:
            return None

    async def control(self, job_id: str, command: Command) -> None:
        st = self._jobs.get(job_id)
        if st is None:
            raise UnknownJobError(job_id)
        if st.status in FINAL_STATUSES:
            raise JobStateError("O job já terminou.")
        if st.status == "queued":
            if command in ("cancel", "stop"):
                self._queues[st.lane].remove(job_id)
                self._finish(st, {"type": "finished", "status": "cancelled", "stop_reason": None})
                self._broadcast_positions(st.lane)
                return
            raise JobStateError("O job ainda está na fila: só é possível cancelá-lo.")
        assert st.events is not None
        pause, stop, cancel = st.events
        if command == "pause":
            if st.status in ("stopping", "finalizing"):
                raise JobStateError("O job está terminando e não pode ser pausado.")
            pause.set()
        elif command == "resume":
            if st.status in ("stopping", "finalizing"):
                raise JobStateError("O job está terminando e não pode ser retomado.")
            pause.clear()
        elif command == "stop":
            if st.status == "finalizing":
                return  # parada já em andamento (finalização)
            stop.set()
            pause.clear()
            self._emit(st, {"type": "status", "status": "stopping"})
        else:
            cancel.set()
            pause.clear()
            self._emit(st, {"type": "status", "status": "stopping"})
        st.command_ts = time.time()
        st.deadline = time.monotonic() + self.command_timeout_s

    async def events(self, job_id: str) -> AsyncIterator[JobEvent]:
        st = self._jobs.get(job_id)
        if st is None:
            raise UnknownJobError(job_id)
        q: asyncio.Queue[JobEvent] = asyncio.Queue()
        st.subscribers.add(q)
        try:
            yield self.snapshot(job_id)
            if st.finished is not None:
                yield st.finished
                return
            while True:
                msg = await q.get()
                yield msg
                if msg["type"] == "finished":
                    return
        finally:
            st.subscribers.discard(q)

    def snapshot(self, job_id: str) -> JobEvent:
        st = self._jobs[job_id]
        msg: JobEvent = {
            "type": "snapshot",
            "job_id": job_id,
            "job_kind": st.job.kind,
            "seq": max(st.seq, 0),
            "status": st.status,
            "queue_position": self.queue_position(job_id),
            **st.job.meta,
            **st.data,
        }
        if st.job.kind == "solve":
            msg["history"] = list(st.history)
        return msg

    # ---------------- internos ----------------
    def _dispatch(self, lane: Lane) -> None:
        if self._running[lane] is not None or not self._queues[lane] or self._closing:
            return
        job_id = self._queues[lane].popleft()
        st = self._jobs[job_id]
        self._running[lane] = job_id
        if self.backend == "process":
            ev = (self._manager.Event(), self._manager.Event(), self._manager.Event())
        else:
            ev = (threading.Event(), threading.Event(), threading.Event())
        st.events = ev
        self._emit(st, {"type": "status", "status": "running"})
        assert self._loop is not None
        fut = self._executors[lane].submit(
            worker_main, job_id, st.job.func, st.job.payload, self._events_q, *ev
        )

        def done(f: Future[None], jid: str = job_id) -> None:
            self._threadsafe(self._on_done, jid, f)

        fut.add_done_callback(done)
        self._broadcast_positions(lane)

    def _broadcast_positions(self, lane: Lane) -> None:
        for jid in self._queues[lane]:
            st = self._jobs[jid]
            self._emit(
                st,
                {"type": "status", "status": "queued", "queue_position": self.queue_position(jid)},
            )

    def _threadsafe(self, fn: Any, *args: Any) -> None:
        loop = self._loop
        if loop is None or loop.is_closed():
            return
        with contextlib.suppress(RuntimeError):
            loop.call_soon_threadsafe(fn, *args)

    def _pump_events(self) -> None:
        while True:
            try:
                ev = self._events_q.get()
            except (EOFError, OSError, BrokenPipeError):
                return
            if ev is None:
                return
            self._threadsafe(self._on_worker_event, ev)

    def _on_worker_event(self, ev: dict[str, Any]) -> None:
        st = self._jobs.get(ev.get("job_id", ""))
        if st is None or st.finished is not None:
            return
        kind = ev["type"]
        if ev.get("ts", 0.0) >= st.command_ts and (
            kind in ("progress", "result", "error")
            or (kind == "status" and ev.get("status") == "paused")
            or (kind == "status" and ev.get("status") == "running" and st.status == "paused")
        ):
            st.deadline = None  # o worker reagiu depois do último comando
        if kind == "status":
            status = ev["status"]
            if status == st.status:
                return
            if st.status == "stopping" and status in ("running", "paused"):
                return
            self._emit(st, {"type": "status", "status": status})
        elif kind == "progress":
            payload = {k: v for k, v in ev.items() if k not in ("job_id", "type", "ts")}
            st.data.update(payload)
            if (
                payload.get("exploitability_pct") is not None
                and payload.get("exploitability_iteration") is not None
            ):
                point = [
                    payload["exploitability_iteration"],
                    payload.get("elapsed_s", 0.0),
                    payload["exploitability_pct"],
                ]
                if not st.history or st.history[-1][0] != point[0]:
                    st.history.append(point)
            if payload.get("phase") == "finalizing" and st.status not in ("finalizing",):
                self._emit(st, {"type": "status", "status": "finalizing"})
            self._throttled_progress(st, {"type": "progress", **payload})
        elif kind == "result":
            fields = {k: v for k, v in ev.items() if k not in ("job_id", "type", "ts")}
            self._finish(st, {"type": "finished", **fields})
        elif kind == "error":
            self._emit(
                st,
                {
                    "type": "error",
                    "code": ev.get("code", "erro_interno"),
                    "detail": ev.get("detail", ""),
                },
            )
            self._finish(
                st,
                {
                    "type": "finished",
                    "status": "failed",
                    "stop_reason": None,
                    "error": {"code": ev.get("code"), "detail": ev.get("detail")},
                },
            )

    def _throttled_progress(self, st: _State, msg: JobEvent) -> None:
        now = time.monotonic()
        if now - st.last_sent >= MAX_RATE_S:
            st.last_sent = now
            st.pending = None
            self._emit(st, msg)
            return
        st.pending = msg
        if st.flush is None and self._loop is not None:
            st.flush = self._loop.call_later(MAX_RATE_S - (now - st.last_sent), self._flush, st)

    def _flush(self, st: _State) -> None:
        st.flush = None
        if st.pending is not None and st.finished is None:
            msg, st.pending = st.pending, None
            st.last_sent = time.monotonic()
            self._emit(st, msg)

    def _emit(self, st: _State, msg: JobEvent) -> None:
        if msg["type"] == "status":
            st.status = msg["status"]
        st.seq += 1
        full = {
            "type": msg["type"],
            "job_id": st.job.id,
            "job_kind": st.job.kind,
            "seq": st.seq,
            **{k: v for k, v in msg.items() if k != "type"},
        }
        for q in list(st.subscribers):
            q.put_nowait(full)
        if self.on_event is not None:
            try:
                self.on_event(st.job, full)
            except Exception:  # persistência não pode derrubar o runner
                log.exception("falha ao persistir evento do job %s", st.job.id)

    def _finish(self, st: _State, msg: JobEvent) -> None:
        if st.finished is not None:
            return
        if st.flush is not None:
            st.flush.cancel()
            st.flush = None
        st.pending = None  # progresso pendente é descartado: o `finished` traz os valores finais
        st.status = msg.get("status", "failed")
        self._emit(st, msg)
        st.finished = {**msg, "job_id": st.job.id, "job_kind": st.job.kind, "seq": st.seq}
        st.deadline = None
        if self._running[st.lane] == st.job.id:
            self._running[st.lane] = None
        self._dispatch(st.lane)

    def _on_done(self, job_id: str, fut: Future[None]) -> None:
        st = self._jobs.get(job_id)
        if st is None or st.finished is not None:
            return
        exc = fut.exception() if not fut.cancelled() else None

        # o resultado chega pela fila de eventos; se o worker morreu sem enviar, marca falha
        def late() -> None:
            if st.finished is None:
                detail = str(exc) if exc else "O worker terminou sem informar o resultado."
                self._finish(
                    st,
                    {
                        "type": "finished",
                        "status": "failed",
                        "stop_reason": None,
                        "error": {"code": "erro_interno", "detail": detail},
                    },
                )

        assert self._loop is not None
        self._loop.call_later(1.0, late)

    async def _watch(self) -> None:
        while True:
            await asyncio.sleep(0.25)
            now = time.monotonic()
            for st in list(self._jobs.values()):
                if st.deadline is not None and now > st.deadline and st.finished is None:
                    self._kill(st)

    def _kill(self, st: _State) -> None:
        log.warning("worker do job %s sem resposta; encerrando", st.job.id)
        ex = self._executors[st.lane]
        if isinstance(ex, ProcessPoolExecutor):
            for p in list(getattr(ex, "_processes", {}).values()):
                with contextlib.suppress(Exception):
                    p.terminate()
        ex.shutdown(wait=False, cancel_futures=True)
        self._executors[st.lane] = self._new_executor()
        detail = "O processo do job parou de responder e foi encerrado."
        self._emit(st, {"type": "error", "code": "worker_sem_resposta", "detail": detail})
        self._finish(
            st,
            {
                "type": "finished",
                "status": "failed",
                "stop_reason": None,
                "error": {"code": "worker_sem_resposta", "detail": detail},
            },
        )


def _noop() -> None:
    return None
