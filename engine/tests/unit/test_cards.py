"""T007 — cartas e combos (52 cartas, 1326 combos, notação AhKh)."""

import pytest

from gto_engine.cards import (
    COMBO_CARDS,
    N_CARDS,
    N_COMBOS,
    InvalidCardError,
    card_str,
    combo_index,
    combo_str,
    parse_card,
    parse_combo,
)


def test_52_cartas_distintas() -> None:
    assert N_CARDS == 52
    nomes = {card_str(c) for c in range(N_CARDS)}
    assert len(nomes) == 52
    for c in range(N_CARDS):
        assert parse_card(card_str(c)) == c


def test_bijecao_1326_combos() -> None:
    assert N_COMBOS == 1326
    vistos = set()
    for i in range(N_COMBOS):
        a, b = int(COMBO_CARDS[i, 0]), int(COMBO_CARDS[i, 1])
        assert a != b
        assert combo_index(a, b) == i
        assert combo_index(b, a) == i
        vistos.add(frozenset((a, b)))
    assert len(vistos) == 1326


def test_parse_format_combo() -> None:
    i = parse_combo("AhKh")
    assert combo_str(i) == "AhKh"
    assert parse_combo("KhAh") == i


def test_ordem_canonica_maior_carta_primeiro() -> None:
    assert combo_str(parse_combo("2c3d")) == "3d2c"
    # mesmo valor: naipe na ordem s, h, d, c
    assert combo_str(parse_combo("AdAs")) == "AsAd"


@pytest.mark.parametrize("texto", ["AhAh", "Xx", "A", "1h2c", "AhKz"])
def test_rejeita_invalidos(texto: str) -> None:
    with pytest.raises(InvalidCardError):
        parse_combo(texto)
