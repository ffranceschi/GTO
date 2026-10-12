"""Parse de ranges usado pelo formulário do spot (T060)."""

from fastapi.testclient import TestClient


def test_parse_com_bloqueio(client: TestClient) -> None:
    r = client.post("/api/v1/ranges/parse", json={"notation": "22+, A2s+, KTo+"})
    body = r.json()
    assert r.status_code == 200 and body["combos"] == 162 and body["canonical"] == "22+, A2s+, KTo+"
    assert round(body["pct_of_total"] * 100, 1) == 12.2
    r2 = client.post(
        "/api/v1/ranges/parse", json={"notation": "AA", "board": ["As", "7d", "2c"]}
    ).json()
    assert r2["combos_after_board"] == 3


def test_notacao_invalida(client: TestClient) -> None:
    r = client.post("/api/v1/ranges/parse", json={"notation": "AKx"})
    assert r.status_code == 422 and r.json()["code"] == "range_invalido"
