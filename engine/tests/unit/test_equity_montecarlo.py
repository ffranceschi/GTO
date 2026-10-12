"""T012 — Monte Carlo: determinismo, cobertura (SC-005), parada, cancelamento e rejeição."""

from __future__ import annotations

import time

import numba
import pytest

from gto_engine.cards import parse_card
from gto_engine.equity.request import EquityRequest
from gto_engine.equity.run import Cancelled, EquityError, run_equity
from gto_engine.ranges import parse_range

FLOP = tuple(parse_card(c) for c in ["Ks", "7d", "2c"])


def req(ranges: list[str], board: tuple[int, ...] = FLOP, **kw: object) -> EquityRequest:
    kw.setdefault("method", "monte_carlo")
    return EquityRequest(tuple(parse_range(r) for r in ranges), board, **kw)  # type: ignore[arg-type]


def test_mesma_semente_mesmo_resultado_com_1_e_4_threads() -> None:
    outs = []
    for th in (1, min(4, numba.config.NUMBA_NUM_THREADS)):
        numba.set_num_threads(th)
        r = run_equity(req(["QQ+, AK", "JJ-88", "A2s+"], seed=11, target_margin_pp=0.5))
        outs.append(
            (
                r.samples,
                tuple(p.equity for p in r.participants),
                tuple(p.margin for p in r.participants),
            )
        )
    numba.set_num_threads(numba.config.NUMBA_NUM_THREADS)
    assert outs[0] == outs[1]
    assert (
        run_equity(req(["QQ+, AK", "JJ-88"], seed=1, target_margin_pp=0.5)).participants[0].equity
        != run_equity(req(["QQ+, AK", "JJ-88"], seed=2, target_margin_pp=0.5))
        .participants[0]
        .equity
    )


def test_cobertura_da_margem_sc005() -> None:
    ranges = ["QQ+, AK", "JJ-99, AQs"]
    truth = run_equity(req(ranges, method="exact")).participants[0].equity
    hits = 0
    runs = 200
    for seed in range(runs):
        r = run_equity(req(ranges, seed=seed, target_margin_pp=1.0))
        p = r.participants[0]
        hits += abs(p.equity - truth) <= p.margin
    # cobertura real de 95% não é rejeitada a 1%: limite inferior binomial (n = 200) ≈ 183
    assert hits >= 183, hits


def test_parada_por_margem_tempo_e_stop() -> None:
    r = run_equity(req(["AA", "KK"], target_margin_pp=0.5))
    assert r.stop_reason == "target_reached" and all(p.margin <= 0.005 for p in r.participants)
    r2 = run_equity(req(["22+, A2+", "22+, K2+", "QQ+"], target_margin_pp=0.05, time_limit_s=0.02))
    assert (
        r2.stop_reason == "time_limit"
        and r2.method == "monte_carlo"
        and r2.participants[0].margin > 0
    )

    class Stop:
        calls = 0

        def should_stop(self) -> bool:
            self.calls += 1
            return self.calls > 2

        def wait_if_paused(self) -> None:
            return None

    r3 = run_equity(req(["22+, A2+", "QQ+"], target_margin_pp=0.05), control=Stop())
    assert r3.stop_reason == "user_stopped" and r3.samples > 0 and r3.participants[0].margin > 0


def test_cancelamento_em_um_bloco() -> None:
    class Cancel:
        t: float | None = None

        def should_stop(self) -> bool:
            if self.t is None:
                self.t = time.perf_counter()
            return True

        def wait_if_paused(self) -> None:
            return None

        def is_cancelled(self) -> bool:
            return self.t is not None

    c = Cancel()
    with pytest.raises(Cancelled):
        run_equity(req(["22+, A2+", "QQ+"], target_margin_pp=0.05), control=c)
    assert c.t is not None and time.perf_counter() - c.t < 0.5


def test_rejeicao_alta_vira_erro() -> None:
    # os dois ranges têm quase todo o peso em AhAd (nenhum é mão específica, então não há
    # bloqueio prévio): rejeição ≈ 99,8%
    r = req(["AhAd, KsKc:0.001", "AhAd, AsAc:0.001"], board=())
    with pytest.raises(EquityError) as exc:
        run_equity(r)
    assert exc.value.code == "confronto_improvavel"
