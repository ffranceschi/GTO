"""T041 — o OpenAPI gerado contém o contrato de referência (contracts/openapi.yaml).

Paths de stories ainda não implementadas ficam como xfail (não estrito) com a story indicada.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
import yaml
from fastapi.testclient import TestClient

CONTRACT = Path(__file__).resolve().parents[3] / "specs/002-postflop-solver/contracts/openapi.yaml"
SPEC: dict[str, Any] = yaml.safe_load(CONTRACT.read_text())
STORY: dict[str, str] = {}
CASES = [
    pytest.param(
        path,
        method,
        id=f"{method.upper()} {path}",
        marks=[pytest.mark.xfail(reason=f"implementado na {STORY.get(path, 'US4')}", strict=False)]
        if path in STORY
        else [],
    )
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
    want = {p["name"] for p in SPEC["paths"][path][method].get("parameters", []) if "name" in p}
    want |= {
        SPEC["components"]["parameters"][p["$ref"].split("/")[-1]]["name"]
        for p in SPEC["paths"][path].get("parameters", [])
        + SPEC["paths"][path][method].get("parameters", [])
        if "$ref" in p
    }
    have = {p["name"] for p in op[method].get("parameters", [])}
    assert want <= have, f"parâmetros faltando: {want - have}"


SCHEMAS_US1 = [
    "Spot",
    "TreeConfig",
    "SolveParams",
    "SolveRequest",
    "Solve",
    "NodeView",
    "ActionView",
    "HandView",
    "ComboView",
    "RangeAtNode",
    "Health",
]


@pytest.mark.parametrize("name", SCHEMAS_US1)
def test_schemas_obrigatorios_e_enums(generated: dict[str, Any], name: str) -> None:
    ref = SPEC["components"]["schemas"][name]
    gen = generated["components"]["schemas"].get(name)
    assert gen is not None, f"schema {name} ausente"
    gen_props = gen.get("properties", {})
    for req in ref.get("required", []):
        assert req in gen_props, f"{name}.{req} ausente"
    for prop, spec in ref.get("properties", {}).items():
        if "enum" in spec and prop in gen_props:
            gen_enum = _enum(generated, gen_props[prop])
            assert set(x for x in spec["enum"] if x is not None) <= set(gen_enum), f"{name}.{prop}"


def _enum(root: dict[str, Any], schema: dict[str, Any]) -> list[Any]:
    if "enum" in schema:
        return list(schema["enum"])
    if "$ref" in schema:
        return _enum(root, root["components"]["schemas"][schema["$ref"].split("/")[-1]])
    out: list[Any] = []
    for k in ("anyOf", "oneOf", "allOf"):
        for s in schema.get(k, []):
            out += _enum(root, s)
    return out
