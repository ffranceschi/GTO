"""T044 — latência de controle da equity com o runner de processos real (com warm-up)."""

from __future__ import annotations

import time
from collections.abc import Iterator
from typing import Any

import pytest
from fastapi.testclient import TestClient

from gto_api.main import create_app
from gto_api.settings import Settings

FULL = "22+, A2+, K2+, Q2+, J2+, T2+, 92+, 82+, 72+, 62+, 52+, 42+, 32"
# 6-way amplo até ±0,05 pp: ~2 M amostras em blocos crescentes — ainda está rodando logo após o
# primeiro `progress` (bloco de 16 k amostras), mesmo numa máquina rápida
SIX_WAY = {
    "participants": [{"notation": FULL}] * 6,
    "method": "monte_carlo",
    "target_margin_pp": 0.05,
    "time_limit_s": 60,
}


@pytest.fixture(scope="module")
def proc_client(tmp_path_factory: pytest.TempPathFactory) -> Iterator[TestClient]:
    app = create_app(
        Settings(
            data_dir=tmp_path_factory.mktemp("eqlat"), use_processes=True, periodic_cleanup=False
        )
    )
    with TestClient(app) as c:
        t0 = time.monotonic()
        while c.get("/api/v1/health").status_code != 200:
            assert time.monotonic() - t0 < 120
            time.sleep(0.1)
        yield c


def until(ws: Any, pred: Any, t0: float, limit: float) -> dict[str, Any]:
    while True:
        m: dict[str, Any] = ws.receive_json()
        if pred(m):
            assert time.monotonic() - t0 < limit, (m, time.monotonic() - t0)
            return m
        assert m["type"] != "finished", m


def test_post_rapido_e_taxa_medida_no_warmup(proc_client: TestClient) -> None:
    c = proc_client
    assert c.app.state.runner.equity_rate > 0  # type: ignore[attr-defined]
    c.post("/api/v1/equity-jobs", json={"participants": [{"notation": "AA"}, {"notation": "KK"}]})
    t0 = time.perf_counter()
    r = c.post("/api/v1/equity-jobs", json=SIX_WAY)
    assert r.status_code == 202 and time.perf_counter() - t0 <= 0.2
    c.delete(f"/api/v1/equity-jobs/{r.json()['id']}")


@pytest.mark.parametrize("command", ["stop", "cancel"])
def test_parar_e_cancelar_6_way_em_menos_de_1s(proc_client: TestClient, command: str) -> None:
    c = proc_client
    job = c.post("/api/v1/equity-jobs", json=SIX_WAY).json()
    with c.websocket_connect(f"/api/v1/jobs/{job['id']}/events") as ws:
        ws.receive_json()
        until(ws, lambda m: m["type"] == "progress", time.monotonic(), 30)
        t = time.monotonic()
        if command == "stop":
            assert c.post(f"/api/v1/equity-jobs/{job['id']}/stop").status_code == 202
            fin = until(ws, lambda m: m["type"] == "finished", t, 1.0)
            assert fin["status"] == "completed" and fin["stop_reason"] == "user_stopped"
        else:
            assert c.delete(f"/api/v1/equity-jobs/{job['id']}").status_code == 202
            fin = until(ws, lambda m: m["type"] == "finished", t, 1.0)
            assert fin["status"] == "cancelled"
    body = c.get(f"/api/v1/equity-jobs/{job['id']}").json()
    assert (body["result"] is None) == (command == "cancel")
