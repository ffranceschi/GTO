"""T065 — isomorfismo de naipes (research R5)."""

from __future__ import annotations

import numpy as np
import pytest

from gto_engine.cards import N_COMBOS, parse_card, parse_combo
from gto_engine.game.isomorphism import (
    SUIT_PERMS,
    chance_orbits,
    permute_card,
    permute_combo,
    symmetry_group,
)
from gto_engine.ranges import parse_range

FULL = parse_range("22+, A2+, K2+, Q2+, J2+, T2+, 92+, 82+, 72+, 62+, 52+, 42+, 32").weights


def board(*cs: str) -> tuple[int, ...]:
    return tuple(parse_card(c) for c in cs)


def test_24_permutacoes_e_aplicacao() -> None:
    assert len(SUIT_PERMS) == 24 and SUIT_PERMS[0] == (0, 1, 2, 3)
    k = SUIT_PERMS.index((1, 0, 2, 3))  # troca s <-> h
    assert permute_card(parse_card("As"), k) == parse_card("Ah")
    assert permute_combo(parse_combo("AsKd"), k) == parse_combo("AhKd")


@pytest.mark.parametrize(
    ("cards", "size"),
    [
        (("Ks", "7d", "2c"), 1),  # rainbow: grupo trivial
        (("Ks", "Js", "2d"), 2),  # two-tone: troca h <-> c
        (("Ks", "7s", "2s"), 6),  # monotone: permuta h, d, c
    ],
)
def test_grupo_fixa_board_e_ranges(cards: tuple[str, ...], size: int) -> None:
    g = symmetry_group(board(*cards), [FULL, FULL])
    assert len(g) == size and 0 in g
    for k in g:
        assert {permute_card(c, k) for c in board(*cards)} == set(board(*cards))
        perm = np.array([permute_combo(i, k) for i in range(N_COMBOS)])
        np.testing.assert_array_equal(FULL[perm], FULL)


def test_peso_diferente_num_naipe_quebra_a_simetria() -> None:
    w = FULL.copy()
    w[parse_combo("AhKh")] = 0.5
    g = symmetry_group(board("Ks", "7s", "2s"), [w, FULL])
    assert len(g) == 2  # só s e h fixos; troca d <-> c
    for k in g:
        assert SUIT_PERMS[k][1] == 1


def test_orbitas_das_cartas_de_chance() -> None:
    b = board("Ks", "7s", "2s", "Jd")
    g = symmetry_group(b, [FULL, FULL])  # fixa s e d; troca h <-> c
    orbits = chance_orbits(b, g)
    total = sum(1 + len(members) for _, members in orbits)
    assert total == 48
    canon = {x for x, _ in orbits}
    assert parse_card("Ah") in canon and parse_card("Ac") not in canon
    for x, members in orbits:
        for y, kinv in members:
            # kinv leva y de volta à carta canônica x
            assert permute_card(y, kinv) == x


def test_estrategia_da_carta_isomorfa_e_a_da_canonica_permutada() -> None:
    from gto_engine.analysis.node_view import node_view
    from gto_engine.game.builder import build_tree
    from gto_engine.game.config import TreeConfig
    from gto_engine.game.isomorphism import SUIT_PERMS as P
    from gto_engine.game.tree import Spot
    from gto_engine.io.solution_dir import solution_from_result
    from gto_engine.solver.dcfr import solve
    from gto_engine.solver.params import SolveParams

    b = board("Ks", "7s", "2s", "Jd")  # fixa s e d; h <-> c
    spot = Spot(parse_range("AA, KK, AK, QJs"), parse_range("QQ+, AQ, T9s"), b, 10, 30)
    cfg = TreeConfig.uniform(bets=(0.5,), max_raises=0)
    tree = build_tree(spot, cfg)
    p = SolveParams(max_iterations=30, target_exploitability_pct=0.0)
    sol = solution_from_result(tree, spot, cfg, p, solve(tree, p))
    chance = node_view(tree, sol, ["x", "x"])
    assert len(chance.next_cards) == 48 and "Ac" in chance.next_cards
    vx = node_view(tree, sol, ["x", "x", "Ah"])  # canônica
    vy = node_view(tree, sol, ["x", "x", "Ac"])  # isomorfa (h <-> c)
    k = P.index((0, 3, 2, 1))  # troca h <-> c
    fx = {c.combo: c for c in vx.combos}
    for c in vy.combos:
        twin = fx[_swap(c.combo, k)]
        assert c.reach_weight == pytest.approx(twin.reach_weight)
        assert c.frequencies == pytest.approx(twin.frequencies)
        assert c.ev_bb == pytest.approx(twin.ev_bb, abs=1e-6)
        assert c.equity == pytest.approx(twin.equity, abs=1e-6)
    assert vy.breadcrumb[-1] == "Ac"


def _swap(combo: str, k: int) -> str:
    from gto_engine.cards import combo_str

    return combo_str(permute_combo(parse_combo(combo), k))
