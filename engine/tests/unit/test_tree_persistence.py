"""T101 — árvore gravada em arrays e reaberta por mmap, sem reconstruir."""

from __future__ import annotations

from pathlib import Path

import numpy as np

from gto_engine.analysis.node_view import node_view
from gto_engine.cards import parse_card
from gto_engine.game.builder import build_tree
from gto_engine.game.config import TreeConfig
from gto_engine.game.tree import Spot
from gto_engine.io.exchange import export_npz, import_npz
from gto_engine.io.solution_dir import (
    open_solution_dir,
    open_tree_dir,
    save_solution_dir,
    solution_from_result,
)
from gto_engine.ranges import parse_range
from gto_engine.solver.dcfr import solve
from gto_engine.solver.params import SolveParams

MONO_TURN = tuple(parse_card(c) for c in ("Ks", "7s", "2s", "Jd"))
PATHS = [
    [],
    ["x"],
    ["x", "x"],
    ["x", "x", "Ah"],
    ["x", "x", "Ac"],
    ["x", "x", "Ac", "x"],
    ["b50", "f"],
    ["x", "x", "Ah", "x", "x"],
]


def test_arvore_reaberta_identica_e_exportada(tmp_path: Path) -> None:
    spot = Spot(parse_range("AA, KK, AK, QJs"), parse_range("QQ+, AQ, T9s"), MONO_TURN, 10, 30)
    cfg = TreeConfig.uniform(bets=(0.5,), max_raises=1)
    tree = build_tree(spot, cfg)
    p = SolveParams(max_iterations=20, target_exploitability_pct=0.0)
    sol = solution_from_result(tree, spot, cfg, p, solve(tree, p))
    d = tmp_path / "sol"
    save_solution_dir(sol, d, tree)
    reopened = open_tree_dir(d)
    assert reopened is not None and isinstance(reopened.node_type, np.memmap)
    opened = open_solution_dir(d)
    for path in PATHS:
        assert node_view(reopened, opened, path) == node_view(tree, sol, path), path
    # a árvore viaja no .npz
    npz = tmp_path / "s.npz"
    export_npz(d, npz)
    d2 = tmp_path / "imp"
    import_npz(npz, d2)
    t2 = open_tree_dir(d2)
    assert t2 is not None
    assert node_view(t2, open_solution_dir(d2), ["x", "x", "Ac", "x"]) == node_view(
        tree, sol, ["x", "x", "Ac", "x"]
    )


def test_solucao_sem_arvore(tmp_path: Path) -> None:
    spot = Spot(parse_range("AA"), parse_range("KK"), (*MONO_TURN, parse_card("3h")), 10, 30)
    cfg = TreeConfig.uniform(bets=(0.5,))
    tree = build_tree(spot, cfg)
    p = SolveParams(max_iterations=5, target_exploitability_pct=0.0)
    d = tmp_path / "x"
    save_solution_dir(solution_from_result(tree, spot, cfg, p, solve(tree, p)), d)
    assert open_tree_dir(d) is None
