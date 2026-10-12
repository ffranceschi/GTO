"""T077 — opções do builder: all-in extra e donk bet."""

from __future__ import annotations

import pytest

from gto_engine.cards import parse_card
from gto_engine.game.builder import build_tree
from gto_engine.game.config import TreeConfig
from gto_engine.game.tree import Spot
from gto_engine.ranges import parse_range

RIVER = tuple(parse_card(c) for c in ("Ks", "7d", "2c", "Jh", "3s"))
FLOP = RIVER[:3]


def spot(board: tuple[int, ...] = RIVER, stack: float = 50) -> Spot:
    return Spot(parse_range("AA, KK, AK"), parse_range("QQ, AQ"), board, 10, stack)


def ids(t, n: int) -> list[str]:  # type: ignore[no-untyped-def]
    return [a.id for a in t.actions(n)]


def test_allin_extra() -> None:
    t = build_tree(spot(), TreeConfig.uniform(bets=(0.5,), raises=(1.0,), add_allin=True))
    assert ids(t, t.root) == ["x", "b50", "a"]
    assert t.actions(t.root)[2].amount == pytest.approx(50)
    raises = ids(t, t.node_at(["b50"]))
    assert raises[-1] == "a" and raises.count("a") == 1


def test_allin_extra_nao_duplica_quando_coincide() -> None:
    t = build_tree(spot(stack=5), TreeConfig.uniform(bets=(1.0,), add_allin=True))
    assert ids(t, t.root) == ["x", "a"]


def test_sem_allin_extra() -> None:
    t = build_tree(spot(), TreeConfig.uniform(bets=(0.5,), add_allin=False))
    assert "a" not in ids(t, t.root)


@pytest.mark.parametrize(("donk", "has_bet"), [(False, False), (True, True)])
def test_donk_depois_de_aposta_do_ip(donk: bool, has_bet: bool) -> None:
    t = build_tree(spot(FLOP, 100), TreeConfig.uniform(bets=(0.5,), max_raises=0, donk=donk))
    turn_root = t.children(t.node_at(["x", "b50", "c"]))[0]
    assert any(a.kind == "bet" for a in t.actions(turn_root)) is has_bet
