"""Execução do cálculo de equity em blocos com controle cooperativo (research R2–R4)."""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

import numpy as np

from gto_engine.cards import COMBO_CARDS, N_CARDS
from gto_engine.equity.estimate import DEFAULT_RATE, estimate_equity
from gto_engine.equity.exact import completions, hu_chunk, mw_chunk
from gto_engine.equity.montecarlo import mc_block, samples_per_slice
from gto_engine.equity.request import EquityRequest
from gto_engine.equity.result import EquityResult, StopReason, build_participant
from gto_engine.solver.dcfr import NEVER_STOP
from gto_engine.solver.finalize import SolveCancelled

Cancelled = SolveCancelled
EXACT_CHUNKS = 50
# cada lançamento paralelo custa alguns ms (camada workqueue): blocos de ≥ ~1 M avaliações
EVALS_PER_CHUNK = 1_000_000
MAX_REJECTION = 0.99


class EquityError(Exception):
    def __init__(self, code: str, detail: str) -> None:
        super().__init__(detail)
        self.code = code


@dataclass(frozen=True)
class EquityProgress:
    method: str
    elapsed_s: float
    fraction: float | None = None
    samples: float = 0.0
    samples_per_s: float = 0.0
    equities: tuple[float, ...] = ()
    margins: tuple[float, ...] = ()
    target_margin: float = 0.0


def _ignore(_: EquityProgress) -> None:
    return None


def _cancelled(control: Any) -> bool:
    fn = getattr(control, "is_cancelled", None)
    return bool(fn()) if fn is not None else False


def _arrays(req: EquityRequest) -> tuple[list[np.ndarray], list[np.ndarray], list[np.ndarray]]:
    idx, w, c = [], [], []
    for i in range(len(req.participants)):
        ci, wi = req.participant_combos(i)
        idx.append(ci)
        w.append(wi.astype(np.float64))
        c.append(np.ascontiguousarray(COMBO_CARDS[ci].astype(np.int64)))
    return idx, w, c


def run_equity(
    req: EquityRequest,
    control: Any = NEVER_STOP,
    on_progress: Callable[[EquityProgress], None] = _ignore,
    rate: float = DEFAULT_RATE,
) -> EquityResult:
    method = estimate_equity(req, rate).method
    if method == "exact":
        return _exact(req, control, on_progress)
    return _monte_carlo(req, control, on_progress)


def _n_chunks(evals: float, cap: int) -> int:
    return int(max(1, min(cap, EXACT_CHUNKS, evals // EVALS_PER_CHUNK)))


def _exact(
    req: EquityRequest, control: Any, on_progress: Callable[[EquityProgress], None]
) -> EquityResult:
    t0 = time.perf_counter()
    base = np.asarray(req.board, dtype=np.int64)
    avail = np.array([c for c in range(N_CARDS) if c not in req.board], dtype=np.int64)
    comps = completions(avail, 5 - len(req.board))
    idx, w, c = _arrays(req)
    n = len(idx)

    def check() -> None:
        if control.should_stop() and _cancelled(control):  # parar não interrompe o exato (≤ 2 s)
            raise Cancelled()

    if n == 2:
        pos1 = {int(x): j for j, x in enumerate(idx[1])}
        pos0 = {int(x): j for j, x in enumerate(idx[0])}
        same0 = np.array([pos1.get(int(x), -1) for x in idx[0]], dtype=np.int64)
        same1 = np.array([pos0.get(int(x), -1) for x in idx[1]], dtype=np.int64)
        acc0 = np.zeros((len(idx[0]), 4))
        acc1 = np.zeros((len(idx[1]), 4))
        total = comps.shape[0]
        chunks = _n_chunks(total * (len(idx[0]) + len(idx[1])), total)
        bounds = [total * i // chunks for i in range(chunks + 1)]
        for ci in range(chunks):
            check()
            a0, a1 = hu_chunk(
                base, comps, bounds[ci], bounds[ci + 1], c[0], w[0], c[1], w[1], same0, same1
            )
            acc0 += a0
            acc1 += a1
            on_progress(
                EquityProgress("exact", time.perf_counter() - t0, fraction=(ci + 1) / chunks)
            )
        accs = [acc0, acc1]
        evaluated = float(total)
    else:
        maxn = max(len(x) for x in idx)
        cards = np.zeros((n, maxn, 2), dtype=np.int64)
        weights = np.ones((n, maxn))
        counts = np.array([len(x) for x in idx], dtype=np.int64)
        for q in range(n):
            cards[q, : counts[q]] = c[q]
            weights[q, : counts[q]] = w[q]
        acc = np.zeros((n, maxn, 4))
        n0 = int(counts[0])
        chunks = _n_chunks(
            float(comps.shape[0]) * float(np.prod(counts.astype(np.float64))) * n, n0
        )
        bounds = [n0 * i // chunks for i in range(chunks + 1)]
        for ci in range(chunks):
            check()
            acc += mw_chunk(base, comps, cards, weights, counts, bounds[ci], bounds[ci + 1])
            on_progress(
                EquityProgress("exact", time.perf_counter() - t0, fraction=(ci + 1) / chunks)
            )
        accs = [acc[q, : counts[q]] for q in range(n)]
        evaluated = float(comps.shape[0])
    parts = [
        build_participant(idx[q], w[q], accs[q][:, 0], accs[q][:, 1], accs[q][:, 2], accs[q][:, 3])
        for q in range(n)
    ]
    return EquityResult("exact", "exact", evaluated, req.seed, time.perf_counter() - t0, parts)


def _monte_carlo(
    req: EquityRequest, control: Any, on_progress: Callable[[EquityProgress], None]
) -> EquityResult:
    t0 = time.perf_counter()
    base = np.asarray(req.board, dtype=np.int64)
    idx, w, c = _arrays(req)
    n = len(idx)
    maxn = max(len(x) for x in idx)
    cards = np.zeros((n, maxn, 2), dtype=np.int64)
    cum = np.zeros((n, maxn))
    counts = np.array([len(x) for x in idx], dtype=np.int64)
    for q in range(n):
        cards[q, : counts[q]] = c[q]
        cum[q, : counts[q]] = np.cumsum(w[q])
    part = np.zeros((n, 5))
    combo = np.zeros((n, maxn, 5))
    target = req.target_margin_pp / 100.0
    block = 0
    stop_reason: StopReason = "time_limit"
    while True:
        if control.should_stop():
            if _cancelled(control):
                raise Cancelled()
            if part[0, 0] > 0:
                stop_reason = "user_stopped"
                break
        per = samples_per_slice(block)
        p, cb, tries = mc_block(base, cards, cum, counts, np.uint64(req.seed), block, per)
        if p[0, 0] == 0 or 1.0 - p[0, 0] / tries > MAX_REJECTION:
            raise EquityError(
                "confronto_improvavel",
                "Quase todas as combinações sorteadas repetem cartas entre os participantes: "
                "o confronto é improvável demais para a simulação.",
            )
        part += p
        combo += cb
        block += 1
        ns = part[0, 0]
        eq = part[:, 1] / ns
        margins = 1.96 * np.sqrt(np.maximum(part[:, 2] / ns - eq**2, 0.0) / ns)
        el = time.perf_counter() - t0
        on_progress(
            EquityProgress(
                "monte_carlo",
                el,
                None,
                ns,
                ns / el if el else 0.0,
                tuple(float(x) for x in eq),
                tuple(float(x) for x in margins),
                target,
            )
        )
        if np.all(margins <= target):
            stop_reason = "target_reached"
            break
        if el >= req.time_limit_s:
            break
    parts = [
        build_participant(
            idx[q],
            w[q],
            combo[q, : counts[q], 1],
            combo[q, : counts[q], 3],
            combo[q, : counts[q], 4],
            combo[q, : counts[q], 0],
            combo[q, : counts[q], 2],
            totals=(part[q, 0], part[q, 1], part[q, 2], part[q, 3], part[q, 4]),
        )
        for q in range(n)
    ]
    return EquityResult(
        "monte_carlo", stop_reason, float(part[0, 0]), req.seed, time.perf_counter() - t0, parts
    )
