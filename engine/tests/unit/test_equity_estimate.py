"""T013 — estimativa do custo exato e escolha do método (research R4, FR-016)."""

from __future__ import annotations

import pytest

from gto_engine.cards import parse_card
from gto_engine.equity.estimate import DEFAULT_RATE, estimate_equity
from gto_engine.equity.request import EquityRequest
from gto_engine.ranges import parse_range

FULL = "22+, A2+, K2+, Q2+, J2+, T2+, 92+, 82+, 72+, 62+, 52+, 42+, 32"


def req(ranges: list[str], board: str = "", method: str = "auto") -> EquityRequest:
    return EquityRequest(
        tuple(parse_range(r) for r in ranges),
        tuple(parse_card(c) for c in board.split()),
        method=method,  # type: ignore[arg-type]
    )


def test_contagem_heads_up() -> None:
    e = estimate_equity(req(["AhKh", "QsQd"], "Jh Th 2c"))
    # completações do board com as 49 cartas fora do board: C(49,2) = 1176 boards × 2 mãos
    assert e.exact_evaluations == 1176 * 2


@pytest.mark.parametrize(
    ("ranges", "board", "method"),
    [
        (["AA", "KK"], "", "exact"),
        ([FULL, FULL], "Ks 7d 2c", "exact"),  # SC-002
        ([FULL, FULL], "Ks 7d 2c Jh 3s", "exact"),  # HU no river
        ([FULL] * 6, "", "monte_carlo"),
        ([FULL] * 4, "Ks 7d 2c Jh 3s", "monte_carlo"),  # multiway amplo no river
    ],
)
def test_auto(ranges: list[str], board: str, method: str) -> None:
    assert estimate_equity(req(ranges, board), DEFAULT_RATE).method == method


def test_forcado() -> None:
    assert estimate_equity(req([FULL] * 6, method="exact")).method == "exact"
    assert estimate_equity(req(["AA", "KK"], method="monte_carlo")).method == "monte_carlo"
