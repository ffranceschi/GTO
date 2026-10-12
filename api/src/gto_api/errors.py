"""Erros RFC 9457 (application/problem+json) com `code` estável e `detail` em pt-BR."""

from __future__ import annotations

from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from gto_engine.game.config import InvalidTreeConfigError
from gto_engine.game.tree import InvalidPathError, InvalidSpotError
from gto_engine.ranges import RangeNotationError
from starlette.exceptions import HTTPException as StarletteHTTPException

TITLES = {
    400: "Requisição inválida",
    404: "Não encontrado",
    409: "Conflito",
    410: "Expirado",
    413: "Arquivo grande demais",
    422: "Entrada inválida",
    500: "Erro interno",
    503: "Indisponível",
}


class ApiError(Exception):
    def __init__(
        self, status: int, code: str, detail: str, errors: list[dict[str, str]] | None = None
    ) -> None:
        super().__init__(detail)
        self.status = status
        self.code = code
        self.detail = detail
        self.errors = errors or []


def problem(
    status: int, code: str, detail: str, errors: list[dict[str, str]] | None = None
) -> JSONResponse:
    body: dict[str, Any] = {
        "type": "about:blank",
        "title": TITLES.get(status, "Erro"),
        "status": status,
        "code": code,
        "detail": detail,
    }
    if errors:
        body["errors"] = errors
    return JSONResponse(body, status_code=status, media_type="application/problem+json")


def fmt_num(x: float, digits: int = 2) -> str:
    """Número no formato pt-BR (vírgula decimal, ponto de milhar)."""
    s = f"{x:,.{digits}f}"
    return s.replace(",", "_").replace(".", ",").replace("_", ".")


def not_found(what: str = "Recurso") -> ApiError:
    return ApiError(404, "nao_encontrado", f"{what} não encontrado.")


def install_handlers(app: FastAPI) -> None:
    @app.exception_handler(ApiError)
    async def _api(_: Request, exc: ApiError) -> JSONResponse:
        return problem(exc.status, exc.code, exc.detail, exc.errors)

    @app.exception_handler(InvalidSpotError)
    async def _spot(_: Request, exc: InvalidSpotError) -> JSONResponse:
        return problem(422, "spot_invalido", str(exc))

    @app.exception_handler(InvalidTreeConfigError)
    async def _tree(_: Request, exc: InvalidTreeConfigError) -> JSONResponse:
        return problem(422, "arvore_invalida", str(exc))

    @app.exception_handler(RangeNotationError)
    async def _range(_: Request, exc: RangeNotationError) -> JSONResponse:
        return problem(422, "range_invalido", str(exc))

    @app.exception_handler(InvalidPathError)
    async def _path(_: Request, exc: InvalidPathError) -> JSONResponse:
        return problem(422, "caminho_invalido", str(exc))

    @app.exception_handler(RequestValidationError)
    async def _validation(_: Request, exc: RequestValidationError) -> JSONResponse:
        errs = [
            {"field": ".".join(str(p) for p in e.get("loc", ()) if p != "body"), "detail": _pt(e)}
            for e in exc.errors()
        ]
        return problem(422, "entrada_invalida", "Há campos inválidos na requisição.", errs)

    @app.exception_handler(StarletteHTTPException)
    async def _http(_: Request, exc: StarletteHTTPException) -> JSONResponse:
        code = {404: "nao_encontrado", 405: "metodo_nao_permitido"}.get(
            exc.status_code, "erro_http"
        )
        detail = {
            404: "Recurso não encontrado.",
            405: "Método não permitido para este recurso.",
        }.get(exc.status_code, "Erro na requisição.")
        return problem(exc.status_code, code, detail)


def _pt(e: dict[str, Any]) -> str:
    t = e.get("type", "")
    ctx = e.get("ctx") or {}
    msgs = {
        "missing": "Campo obrigatório.",
        "greater_than": f"Deve ser maior que {ctx.get('gt')}.",
        "greater_than_equal": f"Deve ser maior ou igual a {ctx.get('ge')}.",
        "less_than_equal": f"Deve ser no máximo {ctx.get('le')}.",
        "less_than": f"Deve ser menor que {ctx.get('lt')}.",
        "string_pattern_mismatch": "Formato inválido.",
        "too_short": "Itens de menos.",
        "too_long": "Itens demais.",
        "float_parsing": "Deve ser um número.",
        "int_parsing": "Deve ser um número inteiro.",
        "int_type": "Deve ser um número inteiro.",
        "float_type": "Deve ser um número.",
        "string_type": "Deve ser um texto.",
        "bool_type": "Deve ser verdadeiro ou falso.",
        "bool_parsing": "Deve ser verdadeiro ou falso.",
        "list_type": "Deve ser uma lista.",
        "dict_type": "Deve ser um objeto.",
        "model_type": "Deve ser um objeto.",
        "literal_error": "Valor fora das opções permitidas.",
        "enum": "Valor fora das opções permitidas.",
        "json_invalid": "JSON inválido.",
        "string_too_short": "Texto curto demais.",
        "string_too_long": "Texto longo demais.",
        "extra_forbidden": "Campo não permitido.",
    }
    return msgs.get(t, "Valor inválido.")
