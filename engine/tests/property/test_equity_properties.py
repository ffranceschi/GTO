"""T043 — propriedades da equity (hypothesis): soma 1, simetria, naipes e exato × Monte Carlo."""

from __future__ import annotations

import numpy as np
import pytest
from hypothesis import assume, given, settings
from hypothesis import strategies as st

from gto_engine.cards import COMBO_CARDS, N_COMBOS, combo_index
from gto_engine.equity.request import EquityRequest, InvalidEquityRequestError
from gto_engine.equity.result import EquityResult
from gto_engine.equity.run import run_equity
from gto_engine.ranges import Range

WEIGHTS = st.sampled_from([0.25, 0.5, 1.0])


@st.composite
def spots(draw: st.DrawFn) -> tuple[list[np.ndarray], tuple[int, ...]]:
    """2 ou 3 ranges pequenos (1 a 6 combos, pesos parciais) e um board de river ou turn."""
    board = tuple(draw(st.lists(st.integers(0, 51), min_size=4, max_size=5, unique=True)))
    n = draw(st.integers(2, 3))
    ranges = []
    for _ in range(n):
        w = np.zeros(N_COMBOS)
        for k in draw(st.lists(st.integers(0, N_COMBOS - 1), min_size=1, max_size=6, unique=True)):
            w[k] = draw(WEIGHTS)
        ranges.append(w)
    return ranges, board


def request(ranges: list[np.ndarray], board: tuple[int, ...], **kw: object) -> EquityRequest:
    try:
        return EquityRequest(tuple(Range(w) for w in ranges), board, **kw)  # type: ignore[arg-type]
    except InvalidEquityRequestError:
        assume(False)
        raise


def equities(r: EquityResult) -> list[float]:
    return [p.equity for p in r.participants]


@settings(max_examples=60, deadline=None)
@given(spots())
def test_soma_das_equities_e_1(spot: tuple[list[np.ndarray], tuple[int, ...]]) -> None:
    r = run_equity(request(*spot, method="exact"))
    assert sum(equities(r)) == pytest.approx(1.0, abs=1e-9)
    for p in r.participants:
        assert p.win + p.tie <= 1 + 1e-12 and p.win <= p.equity + 1e-12


@settings(max_examples=40, deadline=None)
@given(spots(), st.randoms(use_true_random=False))
def test_trocar_a_ordem_permuta_os_resultados(spot, rnd) -> None:  # type: ignore[no-untyped-def]
    ranges, board = spot
    order = list(range(len(ranges)))
    rnd.shuffle(order)
    base = equities(run_equity(request(ranges, board, method="exact")))
    perm = equities(run_equity(request([ranges[i] for i in order], board, method="exact")))
    assert perm == pytest.approx([base[i] for i in order], abs=1e-9)


@settings(max_examples=40, deadline=None)
@given(spots(), st.permutations(range(4)))
def test_permutar_naipes_nao_muda_as_equities(spot, suits) -> None:  # type: ignore[no-untyped-def]
    ranges, board = spot

    def card(c: int) -> int:
        return (c // 4) * 4 + suits[c % 4]

    mapped = []
    for w in ranges:
        m = np.zeros(N_COMBOS)
        for k in np.flatnonzero(w):
            a, b = (int(x) for x in COMBO_CARDS[k])
            m[combo_index(card(a), card(b))] = w[k]
        mapped.append(m)
    base = equities(run_equity(request(ranges, board, method="exact")))
    other = equities(run_equity(request(mapped, tuple(card(c) for c in board), method="exact")))
    assert other == pytest.approx(base, abs=1e-9)


@settings(max_examples=15, deadline=None)
@given(spots(), st.integers(0, 2**32))
def test_exato_e_monte_carlo_concordam(spot, seed) -> None:  # type: ignore[no-untyped-def]
    ranges, board = spot
    exact = run_equity(request(ranges, board, method="exact"))
    mc = run_equity(request(ranges, board, method="monte_carlo", target_margin_pp=0.5, seed=seed))
    for e, m in zip(exact.participants, mc.participants, strict=True):
        # 3 margens (IC 95% ⇒ ~1,96σ; 3 margens ≈ 5,9σ) mais folga para margem ≈ 0 (resultado certo)
        assert abs(e.equity - m.equity) <= 3 * m.margin + 1e-9
