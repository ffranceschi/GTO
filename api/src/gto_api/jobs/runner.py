"""Interface de execução de jobs (plan.md): permite trocar por fila distribuída depois."""

from __future__ import annotations

from collections.abc import AsyncIterator, Callable
from dataclasses import dataclass, field
from typing import Any, Literal, Protocol

Lane = Literal["solve", "aux"]
Command = Literal["pause", "resume", "stop", "cancel"]
JobKind = Literal["solve", "export", "import", "cleanup", "test"]
FINAL_STATUSES = ("completed", "stopped", "cancelled", "failed")


@dataclass(frozen=True)
class Job:
    id: str
    kind: JobKind
    func: str  # "modulo:funcao" executada no worker: fn(payload, control, emit) -> dict
    payload: dict[str, Any] = field(default_factory=dict)
    meta: dict[str, Any] = field(
        default_factory=dict
    )  # campos fixos do snapshot (alvo, tempo-limite…)


JobEvent = dict[str, Any]  # mensagem do contrato websocket.md (type, job_id, job_kind, seq, …)
EventHook = Callable[[Job, JobEvent], None]


class JobStateError(Exception):
    """Comando incompatível com o estado do job (vira 409)."""


class UnknownJobError(KeyError):
    pass


class JobRunner(Protocol):
    async def submit(self, job: Job, lane: Lane) -> None: ...
    async def control(self, job_id: str, command: Command) -> None: ...
    def events(self, job_id: str) -> AsyncIterator[JobEvent]: ...
    def queue_position(self, job_id: str) -> int | None: ...
    def status(self, job_id: str) -> str | None: ...
    async def shutdown(self) -> None: ...
