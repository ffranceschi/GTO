"""CRUD de configurações de árvore nomeadas (FR-010)."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Request, Response
from gto_engine.game.config import default_tree_config
from sqlalchemy import select

from gto_api.db.models import TreeConfigRow, new_id, now_utc
from gto_api.db.session import Database
from gto_api.errors import ApiError, not_found
from gto_api.schemas.solves import Problem, TreeConfig
from gto_api.schemas.trees import NamedTreeConfig, NamedTreeConfigInput

router = APIRouter(prefix="/api/v1", tags=["tree-configs"])
PROBLEM: dict[int | str, dict[str, Any]] = {
    404: {"model": Problem},
    409: {"model": Problem},
    422: {"model": Problem},
}
DEFAULT_NAME = "Padrão"


def seed_default(db: Database) -> None:
    with db.session() as s:
        if (
            s.scalars(select(TreeConfigRow).where(TreeConfigRow.is_default.is_(True))).first()
            is None
        ):
            s.add(
                TreeConfigRow(
                    id=new_id(),
                    name=DEFAULT_NAME,
                    config_json=default_tree_config().to_dict(),
                    is_default=True,
                )
            )


def _schema(r: TreeConfigRow) -> NamedTreeConfig:
    return NamedTreeConfig(
        id=r.id,
        name=r.name,
        config=TreeConfig.model_validate(r.config_json),
        overwrite=False,
        is_default=r.is_default,
        updated_at=r.updated_at,
    )


def _validate(cfg: TreeConfig) -> dict[str, Any]:
    cfg.to_engine()  # InvalidTreeConfigError → 422
    return cfg.model_dump(mode="json")


@router.get("/tree-configs", operation_id="listTreeConfigs", response_model=list[NamedTreeConfig])
def list_configs(request: Request) -> list[NamedTreeConfig]:
    with request.app.state.db.session() as s:
        rows = s.scalars(
            select(TreeConfigRow).order_by(TreeConfigRow.is_default.desc(), TreeConfigRow.name)
        )
        return [_schema(r) for r in rows]


@router.post(
    "/tree-configs",
    operation_id="createTreeConfig",
    status_code=201,
    response_model=NamedTreeConfig,
    responses=PROBLEM,
)
def create_config(body: NamedTreeConfigInput, request: Request) -> NamedTreeConfig:
    data = _validate(body.config)
    with request.app.state.db.session() as s:
        existing = s.scalars(select(TreeConfigRow).where(TreeConfigRow.name == body.name)).first()
        if existing is not None:
            if existing.is_default:
                raise ApiError(
                    409, "configuracao_padrao", "A configuração padrão não pode ser sobrescrita."
                )
            if not body.overwrite:
                raise ApiError(
                    409,
                    "nome_em_uso",
                    f"Já existe uma configuração chamada '{body.name}'. "
                    "Confirme para sobrescrever.",
                )
            existing.config_json = data
            existing.updated_at = now_utc()
            return _schema(existing)
        row = TreeConfigRow(id=new_id(), name=body.name, config_json=data, is_default=False)
        s.add(row)
        s.flush()
        return _schema(row)


@router.put(
    "/tree-configs/{config_id}",
    operation_id="updateTreeConfig",
    response_model=NamedTreeConfig,
    responses=PROBLEM,
)
def update_config(config_id: str, body: NamedTreeConfigInput, request: Request) -> NamedTreeConfig:
    data = _validate(body.config)
    with request.app.state.db.session() as s:
        row = s.get(TreeConfigRow, config_id)
        if row is None:
            raise not_found("Configuração")
        if row.is_default:
            raise ApiError(
                409, "configuracao_padrao", "A configuração padrão não pode ser alterada."
            )
        other = s.scalars(
            select(TreeConfigRow).where(
                TreeConfigRow.name == body.name, TreeConfigRow.id != config_id
            )
        ).first()
        if other is not None:
            raise ApiError(409, "nome_em_uso", f"Já existe uma configuração chamada '{body.name}'.")
        row.name = body.name
        row.config_json = data
        row.updated_at = now_utc()
        return _schema(row)


@router.delete(
    "/tree-configs/{config_id}", operation_id="deleteTreeConfig", status_code=204, responses=PROBLEM
)
def delete_config(config_id: str, request: Request) -> Response:
    with request.app.state.db.session() as s:
        row = s.get(TreeConfigRow, config_id)
        if row is None:
            raise not_found("Configuração")
        if row.is_default:
            raise ApiError(
                409, "configuracao_padrao", "A configuração padrão não pode ser excluída."
            )
        s.delete(row)
    return Response(status_code=204)
