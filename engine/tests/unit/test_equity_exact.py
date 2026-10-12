"""T011 — enumeração exata: pesos, multiway (empates 1/k), cartas repetidas e determinismo."""

from __future__ import annotations

import numba
import pytest

from gto_engine.cards import parse_card
from gto_engine.equity.request import EquityRequest
from gto_engine.equity.run import run_equity
from gto_engine.ranges import parse_range

FLOP = tuple(parse_card(c) for c in ["Ks", "7d", "2c"])


def run(ranges: list[str], board: tuple[int, ...] = FLOP):  # type: ignore[no-untyped-def]
    return run_equity(EquityRequest(tuple(parse_range(r) for r in ranges), board, method="exact"))


def test_pesos_parciais_sao_media_ponderada() -> None:
    mixed = run(["AA:0.5, QQ", "JJ"]).participants[0].equity
    aa = run(["AA", "JJ"]).participants[0].equity
    qq = run(["QQ", "JJ"]).participants[0].equity
    # AA tem 6 combos (peso 0,5 ⇒ 3), QQ 6 combos; bloqueios iguais contra JJ
    assert mixed == pytest.approx((3 * aa + 6 * qq) / 9, abs=1e-9)


def test_multiway_empate_divide_e_soma_1() -> None:
    # royal na mesa: todos empatam
    board = tuple(parse_card(c) for c in ["As", "Ks", "Qs", "Js", "Ts"])
    r = run(["22", "33", "44"], board)
    for p in r.participants:
        assert p.equity == pytest.approx(1 / 3) and p.tie == pytest.approx(1.0) and p.win == 0
    r2 = run(["AA", "KK", "QQ", "JJ"])
    assert sum(p.equity for p in r2.participants) == pytest.approx(1.0, abs=1e-9)


def test_combinacoes_com_carta_repetida_excluidas() -> None:
    # AhKh contra range que contém combos com Ah ou Kh: esses combos não entram
    r = run(["AhKh", "AA, KK"])
    combos = {c.combo for c in r.participants[1].combos}
    assert all(
        "h" not in (c[1], c[3]) or ("Ah" not in c and "Kh" not in c) for c in map(_s, combos)
    )


def _s(i: int) -> str:
    from gto_engine.cards import combo_str

    return combo_str(i)


def test_independe_do_numero_de_threads() -> None:
    outs = []
    for th in (1, min(4, numba.config.NUMBA_NUM_THREADS)):
        numba.set_num_threads(th)
        r = run(["QQ+, AK", "JJ-88, AQs"])
        outs.append((r.participants[0].equity, tuple(c.equity for c in r.participants[0].combos)))
    numba.set_num_threads(numba.config.NUMBA_NUM_THREADS)
    assert outs[0] == outs[1]
