"""T033 — distribuição por mão e por combo (US3, FR-023)."""

from __future__ import annotations

import pytest

from gto_engine.cards import parse_card
from gto_engine.equity.request import EquityRequest
from gto_engine.equity.result import MARGIN_HIGHLIGHT, ParticipantResult
from gto_engine.equity.run import run_equity
from gto_engine.ranges import parse_range

FLOP = tuple(parse_card(c) for c in ["Ks", "7d", "2c"])


def req(ranges: list[str], **kw: object) -> EquityRequest:
    return EquityRequest(tuple(parse_range(r) for r in ranges), FLOP, **kw)  # type: ignore[arg-type]


def weighted(p: ParticipantResult) -> float:
    """Média das equities por combo ponderada por peso × combinações compatíveis."""
    num = sum(c.weight * c.samples * c.equity for c in p.combos)
    den = sum(c.weight * c.samples for c in p.combos)
    return num / den


def test_media_ponderada_por_combo_e_por_mao_igual_a_total_no_exato() -> None:
    r = run_equity(req(["QQ+, AKs", "JJ-99"], method="exact"))
    p = r.participants[0]
    assert weighted(p) == pytest.approx(p.equity, abs=0.0005)
    hands = {h.hand: h for h in p.hands}
    # KK perde um combo para o K do board; AKs também (AsKs bloqueado)
    assert set(hands) == {"AA", "KK", "QQ", "AKs"}
    assert hands["AA"].combos == 6 and hands["KK"].combos == 3 and hands["AKs"].combos == 3
    by_combo = sum(h.combos * h.samples * h.equity for h in p.hands) / sum(
        h.combos * h.samples for h in p.hands
    )
    assert by_combo == pytest.approx(p.equity, abs=0.0005)
    assert all(h.margin == 0 for h in p.hands)
    for h in p.hands:
        assert 0 <= h.tie <= 1 and h.win <= h.equity <= h.win + h.tie + 1e-12
    assert hands["KK"].equity > hands["AA"].equity  # trinca no flop K


def test_multiway_3_participantes() -> None:
    r = run_equity(req(["QQ+, AKs", "JJ-99", "AQs, KQs"], method="exact"))
    for p in r.participants:
        assert weighted(p) == pytest.approx(p.equity, abs=0.0005)
        assert sum(h.combos for h in p.hands) == pytest.approx(sum(c.weight for c in p.combos))


def test_monte_carlo_margem_e_amostras_por_mao_e_combo() -> None:
    r = run_equity(
        req(["QQ+, AKs", "JJ-99, AQs", "22+"], method="monte_carlo", target_margin_pp=1.0, seed=3)
    )
    for p in r.participants:
        assert all(c.samples > 0 and c.margin > 0 for c in p.combos)
        assert all(h.samples > 0 and h.margin > 0 for h in p.hands)
        assert sum(h.samples for h in p.hands) == pytest.approx(r.samples)
        # equity agregada da mão = média das amostras dos seus combos
        for h in p.hands:
            assert h.high_margin == (h.margin > MARGIN_HIGHLIGHT)
    # com ±1 pp no total, mãos raras de um range amplo têm margem acima de ±2 pp
    assert any(h.high_margin for h in r.participants[2].hands)
    assert any(c.margin > MARGIN_HIGHLIGHT for c in r.participants[2].combos)
