"""Ambiente Alembic.

- Pelo aplicativo: a conexão chega em ``config.attributes["connection"]``.
- Pela linha de comando (``alembic upgrade head``): usa RFM_DATABASE_URL / .env.
"""
from __future__ import annotations

from alembic import context
from sqlalchemy import create_engine

from app.core.config import load_settings
from app.database.models import Base

config = context.config
target_metadata = Base.metadata


def _configure(connection) -> None:
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        render_as_batch=connection.dialect.name == "sqlite",
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_offline() -> None:
    context.configure(url=load_settings().database_url, target_metadata=target_metadata, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connection = config.attributes.get("connection")
    if connection is not None:
        _configure(connection)
        return
    settings = load_settings()
    settings.ensure_dirs()
    engine = create_engine(settings.database_url)
    with engine.connect() as conn:
        _configure(conn)
        conn.commit()
    engine.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
