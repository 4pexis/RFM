from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, utcnow

if TYPE_CHECKING:
    from .account import Account
    from .game import Game


class TaskStatus:
    PENDING = "pending"
    RUNNING = "running"
    PAUSED = "paused"
    DONE = "done"
    CANCELED = "canceled"
    ERROR = "error"
    LABELS = {
        PENDING: "Pendente",
        RUNNING: "Em andamento",
        PAUSED: "Pausada",
        DONE: "Concluída",
        CANCELED: "Cancelada",
        ERROR: "Erro",
    }
    OPEN = (PENDING, RUNNING, PAUSED)
    CLOSED = (DONE, CANCELED, ERROR)


class TaskPriority:
    LOW, NORMAL, HIGH, URGENT = 1, 2, 3, 4
    LABELS = {LOW: "Baixa", NORMAL: "Normal", HIGH: "Alta", URGENT: "Urgente"}


class Task(Base):
    __tablename__ = "tasks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    account_id: Mapped[int | None] = mapped_column(ForeignKey("accounts.id", ondelete="SET NULL"), index=True)
    game_id: Mapped[int | None] = mapped_column(ForeignKey("games.id", ondelete="SET NULL"), index=True)
    type: Mapped[str] = mapped_column(String(48), default="Geral")
    description: Mapped[str] = mapped_column(Text, default="")
    priority: Mapped[int] = mapped_column(Integer, default=TaskPriority.NORMAL, index=True)
    status: Mapped[str] = mapped_column(String(16), default=TaskStatus.PENDING, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    started_at: Mapped[datetime | None] = mapped_column(DateTime)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, index=True)
    result: Mapped[str] = mapped_column(Text, default="")

    account: Mapped["Account | None"] = relationship(lazy="joined")
    game: Mapped["Game | None"] = relationship(lazy="joined")
