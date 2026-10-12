"""T048 — armazenamento interno: diretório com meta.json + .npy sem compressão (mmap)."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from gto_engine import __version__
from gto_engine.game.builder import build_tree
from gto_engine.io.solution_dir import open_solution_dir, save_solution_dir, solution_from_result
from gto_engine.solver.dcfr import solve
from gto_engine.solver.params import SolveParams
from tests.conftest import load_spot


def test_grava_e_abre_com_mmap(tmp_path: Path) -> None:
    spot, cfg = load_spot("river_reference.json")
    tree = build_tree(spot, cfg)
    params = SolveParams(max_iterations=20, target_exploitability_pct=0.0)
    r = solve(tree, params)
    sol = solution_from_result(tree, spot, cfg, params, r)
    d = tmp_path / sol.meta.input_hash
    size = save_solution_dir(sol, d)
    meta = json.loads((d / "meta.json").read_text())
    for k in (
        "format_version",
        "engine_version",
        "input_hash",
        "spot",
        "tree_config",
        "solve_params",
        "iterations",
        "final_exploitability_pct",
        "stop_reason",
        "created_at",
    ):
        assert k in meta
    assert meta["format_version"] == "1.0" and meta["engine_version"] == __version__
    files = {p.name for p in d.iterdir()}
    assert {
        "strategy.npy",
        "ev.npy",
        "equity.npy",
        "node_offsets.npy",
        "combo_offsets.npy",
        "exploitability_history.npy",
    } <= files
    assert size == sum(p.stat().st_size for p in d.iterdir())
    for p in d.glob("*.npy"):  # sem compressão: lê direto como .npy
        assert np.load(p, mmap_mode="r") is not None
    opened = open_solution_dir(d)
    assert isinstance(opened.strategy, np.memmap)
    np.testing.assert_array_equal(opened.strategy, r.strategy)
    np.testing.assert_array_equal(opened.ev, r.ev)
    np.testing.assert_array_equal(opened.equity, r.equity)
    assert opened.meta == sol.meta
