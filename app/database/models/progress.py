from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, utcnow

if TYPE_CHECKING:
    from .account import Account
    from .game import Game


class ProgressKind:
    LEVEL = "level"
    ACHIEVEMENT = "achievement"
    ITEM = "item"
    OBJECTIVE = "objective"
    STAT = "stat"
    LABELS = {
        LEVEL: "Nível",
        ACHIEVEMENT: "Conquista",
        ITEM: "Item",
        OBJECTIVE: "Objetivo",
        STAT: "Estatística",
    }


class ProgressRecord(Base):
    __tablename__ = "progress_records"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    account_id: Mapped[int] = mapped_column(ForeignKey("accounts.id", ondelete="CASCADE"), index=True)
    game_id: Mapped[int | None] = mapped_column(ForeignKey("games.id", ondelete="SET NULL"), index=True)
    kind: Mapped[str] = mapped_column(String(16), default=ProgressKind.OBJECTIVE, index=True)
    name: Mapped[str] = mapped_column(String(128))
    value: Mapped[str] = mapped_column(String(255), default="")
    numeric_value: Mapped[float | None] = mapped_column(Float)
    recorded_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, index=True)
    notes: Mapped[str] = mapped_column(Text, default="")

    account: Mapped["Account"] = relationship(lazy="joined")
    game: Mapped["Game | None"] = relationship(lazy="joined")
