"""Engine e sessões SQLite; `create_all` no startup (sem Alembic no MVP)."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy import Engine, create_engine, event, update
from sqlalchemy.orm import Session, sessionmaker

from gto_api.db.models import (
    ACTIVE_SOLVE_STATUSES,
    AuxJobRow,
    Base,
    EquityJobRow,
    SolveRow,
    now_utc,
)


class Database:
    def __init__(self, url: str) -> None:
        self.engine: Engine = create_engine(url, connect_args={"check_same_thread": False})

        @event.listens_for(self.engine, "connect")
        def _pragmas(conn, _):  # type: ignore[no-untyped-def]
            cur = conn.cursor()
            cur.execute("PRAGMA foreign_keys=ON")
            cur.execute("PRAGMA journal_mode=WAL")
            cur.close()

        self._factory = sessionmaker(self.engine, expire_on_commit=False)

    def create_all(self) -> None:
        Base.metadata.create_all(self.engine)

    @contextmanager
    def session(self) -> Iterator[Session]:
        s = self._factory()
        try:
            yield s
            s.commit()
        except Exception:
            s.rollback()
            raise
        finally:
            s.close()

    def reconcile_after_restart(self) -> int:
        """Jobs que estavam ativos quando o servidor parou viram `failed` (servidor_reiniciado)."""
        detail = "O servidor reiniciou com o job ativo."
        with self.session() as s:
            r1 = s.execute(
                update(SolveRow)
                .where(SolveRow.status.in_(ACTIVE_SOLVE_STATUSES))
                .values(
                    status="failed",
                    error_code="servidor_reiniciado",
                    error_detail=detail,
                    finished_at=now_utc(),
                )
            )
            r2 = s.execute(
                update(AuxJobRow)
                .where(AuxJobRow.status.in_(("queued", "running")))
                .values(
                    status="failed",
                    error_code="servidor_reiniciado",
                    error_detail=detail,
                    finished_at=now_utc(),
                )
            )
            r3 = s.execute(
                update(EquityJobRow)
                .where(EquityJobRow.status.in_(("queued", "running")))
                .values(
                    status="failed",
                    error_code="servidor_reiniciado",
                    error_detail=detail,
                    finished_at=now_utc(),
                )
            )
            return int(r1.rowcount or 0) + int(r2.rowcount or 0) + int(r3.rowcount or 0)  # type: ignore[attr-defined]
