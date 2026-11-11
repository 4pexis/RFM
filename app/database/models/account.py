from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, utcnow

if TYPE_CHECKING:
    from .game import Game


class AccountStatus:
    ACTIVE = "active"
    PAUSED = "paused"
    TRACKING = "tracking"
    DONE = "done"
    ERROR = "error"
    ARCHIVED = "archived"
    LABELS = {
        ACTIVE: "Ativa",
        PAUSED: "Pausada",
        TRACKING: "Em acompanhamento",
        DONE: "Concluída",
        ERROR: "Com erro",
        ARCHIVED: "Arquivada",
    }


class Account(Base):
    __tablename__ = "accounts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    username: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    roblox_user_id: Mapped[int | None] = mapped_column(BigInteger, index=True)
    category: Mapped[str] = mapped_column(String(64), default="", index=True)
    level: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(16), default=AccountStatus.ACTIVE, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    last_activity: Mapped[datetime | None] = mapped_column(DateTime)
    notes: Mapped[str] = mapped_column(Text, default="")
    tags: Mapped[str] = mapped_column(String(255), default="")  # separadas por vírgula

    game_links: Mapped[list["AccountGame"]] = relationship(
        back_populates="account", cascade="all, delete-orphan", lazy="selectin"
    )

    @property
    def games(self) -> list["Game"]:
        return [link.game for link in self.game_links]

    @property
    def game_names(self) -> str:
        return ", ".join(sorted(g.name for g in self.games))

    @property
    def tag_list(self) -> list[str]:
        return [t for t in self.tags.split(",") if t]


class AccountGame(Base):
    __tablename__ = "account_games"

    account_id: Mapped[int] = mapped_column(ForeignKey("accounts.id", ondelete="CASCADE"), primary_key=True)
    game_id: Mapped[int] = mapped_column(ForeignKey("games.id", ondelete="CASCADE"), primary_key=True)
    level: Mapped[int] = mapped_column(Integer, default=0)
    added_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    account: Mapped[Account] = relationship(back_populates="game_links")
    game: Mapped["Game"] = relationship(lazy="joined")
