"""T038 — CRUD de ranges salvos (US4, FR-025 a FR-027)."""

from __future__ import annotations

from pathlib import Path

import numpy as np
from fastapi.testclient import TestClient
from gto_engine.ranges import parse_range

from gto_api.main import create_app
from gto_api.settings import Settings
from tests.fakes import FakeJobRunner

URL = "/api/v1/saved-ranges"
BTN = "22+, A2s+, K9s+, QTs+, JTs, ATo+, KJo+, KQo:0.5, AhKh"


def test_criar_listar_sobrescrever_renomear_excluir(client: TestClient) -> None:
    r = client.post(URL, json={"name": "BTN open 100bb", "notation": BTN})
    assert r.status_code == 201, r.text
    saved = r.json()
    assert {"id", "name", "notation", "combos", "updated_at"} <= saved.keys()
    # notação canônica com os pesos preservados exatamente (ida e volta — FR-026)
    back = parse_range(saved["notation"]).weights
    assert np.array_equal(back, parse_range(BTN).weights)
    assert saved["combos"] == float(parse_range(BTN).weights.sum())

    dup = client.post(URL, json={"name": "BTN open 100bb", "notation": "AA"})
    assert dup.status_code == 409 and dup.json()["code"] == "nome_em_uso"
    over = client.post(URL, json={"name": "BTN open 100bb", "notation": "AA", "overwrite": True})
    assert over.status_code == 201 and over.json()["id"] == saved["id"]
    assert over.json()["notation"] == "AA" and over.json()["combos"] == 6

    other = client.post(URL, json={"name": "CO open", "notation": "KK+"}).json()
    names = [x["name"] for x in client.get(URL).json()]
    assert names == ["BTN open 100bb", "CO open"]

    ren = client.put(f"{URL}/{other['id']}", json={"name": "BTN open 100bb", "notation": "KK+"})
    assert ren.status_code == 409 and ren.json()["code"] == "nome_em_uso"
    ok = client.put(f"{URL}/{other['id']}", json={"name": "CO 2,5x", "notation": "QQ+"})
    assert ok.status_code == 200 and ok.json()["name"] == "CO 2,5x" and ok.json()["combos"] == 18

    assert client.delete(f"{URL}/{other['id']}").status_code == 204
    assert client.delete(f"{URL}/{other['id']}").status_code == 404
    missing = "00000000-0000-0000-0000-000000000000"
    assert client.put(f"{URL}/{missing}", json={"name": "x", "notation": "AA"}).status_code == 404


def test_validacoes(client: TestClient) -> None:
    for name in ("", "x" * 61):
        r = client.post(URL, json={"name": name, "notation": "AA"})
        assert r.status_code == 422
        assert any("Texto" in e["detail"] for e in r.json()["errors"])
    assert client.post(URL, json={"name": "  ", "notation": "AA"}).status_code == 422
    bad = client.post(URL, json={"name": "ruim", "notation": "AKx"})
    assert bad.status_code == 422 and bad.json()["code"] == "range_invalido"
    empty = client.post(URL, json={"name": "vazio", "notation": ""})
    assert empty.status_code == 422


def test_persiste_apos_reiniciar(tmp_path: Path) -> None:
    s = Settings(data_dir=tmp_path, use_processes=False)
    with TestClient(create_app(s, FakeJobRunner())) as c:
        assert c.post(URL, json={"name": "BTN", "notation": BTN}).status_code == 201
    with TestClient(create_app(s, FakeJobRunner())) as c:
        rows = c.get(URL).json()
        assert [r["name"] for r in rows] == ["BTN"]
        assert np.array_equal(parse_range(rows[0]["notation"]).weights, parse_range(BTN).weights)


def test_pedidos_simultaneos_com_o_mesmo_nome(client: TestClient) -> None:
    """Corrida entre a consulta do nome e o insert: o perdedor recebe 409, nunca 500."""
    from concurrent.futures import ThreadPoolExecutor

    def post(_: int) -> int:
        return client.post(URL, json={"name": "corrida", "notation": "AA"}).status_code

    with ThreadPoolExecutor(8) as ex:
        codes = list(ex.map(post, range(16)))
    assert codes.count(201) == 1 and set(codes) == {201, 409}, codes
