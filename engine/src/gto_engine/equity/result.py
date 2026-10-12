"""Resultado do cálculo de equity (data-model.md)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

import numpy as np

from gto_engine.cards import COMBO_CARDS, RANKS, combo_str

MARGIN_HIGHLIGHT = 0.02  # ±2 pp (FR-023)
StopReason = Literal["exact", "target_reached", "time_limit", "user_stopped"]


@dataclass(frozen=True)
class ComboResult:
    combo: int
    weight: float
    equity: float
    win: float
    tie: float
    margin: float
    samples: float

    @property
    def name(self) -> str:
        return combo_str(self.combo)


@dataclass(frozen=True)
class HandResult:
    hand: str
    combos: float
    equity: float
    win: float
    tie: float
    margin: float
    samples: float

    @property
    def high_margin(self) -> bool:
        return self.margin > MARGIN_HIGHLIGHT


@dataclass(frozen=True)
class ParticipantResult:
    equity: float
    win: float
    tie: float
    margin: float
    combos: list[ComboResult]
    hands: list[HandResult] = field(default_factory=list)


@dataclass(frozen=True)
class EquityResult:
    method: Literal["exact", "monte_carlo"]
    stop_reason: StopReason
    samples: float
    seed: int
    elapsed_s: float
    participants: list[ParticipantResult]


def _safe(num: np.ndarray, den: np.ndarray) -> np.ndarray:
    out: np.ndarray = np.divide(num, den, out=np.zeros_like(num, dtype=np.float64), where=den > 0)
    return out


def combo_hand(index: int) -> str:
    """Célula da grade do combo (AA, AKs, AKo)."""
    hi, lo = (int(x) for x in COMBO_CARDS[index])
    r1, r2 = RANKS[hi // 4], RANKS[lo // 4]
    if r1 == r2:
        return r1 + r2
    return r1 + r2 + ("s" if hi % 4 == lo % 4 else "o")


def _hand_key(hand: str) -> tuple[int, int, int]:
    # ordem da grade: maior rank primeiro, pares, suited antes de offsuit
    return (
        -RANKS.index(hand[0]),
        -RANKS.index(hand[1]),
        0 if len(hand) == 2 or hand[2] == "s" else 1,
    )


def _hands(
    combos: np.ndarray,
    weights: np.ndarray,
    share: np.ndarray,
    win: np.ndarray,
    tie: np.ndarray,
    tot: np.ndarray,
    share2: np.ndarray | None,
) -> list[HandResult]:
    """Agrega os acumuladores dos combos de cada célula (FR-023).

    Exato: médias ponderadas por peso × combinações compatíveis; `samples` = combinações
    compatíveis médias por combo. Monte Carlo: soma das amostras dos combos (os combos já são
    sorteados na proporção peso × compatibilidade), com a margem do IC 95% sobre a soma.
    """
    groups: dict[str, list[int]] = {}
    for i, c in enumerate(combos):
        groups.setdefault(combo_hand(int(c)), []).append(i)
    out: list[HandResult] = []
    for hand in sorted(groups, key=_hand_key):
        ix = np.asarray(groups[hand])
        w = weights[ix]
        n_combos = float(w.sum())
        if share2 is None:
            den = float((w * tot[ix]).sum())

            def avg(
                a: np.ndarray, ix: np.ndarray = ix, w: np.ndarray = w, den: float = den
            ) -> float:
                return float((w * a[ix]).sum() / den) if den else 0.0

            samples = den / n_combos if n_combos else 0.0
            out.append(HandResult(hand, n_combos, avg(share), avg(win), avg(tie), 0.0, samples))
        else:
            n = float(tot[ix].sum())
            if not n:
                out.append(HandResult(hand, n_combos, 0.0, 0.0, 0.0, 0.0, 0.0))
                continue
            eq = float(share[ix].sum()) / n
            var = max(float(share2[ix].sum()) / n - eq * eq, 0.0)
            out.append(
                HandResult(
                    hand,
                    n_combos,
                    eq,
                    float(win[ix].sum()) / n,
                    float(tie[ix].sum()) / n,
                    1.96 * float(np.sqrt(var / n)),
                    n,
                )
            )
    return out


def build_participant(
    combos: np.ndarray,
    weights: np.ndarray,
    share: np.ndarray,
    win: np.ndarray,
    tie: np.ndarray,
    tot: np.ndarray,
    share2: np.ndarray | None = None,
    totals: tuple[float, float, float, float, float] | None = None,
) -> ParticipantResult:
    """Agrega acumuladores por combo. No exato, tot é o peso das combinações; no MC, contagens."""
    eq_c, win_c, tie_c = _safe(share, tot), _safe(win, tot), _safe(tie, tot)
    if share2 is None:
        margin_c = np.zeros_like(eq_c)
    else:
        var = np.maximum(_safe(share2, tot) - eq_c**2, 0.0)
        margin_c = 1.96 * np.sqrt(_safe(var, tot))
    combo_list = [
        ComboResult(int(c), float(w), float(e), float(wi), float(t), float(m), float(n))
        for c, w, e, wi, t, m, n in zip(
            combos, weights, eq_c, win_c, tie_c, margin_c, tot, strict=True
        )
    ]
    if totals is not None:  # Monte Carlo: totais pela amostra (n, Σshare, Σshare², Σwin, Σtie)
        n, s1, s2, w, t = totals
        eq = s1 / n if n else 0.0
        margin = 1.96 * float(np.sqrt(max(s2 / n - eq * eq, 0.0) / n)) if n else 0.0
        hands = _hands(combos, weights, share, win, tie, tot, share2)
        return ParticipantResult(
            eq, w / n if n else 0.0, t / n if n else 0.0, margin, combo_list, hands
        )
    wt = weights * tot
    den = float(wt.sum())
    eq = float((weights * share).sum() / den) if den else 0.0
    return ParticipantResult(
        eq,
        float((weights * win).sum() / den) if den else 0.0,
        float((weights * tie).sum() / den) if den else 0.0,
        0.0,
        combo_list,
        _hands(combos, weights, share, win, tie, tot, None),
    )
