"""Notação textual de ranges (Princípio VIII): 22+, A2s+, KTo+, 55-22, K9s-K6s, AhKh, AKs:0.5."""

from __future__ import annotations

import re

import numpy as np

from gto_engine.cards import (
    COMBO_CARDS,
    N_COMBOS,
    RANKS,
    InvalidCardError,
    card_rank,
    card_suit,
    combo_str,
    parse_combo,
)
from gto_engine.ranges.range import Range


class RangeNotationError(ValueError):
    def __init__(self, message: str, position: int) -> None:
        super().__init__(message)
        self.position = position


# mão (classe da grade): (rank alto, rank baixo, tipo) com tipo 'p', 's' ou 'o'
Hand = tuple[int, int, str]


def _hand_combos() -> dict[Hand, list[int]]:
    out: dict[Hand, list[int]] = {}
    for i in range(N_COMBOS):
        a, b = int(COMBO_CARDS[i, 0]), int(COMBO_CARDS[i, 1])
        ra, rb = card_rank(a), card_rank(b)
        if ra == rb:
            key: Hand = (ra, rb, "p")
        else:
            key = (ra, rb, "s" if card_suit(a) == card_suit(b) else "o")
        out.setdefault(key, []).append(i)
    return out


HAND_COMBOS = _hand_combos()


def hand_name(h: Hand) -> str:
    hi, lo, k = h
    return RANKS[hi] + RANKS[lo] + ("" if k == "p" else k)


def _r(ch: str) -> int:
    return RANKS.index(ch.upper())


_HAND_RE = re.compile(r"^([AKQJT2-9])([AKQJT2-9])([so]?)$", re.IGNORECASE)


def _parse_hand(tok: str) -> tuple[int, int, str] | None:
    m = _HAND_RE.match(tok)
    if not m:
        return None
    a, b, k = _r(m.group(1)), _r(m.group(2)), m.group(3).lower()
    if a == b:
        return (a, b, "p") if k == "" else None
    hi, lo = max(a, b), min(a, b)
    return (hi, lo, k or "so")


def _expand_kinds(hi: int, lo: int, kind: str) -> list[Hand]:
    if kind == "p":
        return [(hi, lo, "p")]
    return [(hi, lo, k) for k in kind]  # "so" = suited + offsuit


def _expand(tok: str) -> list[int] | None:
    """Combos de um item sem peso; None se inválido."""
    t = tok.strip()
    try:
        return [parse_combo(t)]
    except InvalidCardError:
        pass
    hands: list[Hand] = []
    if "-" in t:
        a_txt, b_txt = t.split("-", 1)
        a, b = _parse_hand(a_txt), _parse_hand(b_txt)
        if not a or not b or a[2] != b[2]:
            return None
        if a[2] == "p":
            lo_r, hi_r = sorted((a[0], b[0]))
            hands = [(r, r, "p") for r in range(lo_r, hi_r + 1)]
        else:
            if a[0] != b[0]:
                return None
            lo_r, hi_r = sorted((a[1], b[1]))
            for r in range(lo_r, hi_r + 1):
                hands += _expand_kinds(a[0], r, a[2])
    elif t.endswith("+"):
        h = _parse_hand(t[:-1])
        if not h:
            return None
        if h[2] == "p":
            hands = [(r, r, "p") for r in range(h[0], 13)]
        else:
            for r in range(h[1], h[0]):
                hands += _expand_kinds(h[0], r, h[2])
    else:
        h = _parse_hand(t)
        if not h:
            return None
        hands = _expand_kinds(*h)
    out: list[int] = []
    for hh in hands:
        out += HAND_COMBOS[hh]
    return out


def parse_range(text: str) -> Range:
    """Converte notação em Range; itens repetidos: vale o último peso."""
    w = np.zeros(N_COMBOS)
    pos = 0
    for raw in text.split(","):
        start = pos + (len(raw) - len(raw.lstrip()))
        pos += len(raw) + 1
        item = raw.strip()
        if not item:
            continue
        weight = 1.0
        body = item
        if ":" in item:
            body, wtxt = item.split(":", 1)
            body = body.strip()
            wtxt = wtxt.strip()
            try:
                weight = float(wtxt[:-1]) / 100 if wtxt.endswith("%") else float(wtxt)
            except ValueError:
                weight = -1.0
            if not 0.0 <= weight <= 1.0:
                raise RangeNotationError(
                    f"Peso inválido em '{item}' (posição {start}): use 0 a 1 ou 0% a 100%.", start
                )
        combos = _expand(body)
        if combos is None:
            raise RangeNotationError(
                f"Notação inválida: '{item}' (posição {start}). Exemplos válidos: "
                "22+, A2s+, KTo+, 55-22, K9s-K6s, AhKh, AKs:0.5.",
                start,
            )
        w[combos] = weight
    return Range(w)


def _fmt_weight(x: float) -> str:
    return repr(float(x))


def _group_pairs(ranks: list[int]) -> list[str]:
    """Pares (ranks ascendentes) → '22+', 'QQ+', '55-22', 'TT'."""
    out: list[str] = []
    runs: list[list[int]] = []
    for r in sorted(ranks):
        if runs and r == runs[-1][-1] + 1:
            runs[-1].append(r)
        else:
            runs.append([r])
    for run in reversed(runs):
        lo, hi = run[0], run[-1]
        if hi == 12 and len(run) > 1:
            out.append(f"{RANKS[lo]}{RANKS[lo]}+")
        elif len(run) == 1:
            out.append(RANKS[lo] * 2)
        else:
            out.append(f"{RANKS[hi]}{RANKS[hi]}-{RANKS[lo]}{RANKS[lo]}")
    return out


def _group_kickers(hi: int, kickers: list[int], kind: str) -> list[str]:
    out: list[str] = []
    runs: list[list[int]] = []
    for r in sorted(kickers):
        if runs and r == runs[-1][-1] + 1:
            runs[-1].append(r)
        else:
            runs.append([r])
    for run in reversed(runs):
        lo, top = run[0], run[-1]
        h = RANKS[hi]
        if top == hi - 1 and len(run) > 1:
            out.append(f"{h}{RANKS[lo]}{kind}+")
        elif len(run) == 1:
            out.append(f"{h}{RANKS[lo]}{kind}")
        else:
            out.append(f"{h}{RANKS[top]}{kind}-{h}{RANKS[lo]}{kind}")
    return out


def format_range(r: Range) -> str:
    """Texto canônico compacto (agrupa com + e intervalos). Ida e volta exata."""
    w = r.weights
    by_weight: dict[float, list[Hand]] = {}
    singles: list[tuple[int, float]] = []
    for h in sorted(HAND_COMBOS, key=lambda x: (-x[0], -x[1], x[2])):
        idx = HAND_COMBOS[h]
        vals = w[idx]
        if np.all(vals == vals[0]):
            if vals[0] > 0:
                by_weight.setdefault(float(vals[0]), []).append(h)
        else:
            singles += [(i, float(w[i])) for i in idx if w[i] > 0]
    parts: list[str] = []
    for weight in sorted(by_weight, reverse=True):
        hands = by_weight[weight]
        suffix = "" if weight == 1.0 else f":{_fmt_weight(weight)}"
        items: list[str] = _group_pairs([h[0] for h in hands if h[2] == "p"])
        for hi in range(12, 0, -1):
            for kind in ("s", "o"):
                ks = [h[1] for h in hands if h[0] == hi and h[2] == kind]
                if ks:
                    items += _group_kickers(hi, ks, kind)
        parts += [it + suffix for it in items]
    for i, weight in singles:
        parts.append(combo_str(i) + ("" if weight == 1.0 else f":{_fmt_weight(weight)}"))
    return ", ".join(parts)
