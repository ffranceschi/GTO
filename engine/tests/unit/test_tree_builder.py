"""T012 — builder de river com regras de No-Limit (spec US3 cenários 1–4)."""

import numpy as np
import pytest

from gto_engine.cards import parse_card
from gto_engine.game.builder import build_tree
from gto_engine.game.config import TreeConfig
from gto_engine.game.tree import InvalidSpotError, Spot
from gto_engine.ranges import Range, parse_range

BOARD = tuple(parse_card(c) for c in ("Ks", "7d", "2c", "Jh", "3s"))


def spot(pot: float = 10.0, stack: float = 50.0, board: tuple[int, ...] = BOARD) -> Spot:
    return Spot(parse_range("22+, AKs"), parse_range("QQ+, AKo"), board, pot, stack)


def ids(tree, node: int) -> list[str]:  # type: ignore[no-untyped-def]
    return [a.id for a in tree.actions(node)]


def test_raiz_oop_check_e_bets() -> None:
    t = build_tree(spot(), TreeConfig.uniform(bets=(0.33, 0.75), raises=(1.0,), max_raises=2))
    assert t.player(t.root) == "oop"
    assert ids(t, t.root) == ["x", "b33", "b75"]


def test_limite_de_raises() -> None:
    t = build_tree(
        spot(stack=1000), TreeConfig.uniform(bets=(0.33, 0.75), raises=(1.0,), max_raises=2)
    )
    n = t.node_at(["b33", "r100", "r100"])
    assert ids(t, n) == ["f", "c"]


def test_threshold_vira_allin() -> None:
    # pote 10, stack 10: bet 75% = 7,5 ≥ 0,67 × 10 ⇒ all-in de 10
    t = build_tree(spot(stack=10), TreeConfig.uniform(bets=(0.33, 0.75), threshold=0.67))
    assert ids(t, t.root) == ["x", "b33", "a"]
    allin = t.actions(t.root)[2]
    assert allin.amount == pytest.approx(10.0)


def test_acima_do_stack_vira_allin_e_unifica() -> None:
    t = build_tree(spot(stack=5), TreeConfig.uniform(bets=(1.0, 2.0), threshold=1.0))
    assert ids(t, t.root) == ["x", "a"]


def test_raise_minimo() -> None:
    # bet 100% = 10; raise 1% do pote após o call seria minúsculo ⇒ ajustado ao mínimo (dobrar)
    t = build_tree(spot(stack=1000), TreeConfig.uniform(bets=(1.0,), raises=(0.01,), max_raises=3))
    n = t.node_at(["b100"])
    r = next(a for a in t.actions(n) if a.kind == "raise")
    # raise para 20 (incremento mínimo = 10)
    assert r.amount == pytest.approx(20.0)


def test_rotulos_pt_br() -> None:
    t = build_tree(spot(), TreeConfig.uniform(bets=(0.75,)))
    labels = [a.label for a in t.actions(t.root)]
    assert labels == ["Check", "Bet 75% (7,5 bb)"]
    n = t.node_at(["b75"])
    assert [a.label for a in t.actions(n)][:2] == ["Fold", "Call (7,5 bb)"]


def test_check_check_e_call_terminam_em_showdown() -> None:
    t = build_tree(spot(), TreeConfig.uniform(bets=(0.5,)))
    assert t.node_kind(t.node_at(["x", "x"])) == "showdown"
    assert t.node_kind(t.node_at(["b50", "c"])) == "showdown"
    assert t.node_kind(t.node_at(["b50", "f"])) == "fold"


@pytest.mark.parametrize(
    ("kwargs", "msg"),
    [
        ({"pot": 0.0}, "pote"),
        ({"pot": 10_001.0}, "pote"),
        ({"stack": -1.0}, "stack"),
        ({"stack": 10_001.0}, "stack"),
        ({"board": BOARD[:2]}, "board"),
        ({"board": (*BOARD[:4], BOARD[0])}, "board"),
    ],
)
def test_spot_invalido(kwargs: dict[str, object], msg: str) -> None:
    with pytest.raises(InvalidSpotError) as exc:
        spot(**kwargs)  # type: ignore[arg-type]
    assert msg in str(exc.value).lower()


def test_range_sem_combos_apos_bloqueios() -> None:
    board = tuple(parse_card(c) for c in ("As", "Ah", "Ad", "8d", "2h"))  # sobra só 1 ás
    with pytest.raises(InvalidSpotError) as exc:
        Spot(parse_range("AA"), parse_range("KK"), board, 10, 50)
    assert "OOP" in str(exc.value)
    del exc
    w = np.zeros(1326)
    with pytest.raises(InvalidSpotError):
        Spot(Range(w), parse_range("KK"), board, 10, 50)
