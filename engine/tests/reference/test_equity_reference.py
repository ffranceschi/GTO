"""T010 — referências de equity (REFERENCES.md, seção Equity; Princípio I)."""

from __future__ import annotations

import pytest

from gto_engine.cards import parse_card
from gto_engine.equity.request import EquityRequest
from gto_engine.equity.run import run_equity
from gto_engine.ranges import parse_range
from tests.equity_oracle import brute_force


def board(text: str) -> tuple[int, ...]:
    return tuple(parse_card(c) for c in text.split())


def exact(ranges: list[str], b: str = ""):  # type: ignore[no-untyped-def]
    req = EquityRequest(tuple(parse_range(r) for r in ranges), board(b), method="exact")
    return req, run_equity(req)


def as_dict(req: EquityRequest, i: int) -> dict[int, float]:
    idx, w = req.participant_combos(i)
    return {int(c): float(x) for c, x in zip(idx, w, strict=True)}


def test_aa_vs_kk_preflop() -> None:
    _, r = exact(["AA", "KK"])
    assert r.method == "exact"
    assert r.participants[0].equity == pytest.approx(0.8195, abs=0.001)
    assert r.participants[1].equity == pytest.approx(0.1805, abs=0.001)


def test_board_completo_100pct() -> None:
    _, r = exact(["AsAd", "KsKd"], "2c 7h 9d Jc 3s")
    p = r.participants[0]
    assert (p.equity, p.win, p.tie) == (pytest.approx(1.0), pytest.approx(1.0), pytest.approx(0.0))


CASES = [
    (["AhKh", "QsQd"], "Jh Th 2c"),
    (["AhKh", "QsQd"], "Jh Th 2c 3s"),
    (["AhKh", "QsQd"], "Jh Th 2c 3s 4d"),
    (["7c7d", "AsKc"], "2h 3h 4h"),
    (["8s8h", "JJ, AK"], "Ks 7d 2c"),
    (["AhAd", "KK, QQ, 76s"], "Ks 7d 2c Jh"),
    (["Th9h", "88+"], "8h 7c 2d 4s"),
    (["5s5c", "A5s"], "As 5d 2h 3c"),
    (["AA, KK", "QQ, JJ, AK"], "Qh 7d 2c"),
    (["QJs, T9s", "AA, 77"], "Td 9c 2s 7h"),
]


@pytest.mark.parametrize(("ranges", "b"), CASES)
def test_igual_forca_bruta_phevaluator(ranges: list[str], b: str) -> None:
    req, r = exact(ranges, b)
    oracle = brute_force([as_dict(req, i) for i in range(len(ranges))], board(b))
    for i, (eq, win, tie, per) in enumerate(oracle):
        p = r.participants[i]
        assert (p.equity, p.win, p.tie) == (
            pytest.approx(eq, abs=1e-9),
            pytest.approx(win, abs=1e-9),
            pytest.approx(tie, abs=1e-9),
        )
        got = {c.combo: c.equity for c in p.combos}
        for combo, val in per.items():  # base da distribuição da US3
            assert got[combo] == pytest.approx(val, abs=1e-9)


def test_multiway_por_combo_igual_forca_bruta() -> None:
    ranges = ["AA, KQs", "JJ, T9s", "77, A5s"]
    req, r = exact(ranges, "Ts 9d 2h")
    oracle = brute_force([as_dict(req, i) for i in range(3)], board("Ts 9d 2h"))
    assert sum(p.equity for p in r.participants) == pytest.approx(1.0, abs=1e-9)
    for i, (eq, _win, tie, per) in enumerate(oracle):
        p = r.participants[i]
        assert p.equity == pytest.approx(eq, abs=1e-9) and p.tie == pytest.approx(tie, abs=1e-9)
        got = {c.combo: c.equity for c in p.combos}
        for combo, val in per.items():
            assert got[combo] == pytest.approx(val, abs=1e-9)
