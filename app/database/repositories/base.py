"""Repositório genérico: concentra o acesso SQL usado pelos managers.

Todas as consultas usam SQLAlchemy com parâmetros vinculados (sem SQL montado
por concatenação), o que protege contra SQL injection.
"""
from __future__ import annotations

from typing import Any, Generic, Sequence, TypeVar

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.security import ValidationError

T = TypeVar("T")


def like_pattern(text: str) -> str:
    """Escapa curingas para busca parcial (use com escape='\\\\')."""
    escaped = text.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return f"%{escaped}%"


class Repository(Generic[T]):
    model: type[T]

    def __init__(self, session: Session) -> None:
        self.s = session

    def get(self, entity_id: int) -> T | None:
        return self.s.get(self.model, entity_id)

    def require(self, entity_id: int) -> T:
        entity = self.get(entity_id)
        if entity is None:
            raise ValidationError(f"Registro {entity_id} não encontrado.")
        return entity

    def add(self, entity: T) -> T:
        self.s.add(entity)
        self.s.flush()
        return entity

    def delete(self, entity: T) -> None:
        self.s.delete(entity)
        self.s.flush()

    def list(self, *where: Any, order_by: Any = None, limit: int | None = None) -> Sequence[T]:
        stmt = select(self.model).where(*where)
        if order_by is not None:
            stmt = stmt.order_by(*(order_by if isinstance(order_by, (list, tuple)) else (order_by,)))
        if limit:
            stmt = stmt.limit(limit)
        return self.s.scalars(stmt).unique().all()

    def count(self, *where: Any) -> int:
        return self.s.scalar(select(func.count()).select_from(self.model).where(*where)) or 0
