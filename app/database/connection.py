"""DATABASE MANAGER: engine, sessões e migrações (SQLite e PostgreSQL)."""
from __future__ import annotations

import logging
from contextlib import contextmanager
from typing import Iterator

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.config import resource_root

from .models import Base

log = logging.getLogger(__name__)


def _sqlite_pragmas(dbapi_connection, _record) -> None:
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA busy_timeout=5000")
    cursor.close()


class Database:
    def __init__(self, url: str) -> None:
        self.url = url
        self._make_engine()

    def _make_engine(self) -> None:
        kwargs: dict = {}
        if self.is_sqlite and (":memory:" in self.url or self.url == "sqlite://"):
            kwargs.update(poolclass=StaticPool, connect_args={"check_same_thread": False})
        elif not self.is_sqlite:
            kwargs.update(pool_pre_ping=True)
        self.engine: Engine = create_engine(self.url, **kwargs)
        if self.is_sqlite:
            event.listen(self.engine, "connect", _sqlite_pragmas)
        self._factory = sessionmaker(self.engine, expire_on_commit=False)

    @property
    def is_sqlite(self) -> bool:
        return self.url.startswith("sqlite")

    @contextmanager
    def session(self) -> Iterator[Session]:
        """Unidade de trabalho: commit ao sair, rollback em caso de erro."""
        session = self._factory()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    def create_all(self) -> None:
        """Cria as tabelas direto dos modelos (uso em testes)."""
        Base.metadata.create_all(self.engine)

    def migrate(self) -> None:
        """Aplica as migrações Alembic até a versão mais recente."""
        from alembic import command
        from alembic.config import Config

        cfg = Config()
        cfg.set_main_option("script_location", str(resource_root() / "app" / "database" / "migrations"))
        with self.engine.begin() as connection:
            cfg.attributes["connection"] = connection
            command.upgrade(cfg, "head")
        log.info("Migrações aplicadas")

    def dispose(self) -> None:
        self.engine.dispose()

    def reconnect(self) -> None:
        """Recria o engine (após restaurar um backup)."""
        self.dispose()
        self._make_engine()
