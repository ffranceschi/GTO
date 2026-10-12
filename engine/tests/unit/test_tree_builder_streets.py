"""T066 — builder multi-street: chance, runouts de all-in, stack 0, donk e estimativa."""

from __future__ import annotations

import pytest

from gto_engine.cards import parse_card
from gto_engine.game.builder import build_tree
from gto_engine.game.config import TreeConfig
from gto_engine.game.estimate import estimate_tree
from gto_engine.game.tree import Spot
from gto_engine.ranges import parse_range
from gto_engine.solver.arrays import allocate_solver_arrays
from tests.conftest import load_spot

FULL = "22+, A2+, K2+, Q2+, J2+, T2+, 92+, 82+, 72+, 62+, 52+, 42+, 32"
TURN = tuple(parse_card(c) for c in ("Ks", "7d", "2c", "Jh"))
FLOP = tuple(parse_card(c) for c in ("Ks", "7d", "2c"))


def turn_spot(
    stack: float = 50, oop: str = "AA, KK, 77, AK, KQs, QJs, T9s", ip: str = "QQ+, AK, KJ, 76s"
) -> Spot:
    return Spot(parse_range(oop), parse_range(ip), TURN, 10, stack)


def test_chance_do_turn_para_o_river() -> None:
    t = build_tree(turn_spot(), TreeConfig.uniform(bets=(0.5,), max_raises=1))
    n = t.node_at(["x", "x"])
    assert t.node_kind(n) == "chance"
    kids = t.children(n)
    assert len(kids) == 48  # board com 4 naipes: sem simetria
    assert t.node_kind(kids[0]) == "decision" and t.player(kids[0]) == "oop"
    assert t.street_of(kids[0]) == "river"


def test_allin_chamado_vai_direto_aos_runouts() -> None:
    t = build_tree(turn_spot(stack=10), TreeConfig.uniform(bets=(1.0,), threshold=0.67))
    n = t.node_at(["a", "c"])
    assert t.node_kind(n) == "chance"
    assert all(t.node_kind(c) == "showdown" for c in t.children(n))


def test_stack_zero_showdown_direto() -> None:
    t = build_tree(turn_spot(stack=0), TreeConfig.uniform())
    assert t.node_kind(t.root) == "chance"
    assert all(t.node_kind(c) == "showdown" for c in t.children(t.root))


@pytest.mark.parametrize(("donk", "has_bet"), [(False, False), (True, True)])
def test_donk(donk: bool, has_bet: bool) -> None:
    spot = Spot(parse_range("AA, KK, AK"), parse_range("QQ, AQ"), FLOP, 10, 100)
    t = build_tree(spot, TreeConfig.uniform(bets=(0.5,), raises=(1.0,), max_raises=1, donk=donk))
    chance = t.node_at(["x", "b50", "c"])  # IP apostou, OOP pagou ⇒ IP é o agressor
    turn_root = t.children(chance)[0]
    kinds = {a.kind for a in t.actions(turn_root)}
    assert ("bet" in kinds) is has_bet
    # sem agressão do IP (check-check) OOP pode apostar
    t2 = t.children(t.node_at(["x", "x"]))[0]
    assert "bet" in {a.kind for a in t.actions(t2)}


@pytest.mark.slow
@pytest.mark.parametrize("fixture", ["turn_reference.json", "flop_reference.json"])
def test_estimativa_15pct(fixture: str) -> None:
    spot, cfg = load_spot(fixture)
    est = estimate_tree(spot, cfg)
    tree = build_tree(spot, cfg)
    assert est.decision_nodes == tree.n_decision_nodes
    alocado = allocate_solver_arrays(tree).nbytes
    tabelas = sum(a.nbytes for a in (*tree.strengths, *tree.orders))
    assert est.estimated_bytes == pytest.approx(alocado * 1.2 + tabelas, rel=0.15)


def test_fator_de_isomorfismo_monotone() -> None:
    mono = tuple(parse_card(c) for c in ("Ks", "7s", "2s"))
    spot = Spot(parse_range(FULL), parse_range(FULL), mono, 10, 50)
    est = estimate_tree(spot, TreeConfig.uniform(bets=(0.66,), max_raises=1))
    assert est.isomorphism_factor > 1.5
    rainbow = estimate_tree(
        Spot(parse_range(FULL), parse_range(FULL), FLOP, 10, 50),
        TreeConfig.uniform(bets=(0.66,), max_raises=1),
    )
    assert rainbow.isomorphism_factor == 1.0
    assert est.decision_nodes < rainbow.decision_nodes
