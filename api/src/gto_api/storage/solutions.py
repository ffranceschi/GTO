"""Soluções em disco por hash, cache LRU e `last_used_at` limitado (R12, R14)."""

from __future__ import annotations

import shutil
import threading
import time
from collections import OrderedDict
from pathlib import Path

from gto_engine.game.builder import build_tree
from gto_engine.game.config import TreeConfig
from gto_engine.game.tree import GameTree
from gto_engine.io.solution_dir import (
    Solution,
    open_solution_dir,
    open_tree_dir,
    spot_from_dict,
)

LRU_SIZE = 2
LAST_USED_MIN_INTERVAL_S = 60.0


class SolutionStore:
    def __init__(self, root: Path) -> None:
        self.root = Path(root)
        self._lru: OrderedDict[str, tuple[GameTree, Solution]] = OrderedDict()
        self._lock = threading.Lock()
        self._last_touch: dict[str, float] = {}

    def path(self, input_hash: str) -> Path:
        return self.root / input_hash

    def open(self, solution_dir: str) -> tuple[GameTree, Solution]:
        with self._lock:
            if solution_dir in self._lru:
                self._lru.move_to_end(solution_dir)
                return self._lru[solution_dir]
        sol = open_solution_dir(self.path(solution_dir))
        # árvore gravada (mmap, ≤ 200 ms — T101); soluções antigas sem árvore são reconstruídas
        tree = open_tree_dir(self.path(solution_dir)) or build_tree(
            spot_from_dict(sol.meta.spot), TreeConfig.from_dict(sol.meta.tree_config)
        )
        with self._lock:
            self._lru[solution_dir] = (tree, sol)
            while len(self._lru) > LRU_SIZE:
                self._lru.popitem(last=False)
        return tree, sol

    def forget(self, solution_dir: str) -> None:
        with self._lock:
            self._lru.pop(solution_dir, None)

    def delete(self, solution_dir: str) -> None:
        self.forget(solution_dir)
        shutil.rmtree(self.path(solution_dir), ignore_errors=True)

    def should_touch(self, solve_id: str) -> bool:
        """`last_used_at` é gravado no máximo 1×/min por solução."""
        now = time.monotonic()
        last = self._last_touch.get(solve_id)
        if last is not None and now - last < LAST_USED_MIN_INTERVAL_S:
            return False
        self._last_touch[solve_id] = now
        return True
