"""T099 — mensagens de erro sempre em pt-BR, números com vírgula decimal."""

from fastapi.testclient import TestClient

from gto_api.errors import fmt_num


def test_fmt_num() -> None:
    assert fmt_num(4.0) == "4,00" and fmt_num(1234.5, 1) == "1.234,5"


def test_validacao_e_405_em_pt_br(client: TestClient) -> None:
    r = client.post("/api/v1/solves", json={"spot": {"pot": "x"}, "tree": 3})
    body = r.json()
    assert r.status_code == 422 and body["detail"] == "Há campos inválidos na requisição."
    english = ("Field required", "Input should", "valid", "Method Not Allowed")
    assert not any(w in e["detail"] for e in body["errors"] for w in english)
    m = client.put("/api/v1/health")
    assert m.status_code == 405 and m.json()["detail"] == "Método não permitido para este recurso."


def test_erros_da_001_em_pt_br(client: TestClient) -> None:
    english = ("Field required", "Input should", "valid", "String should", "List should")
    cases = [
        ("/api/v1/ranges/format", {"weights": [0.5] * 10}),
        (
            "/api/v1/equity/estimate",
            {"participants": [{"notation": "AA"}] * 2, "target_margin_pp": 2},
        ),
        ("/api/v1/equity-jobs", {"participants": [{"notation": "AA"}] * 2, "seed": -1}),
        ("/api/v1/saved-ranges", {"name": "x" * 61, "notation": "AA"}),
    ]
    for url, payload in cases:
        body = client.post(url, json=payload).json()
        assert body["status"] == 422 and body["detail"] == "Há campos inválidos na requisição."
        assert not any(w in e["detail"] for e in body["errors"] for w in english), body
    r = client.post("/api/v1/equity-jobs", json={"participants": [{"notation": "AhKh"}] * 2})
    assert r.json()["code"] == "equity_invalida" and "Carta duplicada: Ah" in r.json()["detail"]
