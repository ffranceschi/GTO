"""T095 — Princípio III: nenhum módulo do motor importa web, banco ou a API (reforço do TID251)."""

from __future__ import annotations

import ast
from pathlib import Path

import gto_engine

BANNED = {"fastapi", "starlette", "pydantic", "sqlalchemy", "uvicorn", "gto_api"}


def test_motor_sem_imports_proibidos() -> None:
    root = Path(gto_engine.__file__).parent
    offenders: list[str] = []
    for path in root.rglob("*.py"):
        tree = ast.parse(path.read_text(), filename=str(path))
        for node in ast.walk(tree):
            names: list[str] = []
            if isinstance(node, ast.Import):
                names = [a.name for a in node.names]
            elif isinstance(node, ast.ImportFrom) and node.module:
                names = [node.module]
            for n in names:
                if n.split(".")[0] in BANNED:
                    offenders.append(f"{path.relative_to(root)}: {n}")
    assert not offenders, offenders
