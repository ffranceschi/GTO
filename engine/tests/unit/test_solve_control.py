"""T019 — controle cooperativo (research R4)."""

import time

from gto_engine.solver.best_response import exploitability
from gto_engine.solver.dcfr import Progress, solve
from gto_engine.solver.params import SolveParams
from gto_engine.toy_games.leduc import leduc_tree


class Ctl:
    def __init__(self, stop_after_polls: int | None = None, pause_s: float = 0.0) -> None:
        self.polls = 0
        self.stop_after = stop_after_polls
        self.pause_s = pause_s
        self.paused_calls = 0
        self.poll_times: list[float] = []

    def should_stop(self) -> bool:
        self.polls += 1
        self.poll_times.append(time.perf_counter())
        return self.stop_after is not None and self.polls > self.stop_after

    def wait_if_paused(self) -> None:
        if self.pause_s and self.paused_calls == 0:
            self.paused_calls += 1
            time.sleep(self.pause_s)


def test_parar_retorna_estrategia_e_explotabilidade_exata() -> None:
    t = leduc_tree()
    ctl = Ctl(stop_after_polls=3)
    r = solve(t, SolveParams(target_exploitability_pct=0.0, time_limit_s=60), control=ctl)
    assert r.stop_reason == "user_stopped"
    assert r.exploitability_pct == exploitability(t, r.strategy)


def test_blocos_de_200ms() -> None:
    t = leduc_tree()
    ctl = Ctl()
    solve(t, SolveParams(target_exploitability_pct=0.0, time_limit_s=2.0), control=ctl)
    gaps = [b - a for a, b in zip(ctl.poll_times, ctl.poll_times[1:], strict=False)]
    assert gaps and max(gaps) < 0.6  # bloco ~200 ms + medição de explotabilidade


def test_alvo_e_tempo() -> None:
    t = leduc_tree()
    r = solve(t, SolveParams(target_exploitability_pct=5.0, time_limit_s=30))
    assert r.stop_reason == "target_reached" and r.exploitability_pct <= 5.0
    r2 = solve(t, SolveParams(target_exploitability_pct=0.0, time_limit_s=0.5))
    assert r2.stop_reason == "time_limit"


def test_progresso_e_cadencia() -> None:
    t = leduc_tree()
    eventos: list[Progress] = []
    solve(
        t, SolveParams(target_exploitability_pct=0.0, time_limit_s=2.5), on_progress=eventos.append
    )
    assert eventos[0].exploitability_pct is None
    medidos = [e for e in eventos if e.exploitability_pct is not None]
    assert medidos
    # medição pelo menos a cada 2 s
    tempos = sorted({e.exploitability_iteration: e.elapsed_s for e in medidos}.values())
    assert all(b - a <= 2.3 for a, b in zip([0.0, *tempos], tempos, strict=False))


def test_pausa_nao_consome_iteracoes() -> None:
    t = leduc_tree()
    ctl = Ctl(pause_s=0.5)
    t0 = time.perf_counter()
    r = solve(t, SolveParams(max_iterations=50, target_exploitability_pct=0.0), control=ctl)
    assert r.iterations == 50
    assert time.perf_counter() - t0 >= 0.5
