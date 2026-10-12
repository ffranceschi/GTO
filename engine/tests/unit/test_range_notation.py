"""T010 — notação de ranges (Princípios IV e VIII)."""

import numpy as np
import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from gto_engine.cards import N_COMBOS, parse_card, parse_combo
from gto_engine.ranges import Range, RangeNotationError, format_range, parse_range


@pytest.mark.parametrize(
    ("texto", "combos"),
    [
        ("22+, A2s+, KTo+", 162),
        ("QQ", 6),
        ("55-22", 24),
        ("AK", 16),
        ("K9s-K6s", 16),
        ("AhKh", 1),
        ("AKs", 4),
        ("AKo", 12),
        ("22+", 78),
    ],
)
def test_contagens(texto: str, combos: int) -> None:
    assert parse_range(texto).combo_count() == pytest.approx(combos)


def test_pesos() -> None:
    assert parse_range("KQo:0.5").combo_count() == pytest.approx(6)
    assert parse_range("KQo:50%").combo_count() == pytest.approx(6)


def test_repetido_mantem_ultimo_peso() -> None:
    r = parse_range("AKs:0.5, AKs")
    assert r.combo_count() == pytest.approx(4)
    r = parse_range("AKs, AKs:0.25")
    assert r.combo_count() == pytest.approx(1)


def test_bloqueio_do_board() -> None:
    r = parse_range("AA")
    dead = [parse_card(c) for c in ("As", "7d", "2c")]
    assert r.combo_count(dead) == pytest.approx(3)


def test_erro_com_posicao() -> None:
    with pytest.raises(RangeNotationError) as exc:
        parse_range("AKx, 33++")
    assert exc.value.position == 0
    assert "AKx" in str(exc.value)
    with pytest.raises(RangeNotationError) as exc2:
        parse_range("AKs, 33++")
    assert exc2.value.position == 5


def test_canonico_compacto() -> None:
    assert format_range(parse_range("22+, A2s+, KTo+")) == "22+, A2s+, KTo+"
    assert format_range(parse_range("AhKh")) == "AhKh"


pesos = st.sampled_from([0.0, 0.25, 0.5, 1.0])


@settings(max_examples=200, deadline=None)
@given(st.lists(st.tuples(st.integers(0, N_COMBOS - 1), pesos), max_size=60))
def test_ida_e_volta(itens: list[tuple[int, float]]) -> None:
    w = np.zeros(N_COMBOS)
    for i, p in itens:
        w[i] = p
    r = Range(w)
    texto = format_range(r)
    r2 = parse_range(texto)
    np.testing.assert_allclose(r2.weights, r.weights)
    assert format_range(r2) == texto


def test_combo_especifico_parse() -> None:
    r = parse_range("AhKh")
    assert r.weights[parse_combo("AhKh")] == 1.0
