"""App FastAPI (uso pessoal, só localhost): lifespan, /health, CORS, WebSocket de jobs."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from gto_engine import __version__ as engine_version

from gto_api.db.session import Database
from gto_api.errors import install_handlers
from gto_api.jobs.local_process import LaneJobRunner
from gto_api.jobs.persist import make_event_hook, make_snapshot_lookup
from gto_api.schemas.health import Health
from gto_api.settings import Settings
from gto_api.ws import job_events

CLEANUP_INTERVAL_S = 6 * 3600  # research R14: no startup e a cada 6 h


def create_app(settings: Settings | None = None, runner: LaneJobRunner | None = None) -> FastAPI:
    settings = settings or Settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        for d in (
            settings.data_dir,
            settings.solutions_dir,
            settings.exports_dir,
            settings.imports_dir,
        ):
            d.mkdir(parents=True, exist_ok=True)
        db = Database(settings.db_url)
        db.create_all()
        db.reconcile_after_restart()
        app.state.db = db
        app.state.settings = settings
        app.state.lookup_snapshot = make_snapshot_lookup(db)
        r = runner or LaneJobRunner(
            backend="process" if settings.use_processes else "thread",
            command_timeout_s=settings.command_timeout_s,
        )
        r.on_event = make_event_hook(db)
        app.state.runner = r
        for hook in app.state.startup_hooks:
            hook(app)
        # warm-up em segundo plano: /health responde warming_up até terminar
        app.state.warmup_task = asyncio.create_task(r.start())

        async def schedule_cleanup() -> str:
            from gto_api.routers.aux_jobs import schedule_cleanup as run

            return await run(app)

        app.state.schedule_cleanup = schedule_cleanup

        async def periodic_cleanup() -> None:
            await app.state.warmup_task
            while True:
                try:
                    await schedule_cleanup()
                except Exception:  # limpeza não pode derrubar o serviço
                    logging.getLogger(__name__).exception("falha ao agendar a limpeza")
                await asyncio.sleep(CLEANUP_INTERVAL_S)

        cleanup_task = (
            asyncio.create_task(periodic_cleanup()) if settings.periodic_cleanup else None
        )
        try:
            yield
        finally:
            if cleanup_task:
                cleanup_task.cancel()
            await r.shutdown()

    app = FastAPI(
        title="GTO API — Solver postflop",
        version="1.1.0",
        lifespan=lifespan,
        docs_url="/api/docs",
        openapi_url="/openapi.json",
    )
    app.state.startup_hooks = []
    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(settings.cors_origins),
        allow_methods=["*"],
        allow_headers=["*"],
    )
    install_handlers(app)

    @app.get(
        "/api/v1/health",
        operation_id="getHealth",
        tags=["health"],
        response_model=Health,
        responses={503: {"model": Health, "description": "Aquecendo"}},
    )
    async def health() -> JSONResponse:
        r = getattr(app.state, "runner", None)
        ready = bool(r is not None and r.ready is not None and r.ready.is_set())
        body: dict[str, Any] = {
            "status": "ready" if ready else "warming_up",
            "engine_version": engine_version,
        }
        return JSONResponse(body, status_code=200 if ready else 503)

    app.include_router(job_events.router)
    _include_routers(app)
    return app


def _include_routers(app: FastAPI) -> None:
    """Cada story registra aqui o seu router (T042)."""
    from gto_api.routers import aux_jobs, ranges, solves, tree_configs, trees

    app.include_router(aux_jobs.router)
    app.include_router(ranges.router)
    app.include_router(solves.router)
    app.include_router(trees.router)
    app.include_router(tree_configs.router)
    app.state.startup_hooks.append(lambda a: tree_configs.seed_default(a.state.db))


app = create_app()
