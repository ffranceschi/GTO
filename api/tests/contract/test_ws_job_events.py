"""T039 — contrato do WebSocket de jobs (contracts/websocket.md)."""

from __future__ import annotations

import itertools
import time
from typing import Any

import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from gto_api.jobs.runner import Job

LOOP = "tests.jobs_for_tests:loop_job"


def submit(client: TestClient, job: Job) -> None:
    client.portal.call(client.app.state.runner.submit, job, "solve")  # type: ignore[union-attr,attr-defined]


def test_snapshot_seq_campos_e_finished(client: TestClient) -> None:
    submit(client, Job("j1", "test", LOOP, {"blocks": 40, "block_s": 0.05}))
    msgs: list[dict[str, Any]] = []
    times: list[float] = []
    with client.websocket_connect("/api/v1/jobs/j1/events") as ws:
        while True:
            try:
                m = ws.receive_json()
            except WebSocketDisconnect as exc:
                assert exc.code == 1000
                break
            msgs.append(m)
            times.append(time.monotonic())
            if m["type"] == "finished":
                with pytest.raises(WebSocketDisconnect) as exc2:
                    ws.receive_json()
                assert exc2.value.code == 1000
                break
    assert msgs[0]["type"] == "snapshot"
    assert msgs[-1]["type"] == "finished" and msgs[-1]["status"] == "completed"
    assert all({"type", "job_id", "job_kind", "seq"} <= m.keys() for m in msgs)
    seqs = [m["seq"] for m in msgs[1:]]
    assert seqs == sorted(seqs) and len(seqs) == len(set(seqs))
    assert msgs[1]["seq"] > msgs[0]["seq"] or msgs[0]["seq"] == 0
    prog = [t for m, t in zip(msgs, times, strict=True) if m["type"] == "progress"]
    gaps = [b - a for a, b in itertools.pairwise(prog)]
    assert gaps and min(gaps) >= 0.15  # ≤ 5 mensagens/s (margem de agendamento)
    assert max(gaps) <= 1.0  # ≥ 1 mensagem/s durante running


def test_job_inexistente_fecha_4404(client: TestClient) -> None:
    with client.websocket_connect("/api/v1/jobs/nao-existe/events") as ws:
        with pytest.raises(WebSocketDisconnect) as exc:
            ws.receive_json()
        assert exc.value.code == 4404


def test_reconexao_recebe_snapshot_e_job_continua(client: TestClient) -> None:
    submit(client, Job("j2", "test", LOOP, {"blocks": 10_000, "block_s": 0.05}))
    with client.websocket_connect("/api/v1/jobs/j2/events") as ws:
        first = ws.receive_json()
        assert first["type"] == "snapshot"
        ws.receive_json()
    time.sleep(0.3)
    with client.websocket_connect("/api/v1/jobs/j2/events") as ws:
        snap = ws.receive_json()
        assert snap["type"] == "snapshot" and snap["status"] == "running"
        nxt = ws.receive_json()
        assert nxt["seq"] > snap["seq"]
    client.portal.call(client.app.state.runner.control, "j2", "cancel")  # type: ignore[union-attr,attr-defined]
