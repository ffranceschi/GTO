"""T067 — navegação em node_view com cartas; equity de turn/flop vs força bruta (Princípio I)."""

from __future__ import annotations

import itertools

import pytest
from phevaluator import evaluate_cards

from gto_engine.analysis.node_view import node_view
from gto_engine.cards import card_str, combo_str, parse_card, parse_combo
from gto_engine.game.builder import build_tree
from gto_engine.game.config import TreeConfig
from gto_engine.game.tree import InvalidPathError, Spot
from gto_engine.io.solution_dir import solution_from_result
from gto_engine.ranges import parse_range
from gto_engine.solver.dcfr import solve
from gto_engine.solver.params import SolveParams

TURN = tuple(parse_card(c) for c in ("Ks", "7d", "2c", "Jh"))
FLOP = tuple(parse_card(c) for c in ("Ks", "7d", "2c"))
OOP = "AA, KK, 77, AK, KQs, QJs, T9s"  # ~20 combos depois dos bloqueios
IP = "QQ+, AK, KJ, 76s"


def solved(board: tuple[int, ...], cfg: TreeConfig, iters: int = 60):  # type: ignore[no-untyped-def]
    spot = Spot(parse_range(OOP), parse_range(IP), board, 10, 30)
    tree = build_tree(spot, cfg)
    params = SolveParams(max_iterations=iters, target_exploitability_pct=0.0)
    return tree, solution_from_result(tree, spot, cfg, params, solve(tree, params))


@pytest.fixture(scope="module")
def turn():  # type: ignore[no-untyped-def]
    return solved(TURN, TreeConfig.uniform(bets=(0.75,), raises=(1.0,), max_raises=1))


@pytest.fixture(scope="module")
def flop():  # type: ignore[no-untyped-def]
    return solved(FLOP, TreeConfig.uniform(bets=(0.66,), raises=(1.0,), max_raises=0), iters=20)


def test_caminho_com_carta_e_ranges_que_chegam(turn) -> None:  # type: ignore[no-untyped-def]
    tree, sol = turn
    v = node_view(tree, sol, ["x", "b75", "c", "Kh", "x"])
    assert v.kind == "decision" and v.player == "ip"
    assert v.breadcrumb == ["Check", "Bet 75% (7,5 bb)", "Call (7,5 bb)", "Kh", "Check"]
    # ranges = pesos × produto das frequências ao longo do caminho
    root = node_view(tree, sol, [])
    after_x = node_view(tree, sol, ["x"])
    ip_bet = {c.combo: c.frequencies.get("b75", 0.0) for c in after_x.combos}
    oop_x = {c.combo: c.frequencies["x"] for c in root.combos}
    oop_call = {
        c.combo: c.frequencies.get("c", 0.0) for c in node_view(tree, sol, ["x", "b75"]).combos
    }
    river_oop = node_view(tree, sol, ["x", "b75", "c", "Kh"])
    oop_x2 = {c.combo: c.frequencies.get("x", 0.0) for c in river_oop.combos}
    w_oop = next(r for r in v.ranges if r.player == "oop").weights
    for combo, fx in oop_x.items():
        i = parse_combo(combo)
        blocked = "Kh" in (combo[:2], combo[2:])
        want = 0.0 if blocked else fx * oop_call[combo] * oop_x2.get(combo, 0.0)
        assert w_oop[i] == pytest.approx(want, abs=1e-6)
    w_ip = next(r for r in v.ranges if r.player == "ip").weights
    for combo, fb in ip_bet.items():
        blocked = "Kh" in (combo[:2], combo[2:])
        assert w_ip[parse_combo(combo)] == pytest.approx(0.0 if blocked else fb, abs=1e-6)


def test_chance_terminal_e_erros(turn) -> None:  # type: ignore[no-untyped-def]
    tree, sol = turn
    ch = node_view(tree, sol, ["x", "x"])
    assert ch.kind == "chance" and len(ch.next_cards) == 48
    assert not set(ch.next_cards) & {"Ks", "7d", "2c", "Jh"}
    term = node_view(tree, sol, ["b75", "f"])
    assert term.kind == "terminal" and term.terminal == "fold"
    assert node_view(tree, sol, ["x", "x", "As", "x", "x"]).terminal == "showdown"
    with pytest.raises(InvalidPathError) as exc:
        node_view(tree, sol, ["x", "x", "Ks"])
    assert "não" in str(exc.value)


def _brute(hand: str, board: tuple[int, ...], opp: dict[str, float]) -> float:
    hc = {parse_card(hand[:2]), parse_card(hand[2:])}
    rest = [c for c in range(52) if c not in hc and c not in board]
    num = den = 0.0
    for extra in itertools.combinations(rest, 5 - len(board)):
        full = [card_str(c) for c in (*board, *extra)]
        mine = evaluate_cards(hand[:2], hand[2:], *full)
        for o, w in opp.items():
            if w == 0:
                continue
            oc = {parse_card(o[:2]), parse_card(o[2:])}
            if oc & hc or oc & set(extra):
                continue
            theirs = evaluate_cards(o[:2], o[2:], *full)
            num += w * (1.0 if mine < theirs else 0.5 if mine == theirs else 0.0)
            den += w
    return num / den


@pytest.mark.parametrize("which", ["turn", "flop"])
def test_equity_forca_bruta(which: str, request: pytest.FixtureRequest) -> None:
    tree, sol = request.getfixturevalue(which)
    board = TURN if which == "turn" else FLOP
    v = node_view(tree, sol, ["x"])  # IP depois do check de OOP
    w_oop = next(r for r in v.ranges if r.player == "oop").weights
    opp = {combo_str(i): w for i, w in enumerate(w_oop) if w > 0}
    checked = [c for c in v.combos if c.reach_weight > 0][:4]
    assert checked
    for c in checked:
        assert c.equity == pytest.approx(_brute(c.combo, board, opp), abs=1e-6)


def test_resultado_esperado_no_terminal(turn) -> None:  # type: ignore[no-untyped-def]
    tree, sol = turn
    fold = node_view(tree, sol, ["b75", "f"])
    res = {r.player: r for r in fold.terminal_results}
    assert all(
        c.ev_bb == pytest.approx(10 + 0) for c in res["oop"].combos
    )  # IP desistiu: OOP leva o pote
    sd = node_view(tree, sol, ["x", "x", "As", "x", "x"])
    oop = {r.player: r for r in sd.terminal_results}["oop"]
    assert oop.combos and all(0 <= c.equity <= 1 for c in oop.combos)
    assert all(c.ev_bb == pytest.approx(c.equity * 10, abs=1e-6) for c in oop.combos)
