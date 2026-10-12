"""Runner falso para os testes da API: mesmo núcleo do runner local, com threads e sem warm-up."""

from __future__ import annotations

from gto_api.jobs.local_process import LaneJobRunner
from gto_api.jobs.runner import EventHook


class FakeJobRunner(LaneJobRunner):
    def __init__(self, on_event: EventHook | None = None, command_timeout_s: float = 10.0) -> None:
        super().__init__(
            backend="thread", warm=False, command_timeout_s=command_timeout_s, on_event=on_event
        )
