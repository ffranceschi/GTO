"""Hash canônico da entrada de um solve (Princípio VI, research R12)."""

from __future__ import annotations

import base64
import hashlib
import json

import numpy as np

from gto_engine import __version__
from gto_engine.game.config import TreeConfig
from gto_engine.game.tree import Spot
from gto_engine.solver.params import SolveParams


def canonical_board(board: tuple[int, ...]) -> list[int]:
    """Flop ordenado (a ordem das 3 primeiras cartas não importa); turn e river na posição."""
    return sorted(board[:3]) + list(board[3:])


def canonical_input(
    spot: Spot, config: TreeConfig, params: SolveParams, engine_version: str
) -> dict[str, object]:
    def w(r: np.ndarray) -> str:
        return base64.b64encode(np.ascontiguousarray(r, dtype="<f8").tobytes()).decode()

    return {
        "oop_range": w(spot.oop_range.weights),
        "ip_range": w(spot.ip_range.weights),
        "board": canonical_board(spot.board),
        "pot": round(float(spot.pot), 2),
        "effective_stack": round(float(spot.effective_stack), 2),
        "tree": config.to_dict(),
        "params": params.to_dict(),
        "engine_version": engine_version,
    }


def input_hash(
    spot: Spot, config: TreeConfig, params: SolveParams, engine_version: str = __version__
) -> str:
    data = json.dumps(
        canonical_input(spot, config, params, engine_version), sort_keys=True, separators=(",", ":")
    )
    return hashlib.sha256(data.encode()).hexdigest()
