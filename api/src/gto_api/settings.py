"""Configuração por variáveis de ambiente (uso pessoal, só localhost — research R16)."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

GIB = 1024**3


def _env_int(name: str, default: int) -> int:
    v = os.environ.get(name)
    return int(v) if v else default


def _env_float(name: str, default: float) -> float:
    v = os.environ.get(name)
    return float(v) if v else default


@dataclass(frozen=True)
class Settings:
    data_dir: Path = field(default_factory=lambda: Path(os.environ.get("GTO_DATA_DIR", "./data")))
    max_solve_memory_bytes: int = field(
        default_factory=lambda: _env_int("GTO_MAX_SOLVE_MEMORY_BYTES", 4 * GIB)
    )
    solution_retention_days: float = field(
        default_factory=lambda: _env_float("GTO_SOLUTION_RETENTION_DAYS", 30)
    )
    max_import_bytes: int = field(default_factory=lambda: _env_int("GTO_MAX_IMPORT_BYTES", 2 * GIB))
    host: str = field(default_factory=lambda: os.environ.get("GTO_HOST", "127.0.0.1"))
    port: int = field(default_factory=lambda: _env_int("GTO_PORT", 8000))
    cors_origins: tuple[str, ...] = field(
        default_factory=lambda: tuple(
            o.strip()
            for o in os.environ.get("GTO_CORS_ORIGINS", "http://localhost:5173").split(",")
            if o.strip()
        )
    )
    command_timeout_s: float = field(
        default_factory=lambda: _env_float("GTO_COMMAND_TIMEOUT_S", 10.0)
    )
    use_processes: bool = field(
        default_factory=lambda: os.environ.get("GTO_RUNNER", "process") == "process"
    )

    @property
    def solutions_dir(self) -> Path:
        return self.data_dir / "solutions"

    @property
    def exports_dir(self) -> Path:
        return self.data_dir / "exports"

    @property
    def imports_dir(self) -> Path:
        return self.data_dir / "imports"

    @property
    def db_url(self) -> str:
        return f"sqlite:///{self.data_dir / 'gto.sqlite3'}"
