"""Armazenamento interno das soluções: diretório com meta.json + .npy sem compressão (R12)."""

from __future__ import annotations

import json
import os
import shutil
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np

from gto_engine import __version__
from gto_engine.cards import card_str, parse_card
from gto_engine.game.config import TreeConfig
from gto_engine.game.hashing import input_hash
from gto_engine.game.tree import GameTree, Spot
from gto_engine.ranges import format_range, parse_range
from gto_engine.solver.dcfr import SolveResult
from gto_engine.solver.params import SolveParams

FORMAT_VERSION = "1.0"
ARRAYS = ("strategy", "ev", "equity", "node_offsets", "combo_offsets", "exploitability_history")


class SolutionFormatError(ValueError):
    code = "arquivo_invalido"


class IncompatibleVersionError(ValueError):
    code = "versao_incompativel"


@dataclass(frozen=True)
class SolutionMeta:
    format_version: str
    engine_version: str
    input_hash: str
    spot: dict[str, Any]
    tree_config: dict[str, Any]
    solve_params: dict[str, Any]
    iterations: int
    final_exploitability_pct: float
    stop_reason: str
    created_at: str


@dataclass
class Solution:
    meta: SolutionMeta
    strategy: np.ndarray
    ev: np.ndarray
    equity: np.ndarray
    node_offsets: np.ndarray
    combo_offsets: np.ndarray
    exploitability_history: np.ndarray


def spot_to_dict(spot: Spot) -> dict[str, Any]:
    return {
        "oop_range": format_range(spot.oop_range),
        "ip_range": format_range(spot.ip_range),
        "board": [card_str(c) for c in spot.board],
        "pot": spot.pot,
        "effective_stack": spot.effective_stack,
    }


def spot_from_dict(d: dict[str, Any]) -> Spot:
    return Spot(
        parse_range(d["oop_range"]),
        parse_range(d["ip_range"]),
        tuple(parse_card(c) for c in d["board"]),
        float(d["pot"]),
        float(d["effective_stack"]),
    )


def params_from_dict(d: dict[str, Any]) -> SolveParams:
    return SolveParams(**d)


def solution_from_result(
    tree: GameTree, spot: Spot, config: TreeConfig, params: SolveParams, r: SolveResult
) -> Solution:
    if r.ev is None or r.equity is None:
        raise ValueError("O resultado não foi finalizado (sem EV/equity).")
    meta = SolutionMeta(
        FORMAT_VERSION,
        __version__,
        input_hash(spot, config, params),
        spot_to_dict(spot),
        config.to_dict(),
        params.to_dict(),
        int(r.iterations),
        float(r.exploitability_pct),
        r.stop_reason,
        datetime.now(UTC).isoformat(timespec="seconds"),
    )
    return Solution(
        meta,
        r.strategy,
        r.ev,
        r.equity,
        tree.dec_offset.copy(),
        tree.dec_combo_offset.copy(),
        np.asarray(r.history, dtype=np.float64),
    )


def save_solution_dir(solution: Solution, directory: Path) -> int:
    """Grava atomicamente (diretório temporário + rename). Retorna o tamanho em bytes."""
    directory = Path(directory)
    tmp = directory.with_name(directory.name + ".tmp")
    if tmp.exists():
        shutil.rmtree(tmp)
    tmp.mkdir(parents=True)
    (tmp / "meta.json").write_text(json.dumps(asdict(solution.meta), ensure_ascii=False, indent=2))
    for name in ARRAYS:
        np.save(
            tmp / f"{name}.npy", np.ascontiguousarray(getattr(solution, name)), allow_pickle=False
        )
    if directory.exists():
        shutil.rmtree(directory)
    os.replace(tmp, directory)
    return sum(p.stat().st_size for p in directory.iterdir())


def read_meta(directory: Path) -> SolutionMeta:
    try:
        raw = json.loads((Path(directory) / "meta.json").read_text())
        meta = SolutionMeta(**raw)
    except (OSError, ValueError, TypeError) as exc:
        raise SolutionFormatError("Metadados da solução ausentes ou inválidos.") from exc
    if meta.format_version != FORMAT_VERSION:
        raise IncompatibleVersionError(
            f"Versão de formato {meta.format_version} não suportada (esperado {FORMAT_VERSION})."
        )
    return meta


def open_solution_dir(directory: Path) -> Solution:
    directory = Path(directory)
    meta = read_meta(directory)
    try:
        arrays = {
            n: np.load(directory / f"{n}.npy", mmap_mode="r", allow_pickle=False) for n in ARRAYS
        }
    except (OSError, ValueError) as exc:
        raise SolutionFormatError("Arquivos da solução ausentes ou corrompidos.") from exc
    return Solution(meta, **arrays)


def dir_size(directory: Path) -> int:
    return sum(p.stat().st_size for p in Path(directory).iterdir())
