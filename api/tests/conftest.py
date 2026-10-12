from __future__ import annotations

import time
from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from gto_api.main import create_app
from gto_api.settings import Settings
from tests.fakes import FakeJobRunner


@pytest.fixture(scope="session", autouse=True)
def _warm_jit() -> None:
    """Como o warm-up do worker em produção (research R8): compila os kernels uma vez."""
    from gto_engine.warmup import warmup

    warmup()


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    return Settings(data_dir=tmp_path / "data", use_processes=False)


@pytest.fixture
def client(settings: Settings) -> Iterator[TestClient]:
    app = create_app(settings, runner=FakeJobRunner())
    with TestClient(app) as c:
        t0 = time.monotonic()
        while c.get("/api/v1/health").status_code != 200:
            assert time.monotonic() - t0 < 10
            time.sleep(0.02)
        yield c
