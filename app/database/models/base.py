from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass


def utcnow() -> datetime:
    """Datas são gravadas em UTC (sem tzinfo) para portabilidade SQLite/PostgreSQL."""
    return datetime.now(timezone.utc).replace(tzinfo=None)
