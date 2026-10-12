"""T002 — o OpenAPI gerado contém o contrato da feature 001 (specs/001-…/contracts/openapi.yaml).

Todas as rotas do contrato estão implementadas (US1–US4).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
import yaml
from fastapi.testclient import TestClient

CONTRACT = (
    Path(__file__).resolve().parents[3] / "specs/001-range-equity-calculator/contracts/openapi.yaml"
)
SPEC: dict[str, Any] = yaml.safe_load(CONTRACT.read_text())
CASES = [
    pytest.param(path, method, id=f"{method.upper()} {path}")
    for path, ops in SPEC["paths"].items()
    for method in ops
    if method in ("get", "post", "put", "patch", "delete")
]


@pytest.fixture(scope="module")
def generated() -> dict[str, Any]:
    from gto_api.main import create_app

    return TestClient(create_app()).app.openapi()  # type: ignore[attr-defined,no-any-return]


@pytest.mark.parametrize(("path", "method"), CASES)
def test_operacao_existe(generated: dict[str, Any], path: str, method: str) -> None:
    gen_path = "/api/v1" + path
    assert gen_path in generated["paths"], f"falta {method.upper()} {gen_path}"
    op = generated["paths"][gen_path]
    assert method in op, f"falta o método {method.upper()} em {gen_path}"
    want = {p["name"] for p in SPEC["paths"][path].get("parameters", []) if "name" in p}
    have = {p["name"] for p in op[method].get("parameters", [])}
    assert want <= have, f"parâmetros faltando: {want - have}"


@pytest.mark.parametrize(
    "name",
    [
        "EquityRequest",
        "EquityEstimate",
        "EquityJob",
        "EquityResult",
        "ParticipantResult",
        "ComboResult",
    ],
)
def test_schemas_equity(generated: dict[str, Any], name: str) -> None:
    ref = SPEC["components"]["schemas"][name]
    gen = generated["components"]["schemas"].get(name)
    assert gen is not None, f"schema {name} ausente"
    for req in ref.get("required", []):
        assert req in gen.get("properties", {}), f"{name}.{req} ausente"
