"""T015 — API de equity (US1)."""

from __future__ import annotations

import time
from typing import Any

import pytest
from fastapi.testclient import TestClient

FULL = "22+, A2+, K2+, Q2+, J2+, T2+, 92+, 82+, 72+, 62+, 52+, 42+, 32"


def wait_eq(
    c: TestClient, job_id: str, statuses: tuple[str, ...], timeout: float = 60
) -> dict[str, Any]:
    t0 = time.monotonic()
    while True:
        b: dict[str, Any] = c.get(f"/api/v1/equity-jobs/{job_id}").json()
        if b["status"] in statuses:
            return b
        assert time.monotonic() - t0 < timeout, b
        time.sleep(0.05)


def body(*ranges: str, board: list[str] | None = None, **kw: Any) -> dict[str, Any]:
    return {"participants": [{"notation": r} for r in ranges], "board": board or [], **kw}


def test_estimativa_e_resultado_exato(client: TestClient) -> None:
    e = client.post("/api/v1/equity/estimate", json=body("AA", "KK"))
    assert e.status_code == 200 and e.json()["method"] == "exact"
    client.post(
        "/api/v1/equity-jobs", json=body("AhKh", "QsQd", board=["Jh", "Th", "2c"])
    )  # aquece
    t0 = time.perf_counter()
    r = client.post("/api/v1/equity-jobs", json=body("AA", "KK"))
    assert r.status_code == 202 and time.perf_counter() - t0 <= 0.2
    job = r.json()
    assert job["method"] == "exact" and job["estimate"]["exact_evaluations"] > 0
    done = wait_eq(client, job["id"], ("completed",))
    p = done["result"]["participants"]
    assert p[0]["equity"] == pytest.approx(0.8195, abs=0.001) and p[0]["margin"] == 0
    assert {"equity", "win", "tie", "margin", "combos"} <= p[0].keys()
    assert done["result"]["stop_reason"] == "exact"


def test_stop_mantem_parcial_e_cancel_descarta(client: TestClient) -> None:
    # 6-way amplo até ±0,05 pp leva ~0,5 s numa máquina rápida: parar logo após `running`
    # (o Monte Carlo sempre conclui ao menos um bloco antes de atender o stop)
    long = body(*[FULL] * 6, method="monte_carlo", target_margin_pp=0.05, time_limit_s=60)
    a = client.post("/api/v1/equity-jobs", json=long).json()
    wait_eq(client, a["id"], ("running",))
    assert client.post(f"/api/v1/equity-jobs/{a['id']}/stop").status_code == 202
    sa = wait_eq(client, a["id"], ("completed",), timeout=5)
    assert (
        sa["result"]["stop_reason"] == "user_stopped"
        and sa["result"]["participants"][0]["margin"] > 0
    )
    b = client.post("/api/v1/equity-jobs", json=long).json()
    wait_eq(client, b["id"], ("running",))
    t = time.monotonic()
    assert client.delete(f"/api/v1/equity-jobs/{b['id']}").status_code == 202
    sb = wait_eq(client, b["id"], ("cancelled",), timeout=2)
    assert time.monotonic() - t < 1.0 and sb["result"] is None
    assert client.post(f"/api/v1/equity-jobs/{b['id']}/stop").status_code == 409


@pytest.mark.parametrize(
    ("payload", "trecho"),
    [
        (body("AhKh", "AhQd"), "Ah"),
        (body("AA", "KK", board=["Ks", "7d"]), "board"),
        (body("AA", "KK", board=["As", "Ah", "Ad", "8d", "2c"]), "Participante 1"),
        (body("22, 33", "22, 33", board=["2s", "2h", "2d", "2c", "3s"]), "confronto"),
        (body("AA"), "2 a 6"),
    ],
)
def test_erros_422_pt_br(client: TestClient, payload: dict[str, Any], trecho: str) -> None:
    for url in ("/api/v1/equity/estimate", "/api/v1/equity-jobs"):
        r = client.post(url, json=payload)
        assert r.status_code == 422, r.text
        assert trecho in r.json()["detail"] or any(
            trecho in e["detail"] for e in r.json().get("errors", [])
        )


def test_job_inexistente(client: TestClient) -> None:
    assert client.get("/api/v1/equity-jobs/00000000-0000-0000-0000-000000000000").status_code == 404
