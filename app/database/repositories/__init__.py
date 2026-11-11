from __future__ import annotations

from typing import Sequence

from sqlalchemy import func, or_, select

from app.database.models import (
    Account, AccountGame, ActivityLog, Game, GameIntegration, HardwareMetric,
    PlaySession, ProgressRecord, SystemSetting, Task,
)

from .base import Repository, like_pattern


class AccountRepository(Repository[Account]):
    model = Account

    def by_username(self, username: str) -> Account | None:
        return self.s.scalars(
            select(Account).where(func.lower(Account.username) == username.lower())
        ).first()

    def search(
        self,
        text: str = "",
        game_id: int | None = None,
        status: str | None = None,
        category: str | None = None,
    ) -> Sequence[Account]:
        stmt = select(Account)
        if text:
            pattern = like_pattern(text.strip())
            stmt = stmt.where(or_(
                Account.username.ilike(pattern, escape="\\"),
                Account.tags.ilike(pattern, escape="\\"),
                Account.notes.ilike(pattern, escape="\\"),
            ))
        if game_id is not None:
            stmt = stmt.where(Account.id.in_(
                select(AccountGame.account_id).where(AccountGame.game_id == game_id)
            ))
        if status:
            stmt = stmt.where(Account.status == status)
        if category is not None:
            stmt = stmt.where(Account.category == category)
        return self.s.scalars(stmt.order_by(Account.category, Account.username)).unique().all()


class GameRepository(Repository[Game]):
    model = Game

    def by_slug(self, slug: str) -> Game | None:
        return self.s.scalars(select(Game).where(Game.slug == slug)).first()


class TaskRepository(Repository[Task]):
    model = Task


class SessionRepository(Repository[PlaySession]):
    model = PlaySession

    def open_sessions(self) -> Sequence[PlaySession]:
        return self.list(PlaySession.ended_at.is_(None), order_by=PlaySession.started_at)


class ProgressRepository(Repository[ProgressRecord]):
    model = ProgressRecord


class ActivityRepository(Repository[ActivityLog]):
    model = ActivityLog


class SettingRepository(Repository[SystemSetting]):
    model = SystemSetting


class IntegrationRepository(Repository[GameIntegration]):
    model = GameIntegration


class MetricRepository(Repository[HardwareMetric]):
    model = HardwareMetric


__all__ = [
    "AccountRepository", "ActivityRepository", "GameRepository", "IntegrationRepository",
    "MetricRepository", "ProgressRepository", "Repository", "SessionRepository",
    "SettingRepository", "TaskRepository", "like_pattern",
]
