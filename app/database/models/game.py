from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, utcnow


class IntegrationStatus:
    MODULE = "module"
    MANUAL = "manual"
    DISABLED = "disabled"
    LABELS = {MODULE: "Módulo carregado", MANUAL: "Acompanhamento manual", DISABLED: "Desativado"}


class Game(Base):
    __tablename__ = "games"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(128), unique=True)
    slug: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    experience_id: Mapped[str] = mapped_column(String(32), default="")  # Place ID
    category: Mapped[str] = mapped_column(String(64), default="")
    description: Mapped[str] = mapped_column(Text, default="")
    icon: Mapped[str] = mapped_column(String(255), default="gamepad-variant")
    integration_status: Mapped[str] = mapped_column(String(16), default=IntegrationStatus.MANUAL)
    module_name: Mapped[str] = mapped_column(String(64), default="")
    # Lista de objetivos: [{"key", "name", "kind", "description", "max_value"}]
    objectives: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class GameIntegration(Base):
    """Estado do módulo (plugin) responsável por cada jogo."""

    __tablename__ = "game_integrations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    game_id: Mapped[int] = mapped_column(ForeignKey("games.id", ondelete="CASCADE"), unique=True)
    module_name: Mapped[str] = mapped_column(String(64))
    version: Mapped[str] = mapped_column(String(32), default="")
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    last_loaded: Mapped[datetime | None] = mapped_column(DateTime)
    last_error: Mapped[str] = mapped_column(Text, default="")
