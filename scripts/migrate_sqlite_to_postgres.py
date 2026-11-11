"""Copia todos os dados do SQLite local para um PostgreSQL vazio.

    pip install -r requirements-postgres.txt
    python scripts/migrate_sqlite_to_postgres.py "postgresql+psycopg://usuario:senha@host:5432/rfm"

O script cria o esquema no destino (Alembic) e copia todas as tabelas. Depois,
defina RFM_DATABASE_URL no .env com a mesma URL para o aplicativo usar o PostgreSQL.
O arquivo SQLite não é alterado.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.config import load_settings  # noqa: E402
from app.database.transfer import copy_database  # noqa: E402


def main() -> int:
    if len(sys.argv) != 2 or not sys.argv[1].startswith("postgresql"):
        print(__doc__)
        return 2
    settings = load_settings()
    source = f"sqlite:///{(settings.data_dir / 'rfm.db').as_posix()}"
    print(f"Origem : {source}")
    copied = copy_database(source, sys.argv[1])
    for table, total in copied.items():
        print(f"  {table:<20} {total:>7} linha(s)")
    print("Concluído. Defina RFM_DATABASE_URL no .env para usar o PostgreSQL.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
