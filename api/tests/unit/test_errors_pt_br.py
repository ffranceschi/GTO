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
