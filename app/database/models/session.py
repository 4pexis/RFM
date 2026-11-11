from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, utcnow

if TYPE_CHECKING:
    from .account import Account
    from .game import Game


class SessionStatus:
    ACTIVE = "active"
    IDLE = "idle"  # processo sem atividade: possível desconexão
    PROBLEM = "problem"  # marcada manualmente
    ENDED = "ended"
    LABELS = {
        ACTIVE: "Ativa",
        IDLE: "Ociosa (possível desconexão)",
        PROBLEM: "Com problema",
        ENDED: "Encerrada",
    }


class PlaySession(Base):
    """Sessão local acompanhada (processo detectado ou registro manual)."""

    __tablename__ = "sessions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    account_id: Mapped[int | None] = mapped_column(ForeignKey("accounts.id", ondelete="SET NULL"), index=True)
    game_id: Mapped[int | None] = mapped_column(ForeignKey("games.id", ondelete="SET NULL"), index=True)
    pid: Mapped[int | None] = mapped_column(Integer)
    process_name: Mapped[str] = mapped_column(String(128), default="")
    process_created: Mapped[float | None] = mapped_column(Float)  # create_time do processo
    manual: Mapped[bool] = mapped_column(Boolean, default=False)
    status: Mapped[str] = mapped_column(String(16), default=SessionStatus.ACTIVE, index=True)
    started_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, index=True)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime, index=True)
    last_seen: Mapped[datetime | None] = mapped_column(DateTime)
    idle_since: Mapped[datetime | None] = mapped_column(DateTime)
    duration_s: Mapped[int] = mapped_column(Integer, default=0)  # preenchido ao encerrar
    cpu_avg: Mapped[float] = mapped_column(Float, default=0.0)
    cpu_samples: Mapped[int] = mapped_column(Integer, default=0)
    memory_mb: Mapped[float] = mapped_column(Float, default=0.0)
    memory_peak_mb: Mapped[float] = mapped_column(Float, default=0.0)
    notes: Mapped[str] = mapped_column(Text, default="")

    account: Mapped["Account | None"] = relationship(lazy="joined")
    game: Mapped["Game | None"] = relationship(lazy="joined")

    @property
    def is_open(self) -> bool:
        return self.ended_at is None

    @property
    def elapsed_s(self) -> int:
        if self.ended_at is not None:
            return self.duration_s
        return max(0, int((utcnow() - self.started_at).total_seconds()))
