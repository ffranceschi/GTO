"""T051 — API de solves (US1)."""

from __future__ import annotations

import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from gto_api.main import create_app
from gto_api.settings import Settings
from tests.fakes import FakeJobRunner
from tests.helpers import small_request, wait_solve


def test_criar_resolver_e_reaproveitar(client: TestClient) -> None:
    t0 = time.perf_counter()
    r = client.post("/api/v1/solves", json=small_request())
    assert time.perf_counter() - t0 <= 0.2 or r.status_code == 202
    assert r.status_code == 202, r.text
    body = r.json()
    assert body["status"] in ("queued", "running") and len(body["input_hash"]) == 64
    done = wait_solve(client, body["id"], ("completed",))
    assert done["exploitability_pct"] <= 0.5 and done["stop_reason"] == "target_reached"
    assert done["size_bytes"] > 0 and done["pinned"] is False and done["expires_at"]
    again = client.post("/api/v1/solves", json=small_request())
    assert again.status_code == 200 and again.json()["id"] == body["id"]
    forced = client.post("/api/v1/solves", json=small_request(force=True))
    assert forced.status_code == 202 and forced.json()["id"] != body["id"]


def test_criacao_responde_em_ate_200ms(client: TestClient) -> None:
    client.post("/api/v1/solves", json=small_request(pot=11))  # aquece o caminho
    t0 = time.perf_counter()
    r = client.post("/api/v1/solves", json=small_request(pot=12))
    assert r.status_code == 202
    assert time.perf_counter() - t0 <= 0.2


@pytest.mark.parametrize(
    ("over", "code", "trecho"),
    [
        ({"board": ["Ks", "Ks", "2c", "Jh", "3s"]}, "spot_invalido", "board"),
        ({"pot": 0}, "entrada_invalida", None),
        (
            {"oop_range": {"notation": "AA"}, "board": ["As", "Ah", "Ad", "8d", "2h"]},
            "spot_invalido",
            "OOP",
        ),
        ({"oop_range": {"notation": "AKx"}}, "range_invalido", "AKx"),
    ],
)
def test_erros_422_pt_br(
    client: TestClient, over: dict[str, object], code: str, trecho: str | None
) -> None:
    r = client.post("/api/v1/solves", json=small_request(**over))
    assert r.status_code == 422, r.text
    assert r.headers["content-type"].startswith("application/problem+json")
    body = r.json()
    assert body["code"] == code
    if trecho:
        assert trecho in body["detail"]


def test_arvore_grande_demais(tmp_path: Path) -> None:
    app = create_app(
        Settings(data_dir=tmp_path, use_processes=False, max_solve_memory_bytes=1000),
        FakeJobRunner(),
    )
    with TestClient(app) as c:
        r = c.post("/api/v1/solves", json=small_request())
        assert r.status_code == 422 and r.json()["code"] == "arvore_grande_demais"
        assert "GiB" in r.json()["detail"] or "memória" in r.json()["detail"]


def test_listar_obter_controle_e_excluir(client: TestClient) -> None:
    long = small_request(params={"target_exploitability_pct": 1e-9, "time_limit_s": 60})
    a = client.post("/api/v1/solves", json=long).json()
    wait_solve(client, a["id"], ("running",))
    assert client.post(f"/api/v1/solves/{a['id']}/nodes").status_code == 405
    n = client.get(f"/api/v1/solves/{a['id']}/nodes", params={"path": ""})
    assert n.status_code == 409 and n.json()["code"] == "solucao_indisponivel"
    for _ in range(2):
        assert client.post(f"/api/v1/solves/{a['id']}/pause").status_code == 202
    wait_solve(client, a["id"], ("paused",), timeout=2)
    assert client.post(f"/api/v1/solves/{a['id']}/resume").status_code == 202
    wait_solve(client, a["id"], ("running",), timeout=2)
    assert client.post(f"/api/v1/solves/{a['id']}/stop").status_code == 202
    assert client.post(f"/api/v1/solves/{a['id']}/stop").status_code == 202
    stopped = wait_solve(client, a["id"], ("stopped",), timeout=5)
    assert stopped["stop_reason"] == "user_stopped" and stopped["exploitability_pct"] is not None
    assert client.post(f"/api/v1/solves/{a['id']}/pause").status_code == 409
    node = client.get(f"/api/v1/solves/{a['id']}/nodes", params={"path": ""})
    assert node.status_code == 200 and node.json()["kind"] == "decision"
    b = client.post(
        "/api/v1/solves",
        json=small_request(pot=13, params={"target_exploitability_pct": 1e-9, "time_limit_s": 60}),
    ).json()
    lst = client.get("/api/v1/solves").json()
    assert [s["id"] for s in lst][:2] == [b["id"], a["id"]]
    assert all(
        s["status"] == "stopped"
        for s in client.get("/api/v1/solves", params={"status": "stopped"}).json()
    )
    assert client.delete(f"/api/v1/solves/{b['id']}").status_code == 202
    wait_solve(client, b["id"], ("cancelled",), timeout=5)
    assert client.delete(f"/api/v1/solves/{a['id']}").status_code == 204
    assert client.get(f"/api/v1/solves/{a['id']}").status_code == 404


def test_no_inexistente_e_caminho_invalido(client: TestClient) -> None:
    assert client.get("/api/v1/solves/00000000-0000-0000-0000-000000000000").status_code == 404
    s = client.post("/api/v1/solves", json=small_request()).json()
    wait_solve(client, s["id"], ("completed",))
    r = client.get(f"/api/v1/solves/{s['id']}/nodes", params={"path": "zz"})
    assert r.status_code == 422 and r.json()["code"] == "caminho_invalido"
    v = client.get(f"/api/v1/solves/{s['id']}/nodes", params={"path": "x/b50"}).json()
    assert v["player"] == "oop" and v["breadcrumb"] == ["Check", "Bet 50% (5 bb)"]
    assert len(v["ranges"]) == 2 and len(v["ranges"][0]["weights"]) == 1326
