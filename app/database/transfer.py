"""Cópia completa de dados entre bancos (ex.: SQLite -> PostgreSQL)."""
from __future__ import annotations

import logging

from sqlalchemy import func, insert, select, text

from .connection import Database
from .models import Base

log = logging.getLogger(__name__)


def copy_database(source_url: str, target_url: str, batch_size: int = 1000) -> dict[str, int]:
    """Aplica as migrações no destino e copia todas as tabelas.

    O destino precisa estar vazio. Retorna a quantidade de linhas por tabela.
    """
    source, target = Database(source_url), Database(target_url)
    copied: dict[str, int] = {}
    try:
        target.migrate()
        with source.engine.connect() as src, target.engine.begin() as dst:
            for table in Base.metadata.sorted_tables:  # respeita as chaves estrangeiras
                if dst.execute(select(func.count()).select_from(table)).scalar_one():
                    raise RuntimeError(f"A tabela de destino '{table.name}' não está vazia.")
                total = 0
                result = src.execution_options(stream_results=True).execute(select(table))
                while rows := result.fetchmany(batch_size):
                    dst.execute(insert(table), [dict(row._mapping) for row in rows])
                    total += len(rows)
                copied[table.name] = total
                # PostgreSQL: realinha a sequência do ID após inserir valores explícitos.
                if dst.dialect.name == "postgresql" and "id" in table.c and total:
                    dst.execute(text(
                        f"SELECT setval(pg_get_serial_sequence('{table.name}', 'id'), "
                        f"(SELECT MAX(id) FROM {table.name}))"
                    ))
        log.info("Banco copiado", extra={"tables": copied})
        return copied
    finally:
        source.dispose()
        target.dispose()
