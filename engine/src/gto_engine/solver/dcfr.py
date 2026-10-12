"""Loop do solve em blocos com controle cooperativo (research R4)."""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Literal, Protocol

import numpy as np

from gto_engine.game.tree import GameTree
from gto_engine.solver.arrays import allocate_solver_arrays
from gto_engine.solver.best_response import exploitability
from gto_engine.solver.finalize import SolveCancelled
from gto_engine.solver.finalize import finalize as finalize_solution
from gto_engine.solver.kernels import normalize_inplace, run_iterations
from gto_engine.solver.params import SolveParams, default_time_limit

StopReason = Literal["target_reached", "time_limit", "user_stopped"]
BLOCK_TARGET_S = 0.2
MAX_MEASURE_INTERVAL_S = 2.0
MEASURE_COST_FRACTION = 0.10


class SolveControl(Protocol):
    """Controle cooperativo; `is_cancelled()` (opcional) distingue cancelar de parar."""

    def should_stop(self) -> bool: ...
    def wait_if_paused(self) -> None: ...


class _NeverStop:
    def should_stop(self) -> bool:
        return False

    def wait_if_paused(self) -> None:
        return None


NEVER_STOP: SolveControl = _NeverStop()


@dataclass(frozen=True)
class Progress:
    iteration: int
    exploitability_pct: float | None
    exploitability_iteration: int | None
    elapsed_s: float
    iterations_per_s: float
    phase: Literal["running", "finalizing"] = "running"
    finalize_fraction: float | None = None


ProgressSink = Callable[[Progress], None]


def ignore(_: Progress) -> None:
    return None


@dataclass
class SolveResult:
    strategy: np.ndarray  # estratégia média normalizada (float32, layout da árvore)
    iterations: int
    exploitability_pct: float
    stop_reason: StopReason
    elapsed_s: float
    history: np.ndarray = field(default_factory=lambda: np.zeros((0, 3)))  # (iteração, s, %)
    target_reached: bool = False
    ev: np.ndarray | None = None  # float32 por combo do jogador da vez em cada nó de decisão
    equity: np.ndarray | None = None
    peak_train_bytes: int = 0
    peak_finalize_bytes: int = 0


def _algo(params: SolveParams) -> tuple[int, float, float, float]:
    if params.algorithm == "cfr_plus":
        return 1, 0.0, 0.0, 0.0
    if params.algorithm == "linear_cfr":
        return 0, 1.0, 1.0, 1.0
    return 0, params.alpha, params.beta, params.gamma


def solve(
    tree: GameTree,
    params: SolveParams,
    control: SolveControl = NEVER_STOP,
    on_progress: ProgressSink = ignore,
    finalize: bool = True,
) -> SolveResult:
    """Treina até o alvo/tempo/parada e finaliza (EV, equity). Cancelar levanta SolveCancelled."""
    T = tree.kernel
    arrays = allocate_solver_arrays(tree)
    algo, alpha, beta, gamma = _algo(params)
    time_limit = (
        params.time_limit_s if params.time_limit_s is not None else default_time_limit(tree.street)
    )
    max_it = params.max_iterations

    # compila/aquece os kernels antes de começar a medir (a 1ª chamada pode compilar)
    run_iterations(T, arrays.regrets, arrays.strategy_sum, 1, 0, alpha, beta, gamma, algo)
    exploitability(tree, arrays.strategy_sum)

    t0 = time.perf_counter()
    paused_total = 0.0

    def elapsed() -> float:
        return time.perf_counter() - t0 - paused_total

    it = 0
    k = 1
    history: list[tuple[int, float, float]] = []
    last_expl: float | None = None
    last_expl_it: int | None = None
    last_measure = 0.0
    measure_cost = 0.0
    stop_reason: StopReason = "time_limit"
    on_progress(Progress(0, None, None, 0.0, 0.0))

    while True:
        p0 = time.perf_counter()
        control.wait_if_paused()
        paused_total += time.perf_counter() - p0
        if control.should_stop():
            stop_reason = "user_stopped"
            break
        if max_it is not None and it >= max_it:
            stop_reason = "time_limit"  # sem alvo atingido: limite de iterações conta como limite
            break
        kk = k if max_it is None else min(k, max_it - it)
        b0 = time.perf_counter()
        run_iterations(T, arrays.regrets, arrays.strategy_sum, it + 1, kk, alpha, beta, gamma, algo)
        dt = time.perf_counter() - b0
        it += kk
        if dt > 0:
            k = max(1, min(k * 4, int(k * BLOCK_TARGET_S / dt) or 1))
        now = elapsed()
        interval = min(MAX_MEASURE_INTERVAL_S, measure_cost / MEASURE_COST_FRACTION)
        if now - last_measure >= interval or (max_it is not None and it >= max_it):
            m0 = time.perf_counter()
            last_expl = exploitability(tree, arrays.strategy_sum)  # normaliza ao ler, sem cópia
            measure_cost = time.perf_counter() - m0
            last_expl_it = it
            last_measure = elapsed()
            history.append((it, last_measure, last_expl))
        e = elapsed()
        on_progress(Progress(it, last_expl, last_expl_it, e, it / e if e > 0 else 0.0))
        if (
            last_expl is not None
            and last_expl_it == it
            and last_expl <= params.target_exploitability_pct
        ):
            stop_reason = "target_reached"
            break
        if e >= time_limit:
            stop_reason = "time_limit"
            break

    if getattr(control, "is_cancelled", lambda: False)():
        raise SolveCancelled()
    peak_train = arrays.nbytes
    strategy = arrays.strategy_sum
    normalize_inplace(T, strategy)  # no mesmo buffer
    arrays.regrets = np.zeros(0, dtype=np.float32)  # libera os regrets antes da finalização
    final = exploitability(tree, strategy)
    if not history or history[-1][0] != it:
        history.append((it, elapsed(), final))
    reached = final <= params.target_exploitability_pct
    ev = eq = None
    peak_final = int(strategy.nbytes)
    if finalize:
        t_fin = elapsed()

        def fraction(f: float) -> None:
            e2 = elapsed()
            on_progress(
                Progress(it, final, it, e2, it / t_fin if t_fin > 0 else 0.0, "finalizing", f)
            )

        ev, eq = finalize_solution(tree, strategy, control, fraction)
        peak_final = int(strategy.nbytes + ev.nbytes + eq.nbytes)
    return SolveResult(
        strategy,
        it,
        final,
        stop_reason,
        elapsed(),
        np.array(history, dtype=np.float64),
        reached,
        ev,
        eq,
        peak_train,
        peak_final,
    )
