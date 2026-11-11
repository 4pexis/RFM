"""REPORT MANAGER: indicadores do dashboard, produtividade e exportações."""
from __future__ import annotations

import csv
from collections import defaultdict
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Sequence

from sqlalchemy import func, select

from app.database.models import (
    Account, AccountGame, AccountStatus, ActivityLog, Game, PlaySession, ProgressRecord,
    Task, TaskStatus, utcnow,
)

from .base import BaseManager


@dataclass(frozen=True)
class DashboardSummary:
    total_accounts: int
    total_games: int
    active_accounts: int
    paused_accounts: int
    pending_tasks: int
    done_tasks: int
    open_sessions: int
    total_seconds: int


@dataclass(frozen=True)
class TimeRow:
    label: str
    sessions: int
    seconds: int
    tasks_done: int
    progress_records: int


def _local_offset() -> timedelta:
    return datetime.now().astimezone().utcoffset() or timedelta()


def _local_day(value: datetime) -> date:
    return (value + _local_offset()).date()


def _last_days(days: int) -> list[date]:
    today = datetime.now().date()
    return [today - timedelta(days=offset) for offset in range(days - 1, -1, -1)]


class ReportManager(BaseManager):
    # ------------------------------------------------------------- dashboard

    def summary(self) -> DashboardSummary:
        with self.db.session() as s:
            def count(model, *where) -> int:
                return s.scalar(select(func.count()).select_from(model).where(*where)) or 0

            closed = s.scalar(select(func.coalesce(func.sum(PlaySession.duration_s), 0))) or 0
            running = s.scalars(select(PlaySession).where(PlaySession.ended_at.is_(None))).unique().all()
            return DashboardSummary(
                total_accounts=count(Account),
                total_games=count(Game),
                active_accounts=count(Account, Account.status == AccountStatus.ACTIVE),
                paused_accounts=count(Account, Account.status == AccountStatus.PAUSED),
                pending_tasks=count(Task, Task.status == TaskStatus.PENDING),
                done_tasks=count(Task, Task.status == TaskStatus.DONE),
                open_sessions=len(running),
                total_seconds=int(closed) + sum(r.elapsed_s for r in running),
            )

    def accounts_per_game(self) -> list[tuple[str, int]]:
        with self.db.session() as s:
            rows = s.execute(
                select(Game.name, func.count(AccountGame.account_id))
                .outerjoin(AccountGame, AccountGame.game_id == Game.id)
                .group_by(Game.id, Game.name).order_by(func.count(AccountGame.account_id).desc(), Game.name)
            ).all()
        return [(name, total) for name, total in rows]

    def progress_per_game(self) -> list[tuple[str, int]]:
        with self.db.session() as s:
            rows = s.execute(
                select(Game.name, func.count(ProgressRecord.id))
                .outerjoin(ProgressRecord, ProgressRecord.game_id == Game.id)
                .group_by(Game.id, Game.name).order_by(func.count(ProgressRecord.id).desc(), Game.name)
            ).all()
        return [(name, total) for name, total in rows]

    def status_distribution(self) -> list[tuple[str, int]]:
        with self.db.session() as s:
            rows = dict(s.execute(select(Account.status, func.count()).group_by(Account.status)).all())
        return [(label, rows.get(key, 0)) for key, label in AccountStatus.LABELS.items() if rows.get(key)]

    def _per_day(self, column, days: int, *where) -> list[tuple[date, int]]:
        since = utcnow() - timedelta(days=days + 1)
        with self.db.session() as s:
            stamps = s.scalars(select(column).where(column >= since, *where)).all()
        totals: dict[date, int] = defaultdict(int)
        for stamp in stamps:
            totals[_local_day(stamp)] += 1
        return [(day, totals.get(day, 0)) for day in _last_days(days)]

    def daily_activity(self, days: int = 14) -> list[tuple[date, int]]:
        """Operações registradas por dia (histórico de atividades)."""
        return self._per_day(ActivityLog.timestamp, days)

    def weekly_productivity(self, days: int = 7) -> list[tuple[date, int]]:
        """Tarefas concluídas por dia."""
        return self._per_day(Task.finished_at, days, Task.status == TaskStatus.DONE)

    # ------------------------------------------------------------- relatórios

    def time_report(self, start: datetime, end: datetime, by: str = "account") -> list[TimeRow]:
        """Tempo de operação, tarefas concluídas e registros de progresso no
        período [start, end) em UTC, agrupados por conta ("account") ou jogo ("game")."""
        key_col = {"account": "account_id", "game": "game_id"}[by]
        now = utcnow()
        data: dict[int | None, list[int]] = defaultdict(lambda: [0, 0, 0, 0])
        with self.db.session() as s:
            sessions = s.scalars(
                select(PlaySession).where(
                    PlaySession.started_at < end,
                    (PlaySession.ended_at.is_(None)) | (PlaySession.ended_at >= start),
                )
            ).unique().all()
            for session in sessions:
                # Conta apenas a parte da sessão que cai dentro do período.
                begin = max(session.started_at, start)
                finish = min(session.ended_at or now, end)
                row = data[getattr(session, key_col)]
                row[0] += 1
                row[1] += max(0, int((finish - begin).total_seconds()))
            for key, total in s.execute(
                select(getattr(Task, key_col), func.count()).where(
                    Task.status == TaskStatus.DONE, Task.finished_at >= start, Task.finished_at < end,
                ).group_by(getattr(Task, key_col))
            ).all():
                data[key][2] = total
            for key, total in s.execute(
                select(getattr(ProgressRecord, key_col), func.count()).where(
                    ProgressRecord.recorded_at >= start, ProgressRecord.recorded_at < end,
                ).group_by(getattr(ProgressRecord, key_col))
            ).all():
                data[key][3] = total
            if by == "account":
                names = dict(s.execute(select(Account.id, Account.username)).all())
            else:
                names = dict(s.execute(select(Game.id, Game.name)).all())
        rows = [
            TimeRow(names.get(key, "(sem associação)") if key is not None else "(sem associação)", *values)
            for key, values in data.items()
        ]
        return sorted(rows, key=lambda r: (-r.seconds, -r.tasks_done, r.label.lower()))

    def activity(self, start: datetime, end: datetime, limit: int = 1000) -> Sequence[ActivityLog]:
        with self.db.session() as s:
            return s.scalars(
                select(ActivityLog).where(ActivityLog.timestamp >= start, ActivityLog.timestamp < end)
                .order_by(ActivityLog.timestamp.desc()).limit(limit)
            ).all()

    def export_time_report(self, path: str | Path, rows: Sequence[TimeRow], by_label: str) -> None:
        with open(path, "w", newline="", encoding="utf-8-sig") as handle:
            writer = csv.writer(handle)
            writer.writerow([by_label, "sessoes", "horas", "tarefas_concluidas", "registros_progresso"])
            for row in rows:
                writer.writerow([row.label, row.sessions, f"{row.seconds / 3600:.2f}",
                                 row.tasks_done, row.progress_records])
        with self.db.session() as s:
            self._audit(s, "report.export", "report", None, Path(path).name)
