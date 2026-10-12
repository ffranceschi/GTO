"""T078 — estimativa de árvore e configurações nomeadas (US3)."""

from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from gto_api.main import create_app
from gto_api.settings import Settings
from tests.fakes import FakeJobRunner
from tests.helpers import sizes, small_request

FULL = "22+, A2+, K2+, Q2+, J2+, T2+, 92+, 82+, 72+, 62+, 52+, 42+, 32"


def test_estimativa_dentro_do_limite(client: TestClient) -> None:
    req = small_request()
    r = client.post("/api/v1/trees/estimate", json={"spot": req["spot"], "tree": req["tree"]})
    assert r.status_code == 200, r.text
    body = r.json()
    for k in (
        "decision_nodes",
        "chance_nodes",
        "terminal_nodes",
        "estimated_bytes",
        "estimated_solution_bytes",
        "max_bytes",
        "within_limit",
        "isomorphism_factor",
    ):
        assert k in body
    assert body["within_limit"] is True and body["suggestions"] == []


def test_estimativa_flop_padrao_recusada_com_sugestoes(client: TestClient) -> None:
    spot = {
        "oop_range": {"notation": FULL},
        "ip_range": {"notation": FULL},
        "board": ["Ks", "7d", "2c"],
        "pot": 6,
        "effective_stack": 97,
    }
    tree = {
        "bet_sizes": sizes([0.33, 0.75]),
        "raise_sizes": sizes([1.0]),
        "max_raises_per_street": 3,
        "allin_threshold": 0.67,
    }
    body = client.post("/api/v1/trees/estimate", json={"spot": spot, "tree": tree}).json()
    assert body["within_limit"] is False and body["estimated_bytes"] > body["max_bytes"]
    texto = " ".join(body["suggestions"])
    assert "tamanhos" in texto and "raises" in texto and "ranges" in texto
    r = client.post("/api/v1/solves", json={"spot": spot, "tree": tree})
    assert r.status_code == 422 and r.json()["code"] == "arvore_grande_demais"


def test_crud_configuracoes(client: TestClient) -> None:
    lst = client.get("/api/v1/tree-configs").json()
    default = [c for c in lst if c["is_default"]]
    assert len(default) == 1 and default[0]["name"] == "Padrão"
    assert default[0]["config"]["bet_sizes"]["river"]["oop"] == [0.33, 0.75]
    cfg = {
        "bet_sizes": sizes([0.5]),
        "raise_sizes": sizes([1.0]),
        "max_raises_per_street": 1,
        "allin_threshold": 0.67,
    }
    a = client.post("/api/v1/tree-configs", json={"name": "River 1 bet", "config": cfg})
    assert a.status_code == 201, a.text
    a_id = a.json()["id"]
    dup = client.post("/api/v1/tree-configs", json={"name": "River 1 bet", "config": cfg})
    assert dup.status_code == 409 and dup.json()["code"] == "nome_em_uso"
    ow = client.post(
        "/api/v1/tree-configs", json={"name": "River 1 bet", "config": cfg, "overwrite": True}
    )
    assert ow.status_code == 201 and ow.json()["id"] == a_id
    for bad in ("", "x" * 61):
        assert (
            client.post("/api/v1/tree-configs", json={"name": bad, "config": cfg}).status_code
            == 422
        )
    ren = client.put(f"/api/v1/tree-configs/{a_id}", json={"name": "River simples", "config": cfg})
    assert ren.status_code == 200 and ren.json()["name"] == "River simples"
    b = client.post("/api/v1/tree-configs", json={"name": "Outra", "config": cfg}).json()
    clash = client.put(
        f"/api/v1/tree-configs/{b['id']}", json={"name": "River simples", "config": cfg}
    )
    assert clash.status_code == 409
    assert client.delete(f"/api/v1/tree-configs/{default[0]['id']}").status_code == 409
    assert (
        client.put(
            f"/api/v1/tree-configs/{default[0]['id']}", json={"name": "X", "config": cfg}
        ).status_code
        == 409
    )
    assert client.delete(f"/api/v1/tree-configs/{a_id}").status_code == 204
    assert client.delete(f"/api/v1/tree-configs/{a_id}").status_code == 404


def test_padrao_semeado_uma_vez(tmp_path: Path) -> None:
    s = Settings(data_dir=tmp_path, use_processes=False)
    for _ in range(2):
        with TestClient(create_app(s, FakeJobRunner())) as c:
            assert sum(x["is_default"] for x in c.get("/api/v1/tree-configs").json()) == 1
