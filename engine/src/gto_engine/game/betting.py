"""Regras de apostas No-Limit numa street (compartilhadas pelo builder e pela estimativa).

Convenções: valores em bb arredondados a 0,01; `inv` = fichas investidas na street atual por
jogador; `stack` = fichas restantes antes da street (iguais, stack efetivo).
"""

from __future__ import annotations

from dataclasses import dataclass

from gto_engine.game.config import Position, Street, TreeConfig

CENT = 100


def r2(x: float) -> float:
    return round(x + 1e-9, 2)


def fmt_bb(x: float) -> str:
    s = f"{x:.2f}".rstrip("0").rstrip(".")
    return s.replace(".", ",") + " bb"


@dataclass(frozen=True)
class StreetState:
    pot: float  # pote total no início da street (inclui dinheiro morto)
    stack: float  # stack restante de cada jogador no início da street
    inv: tuple[float, float]  # investido na street
    to_act: int  # 0 = OOP, 1 = IP
    n_raises: int
    last_inc: float  # incremento da última aposta/raise (para o raise mínimo)
    first_checked: bool  # OOP deu check no início da street
    can_bet: bool = True  # False quando donk bet está proibida para OOP


@dataclass(frozen=True)
class ActionSpec:
    kind: str  # check | bet | call | raise | fold | allin
    id: str
    amount: float  # bet: valor apostado; raise/allin: total investido na street; call: valor pago
    pot_fraction: float | None
    label: str
    outcome: str  # "continue" | "fold" | "street_end" | "allin_called"
    next_state: StreetState | None


def _pct(f: float) -> int:
    return round(f * 100)


def street_actions(cfg: TreeConfig, street: Street, s: StreetState) -> list[ActionSpec]:
    p = s.to_act
    o = 1 - p
    pos = Position.OOP if p == 0 else Position.IP
    pot_now = r2(s.pot + s.inv[0] + s.inv[1])
    left_p = r2(s.stack - s.inv[p])  # fichas que p ainda tem
    to_call = r2(s.inv[o] - s.inv[p])
    out: list[ActionSpec] = []
    seen: set[float] = set()

    def add_aggr(kind: str, frac: float | None, total_inv: float) -> None:
        # total_inv = investimento total de p na street após a ação
        total_inv = r2(min(total_inv, s.stack))
        is_allin = total_inv >= s.stack - 1e-9
        if total_inv in seen:
            return
        seen.add(total_inv)
        inc = r2(total_inv - s.inv[o])
        ns = StreetState(
            s.pot,
            s.stack,
            (total_inv, s.inv[1]) if p == 0 else (s.inv[0], total_inv),
            o,
            s.n_raises + (1 if kind == "raise" else 0),
            max(inc, s.last_inc),
            s.first_checked,
        )
        if is_allin:
            out.append(
                ActionSpec(
                    "allin", "a", total_inv, frac, f"All-in ({fmt_bb(total_inv)})", "continue", ns
                )
            )
        elif kind == "bet":
            assert frac is not None
            out.append(
                ActionSpec(
                    "bet",
                    f"b{_pct(frac)}",
                    total_inv,
                    frac,
                    f"Bet {_pct(frac)}% ({fmt_bb(total_inv)})",
                    "continue",
                    ns,
                )
            )
        else:
            assert frac is not None
            out.append(
                ActionSpec(
                    "raise",
                    f"r{_pct(frac)}",
                    total_inv,
                    frac,
                    f"Raise {_pct(frac)}% (para {fmt_bb(total_inv)})",
                    "continue",
                    ns,
                )
            )

    if to_call <= 1e-9:
        # sem aposta pendente: check ou bet
        if s.first_checked or p == 0:
            if p == 0:
                nxt = StreetState(s.pot, s.stack, s.inv, 1, s.n_raises, s.last_inc, True, True)
                out.append(ActionSpec("check", "x", 0.0, None, "Check", "continue", nxt))
            else:
                out.append(ActionSpec("check", "x", 0.0, None, "Check", "street_end", None))
        if left_p > 1e-9 and (s.can_bet or p == 1):
            fracs = cfg.bet_sizes.get(street, {}).get(pos, ())
            for f in fracs:
                amount = r2(f * pot_now)
                if amount <= 0:
                    continue
                if amount >= cfg.allin_threshold * left_p or amount >= left_p:
                    amount = left_p
                add_aggr("bet", f, r2(s.inv[p] + amount))
            if cfg.add_allin_action:
                add_aggr("bet", None, s.stack)
        return _sort(out)

    # há aposta pendente: fold, call, raise
    out.append(ActionSpec("fold", "f", 0.0, None, "Fold", "fold", None))
    call_amt = r2(min(to_call, left_p))
    called_allin = s.inv[o] >= s.stack - 1e-9 or call_amt >= left_p - 1e-9
    out.append(
        ActionSpec(
            "call",
            "c",
            call_amt,
            None,
            f"Call ({fmt_bb(call_amt)})",
            "allin_called" if called_allin else "street_end",
            None,
        )
    )
    can_raise = (
        not called_allin and s.n_raises < cfg.max_raises_per_street and left_p - call_amt > 1e-9
    )
    if can_raise:
        pot_after_call = r2(pot_now + to_call)
        min_total = r2(s.inv[o] + max(s.last_inc, to_call))
        for f in cfg.raise_sizes.get(street, {}).get(pos, ()):
            total = r2(s.inv[o] + f * pot_after_call)
            total = max(total, min_total)
            if total - s.inv[p] >= cfg.allin_threshold * left_p or total - s.inv[p] >= left_p:
                total = s.stack
            add_aggr("raise", f, total)
        if cfg.add_allin_action:
            add_aggr("raise", None, s.stack)
    return _sort(out)


_ORDER = {"fold": 0, "check": 0, "call": 1, "bet": 2, "raise": 2, "allin": 3}


def _sort(acts: list[ActionSpec]) -> list[ActionSpec]:
    return sorted(acts, key=lambda a: (_ORDER[a.kind], a.amount))


def initial_state(pot: float, stack: float, oop_can_bet: bool = True) -> StreetState:
    return StreetState(r2(pot), r2(stack), (0.0, 0.0), 0, 0, 0.0, False, oop_can_bet)
