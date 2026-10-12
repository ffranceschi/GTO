"""Parse de ranges do formulário do spot (T060) e /ranges/format com dead_cards (T027 da 001)."""

import time

from fastapi.testclient import TestClient
from gto_engine.cards import N_COMBOS, combo_index, parse_card
from gto_engine.ranges import parse_range


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


# ---- T027 (feature 001, US2): dead_cards e /ranges/format ----
def test_parse_com_dead_cards(client: TestClient) -> None:
    r = client.post("/api/v1/ranges/parse", json={"notation": "AA", "dead_cards": ["As"]}).json()
    assert r["combos"] == 6 and r["combos_after_board"] == 3
    # board e mãos específicas dos outros somam bloqueios
    r2 = client.post(
        "/api/v1/ranges/parse",
        json={"notation": "AA, KK", "board": ["Ks", "7d", "2c"], "dead_cards": ["Ah", "Kh"]},
    ).json()
    assert r2["combos_after_board"] == 3 + 1
    assert round(r2["pct_of_total"] * 1326, 6) == 4


def test_format_canonico(client: TestClient) -> None:
    w = parse_range("AKs").weights.copy()
    w[combo_index(parse_card("As"), parse_card("Ks"))] = 0.0
    r = client.post("/api/v1/ranges/format", json={"weights": w.tolist()})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["canonical"] == "AhKh, AdKd, AcKc" and body["combos"] == 3
    half = parse_range("KQo:0.5").weights.tolist()
    b2 = client.post("/api/v1/ranges/format", json={"weights": half, "dead_cards": ["Kh"]}).json()
    assert b2["canonical"] == "KQo:0.5" and b2["combos"] == 6 and b2["combos_after_board"] == 4.5


def test_format_exige_1326_pesos(client: TestClient) -> None:
    r = client.post("/api/v1/ranges/format", json={"weights": [0.0] * (N_COMBOS - 1)})
    assert r.status_code == 422


def test_parse_e_format_em_200ms(client: TestClient) -> None:
    full = "22+, A2+, K2+, Q2+, J2+, T2+, 92+, 82+, 72+, 62+, 52+, 42+, 32"
    w = parse_range(full).weights.tolist()
    client.post("/api/v1/ranges/format", json={"weights": w})  # aquece
    for url, payload in (
        (
            "/api/v1/ranges/parse",
            {"notation": full, "board": ["Ks", "7d", "2c"], "dead_cards": ["Ah", "Ad"]},
        ),
        ("/api/v1/ranges/format", {"weights": w, "dead_cards": ["Ah"]}),
    ):
        t0 = time.perf_counter()
        assert client.post(url, json=payload).status_code == 200
        assert time.perf_counter() - t0 <= 0.2
