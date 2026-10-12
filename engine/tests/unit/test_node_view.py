"""T049 — node_view na raiz e em nós de decisão do river (FR-018 a FR-020)."""

from __future__ import annotations

import numpy as np
import pytest

from gto_engine.analysis.node_view import node_view
from gto_engine.cards import parse_card
from gto_engine.game.builder import build_tree
from gto_engine.game.config import TreeConfig
from gto_engine.game.tree import Spot
from gto_engine.io.solution_dir import solution_from_result
from gto_engine.ranges import parse_range
from gto_engine.solver.dcfr import solve
from gto_engine.solver.params import SolveParams
from gto_engine.solver.strategy import node_strategy

BOARD = tuple(parse_card(c) for c in ("Ks", "7d", "2c", "Jh", "3s"))


@pytest.fixture(scope="module")
def solved():  # type: ignore[no-untyped-def]
    spot = Spot(
        parse_range("AA, KK, 77, AK, KQs:0.5, QJs, T9s"),
        parse_range("QQ+, AK, KJ, 76s"),
        BOARD,
        10,
        30,
    )
    cfg = TreeConfig.uniform(bets=(0.5, 1.0), raises=(1.0,), max_raises=2)
    tree = build_tree(spot, cfg)
    params = SolveParams(max_iterations=200, target_exploitability_pct=0.0)
    r = solve(tree, params)
    return tree, solution_from_result(tree, spot, cfg, params, r)


def test_raiz_agregados(solved) -> None:  # type: ignore[no-untyped-def]
    tree, sol = solved
    v = node_view(tree, sol, [])
    assert v.kind == "decision" and v.player == "oop"
    assert [a.id for a in v.actions] == ["x", "b50", "b100"]
    assert [a.label for a in v.actions] == ["Check", "Bet 50% (5 bb)", "Bet 100% (10 bb)"]
    sig = node_strategy(tree, sol.strategy, tree.root)
    w = tree.players.weights[0]
    for i, a in enumerate(v.actions):
        assert a.aggregate_frequency == pytest.approx(float((w * sig[i]).sum() / w.sum()), abs=1e-6)
        assert a.combos == pytest.approx(float((w * sig[i]).sum()), abs=1e-6)
    assert sum(a.aggregate_frequency for a in v.actions) == pytest.approx(1.0, abs=1e-5)
    assert v.pot == 10 and v.stacks == {"oop": 30, "ip": 30}


def test_celulas_e_combos(solved) -> None:  # type: ignore[no-untyped-def]
    tree, sol = solved
    v = node_view(tree, sol, [])
    hands = {h.hand: h for h in v.hands}
    assert hands["KQs"].combos == pytest.approx(1.5)  # 3 combos (KsQs bloqueado) × 0,5
    assert hands["AA"].combos == pytest.approx(6)
    aa = [c for c in v.combos if c.combo.startswith("A") and c.combo[2] == "A"]
    assert len(aa) == 6
    ev_mean = np.average([c.ev_bb for c in aa], weights=[c.reach_weight for c in aa])
    assert hands["AA"].ev_bb == pytest.approx(ev_mean, abs=1e-6)
    assert sum(hands["AA"].frequencies.values()) == pytest.approx(1.0, abs=1e-5)


def test_reach_zero_fica_fora_do_range(solved) -> None:  # type: ignore[no-untyped-def]
    tree, sol = solved
    # força uma mão a nunca apostar 100% e verifica o nó seguinte
    sig = node_strategy(tree, sol.strategy, tree.root)
    v = node_view(tree, sol, ["b100"])
    assert v.player == "ip"
    oop = next(r for r in v.ranges if r.player == "oop")
    zero = [i for i, s in enumerate(sig[2]) if s == 0]
    for i in zero:
        assert oop.weights[int(tree.players.hands[0][i])] == 0
    for h in v.hands:
        if h.combos == 0:
            assert h.frequencies == {}
    assert all(c.reach_weight >= 0 for c in v.combos)


def test_terminal_e_caminho_invalido(solved) -> None:  # type: ignore[no-untyped-def]
    tree, sol = solved
    v = node_view(tree, sol, ["x", "x"])
    assert v.kind == "terminal" and v.terminal == "showdown"
    from gto_engine.game.tree import InvalidPathError

    with pytest.raises(InvalidPathError):
        node_view(tree, sol, ["b33"])
    assert node_view(tree, sol, ["b50"]).breadcrumb == ["Bet 50% (5 bb)"]
