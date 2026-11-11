"""TASK MANAGER: tarefas de acompanhamento com prioridade, status e histórico.

As tarefas são registros administrativos (o que precisa ser feito em cada
conta/jogo). O RFM organiza e acompanha — não executa ações dentro do jogo.
"""
from __future__ import annotations

from typing import Any, Sequence

from sqlalchemy import func, or_, select

from app.core import events as ev
from app.core.security import Permission, ValidationError, clean_text
from app.database.models import Account, Game, Task, TaskPriority, TaskStatus, utcnow
from app.database.repositories import TaskRepository, like_pattern

from .base import BaseManager
from .game_manager import GameManager

# Transições permitidas entre status.
_TRANSITIONS = {
    TaskStatus.PENDING: {TaskStatus.RUNNING, TaskStatus.CANCELED, TaskStatus.DONE},
    TaskStatus.RUNNING: {TaskStatus.PAUSED, TaskStatus.DONE, TaskStatus.ERROR, TaskStatus.CANCELED},
    TaskStatus.PAUSED: {TaskStatus.RUNNING, TaskStatus.CANCELED, TaskStatus.DONE},
    TaskStatus.DONE: {TaskStatus.PENDING},
    TaskStatus.CANCELED: {TaskStatus.PENDING},
    TaskStatus.ERROR: {TaskStatus.PENDING, TaskStatus.RUNNING},
}


class TaskManager(BaseManager):
    def __init__(self, *args, games: GameManager, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.games = games

    def _apply(self, s, task: Task, data: dict[str, Any]) -> None:
        if "account_id" in data:
            if data["account_id"] is not None and s.get(Account, data["account_id"]) is None:
                raise ValidationError("Conta não encontrada.")
            task.account_id = data["account_id"]
        if "game_id" in data:
            if data["game_id"] is not None and s.get(Game, data["game_id"]) is None:
                raise ValidationError("Jogo não encontrado.")
            task.game_id = data["game_id"]
        if "type" in data:
            task.type = clean_text(data["type"], 48, "tipo") or "Geral"
        if "description" in data:
            task.description = clean_text(data["description"], 4000, "descrição")
        if "priority" in data:
            if data["priority"] not in TaskPriority.LABELS:
                raise ValidationError("Prioridade inválida.")
            task.priority = data["priority"]
        if "result" in data:
            task.result = clean_text(data["result"], 4000, "resultado")
        game = s.get(Game, task.game_id) if task.game_id else None
        self.games.module_for(game).validate_task(task.type, task.description)

    def create(self, **data: Any) -> Task:
        self.access.require(Permission.WRITE)
        with self.db.session() as s:
            task = Task(type="Geral", description="", priority=TaskPriority.NORMAL,
                        status=TaskStatus.PENDING, result="")
            self._apply(s, task, data)
            TaskRepository(s).add(task)
            s.refresh(task)
            self._audit(s, "task.create", "task", task.id, task.description[:200])
            if task.account_id:
                self._audit(s, "task.create", "account", task.account_id, task.description[:200])
        self.events.publish(ev.TASKS_CHANGED)
        return task

    def update(self, task_id: int, **data: Any) -> Task:
        self.access.require(Permission.WRITE)
        with self.db.session() as s:
            task = TaskRepository(s).require(task_id)
            self._apply(s, task, data)
            s.flush()
            s.refresh(task)
            self._audit(s, "task.update", "task", task.id, ", ".join(sorted(data)))
        self.events.publish(ev.TASKS_CHANGED)
        return task

    def set_status(self, task_id: int, status: str, result: str | None = None) -> Task:
        self.access.require(Permission.WRITE)
        with self.db.session() as s:
            task = TaskRepository(s).require(task_id)
            if status == task.status:
                return task
            if status not in _TRANSITIONS.get(task.status, ()):
                raise ValidationError(
                    f"Não é possível mudar de “{TaskStatus.LABELS[task.status]}” "
                    f"para “{TaskStatus.LABELS.get(status, status)}”."
                )
            now = utcnow()
            if status == TaskStatus.RUNNING and task.started_at is None:
                task.started_at = now
            if status in TaskStatus.CLOSED:
                task.finished_at = now
            if status == TaskStatus.PENDING:  # reabertura
                task.started_at = task.finished_at = None
            if result is not None:
                task.result = clean_text(result, 4000, "resultado")
            detail = f"{task.status} → {status}"
            task.status = status
            self._audit(s, "task.status", "task", task.id, detail)
            if task.account_id:
                account = s.get(Account, task.account_id)
                if account is not None:
                    account.last_activity = now
                self._audit(s, "task.status", "account", task.account_id,
                            f"Tarefa #{task.id}: {detail}")
        self.events.publish(ev.TASKS_CHANGED)
        return task

    def delete(self, task_id: int) -> None:
        self.access.require(Permission.DELETE)
        with self.db.session() as s:
            repo = TaskRepository(s)
            task = repo.require(task_id)
            self._audit(s, "task.delete", "task", task.id, task.description[:200])
            repo.delete(task)
        self.events.publish(ev.TASKS_CHANGED)

    # ------------------------------------------------------------------ leitura

    def search(
        self, text: str = "", status: str | None = None, game_id: int | None = None,
        account_id: int | None = None, priority: int | None = None, open_only: bool = False,
    ) -> Sequence[Task]:
        stmt = select(Task)
        if text:
            pattern = like_pattern(text.strip())
            stmt = stmt.outerjoin(Account, Task.account_id == Account.id).where(or_(
                Task.description.ilike(pattern, escape="\\"),
                Task.type.ilike(pattern, escape="\\"),
                Task.result.ilike(pattern, escape="\\"),
                Account.username.ilike(pattern, escape="\\"),
            ))
        if status:
            stmt = stmt.where(Task.status == status)
        if open_only:
            stmt = stmt.where(Task.status.in_(TaskStatus.OPEN))
        if game_id is not None:
            stmt = stmt.where(Task.game_id == game_id)
        if account_id is not None:
            stmt = stmt.where(Task.account_id == account_id)
        if priority is not None:
            stmt = stmt.where(Task.priority == priority)
        with self.db.session() as s:
            return s.scalars(stmt.order_by(Task.created_at.desc(), Task.id.desc())).unique().all()

    def queue(self, limit: int | None = None) -> Sequence[Task]:
        """Fila de trabalho: pendentes por prioridade (maior primeiro) e antiguidade."""
        stmt = (select(Task).where(Task.status == TaskStatus.PENDING)
                .order_by(Task.priority.desc(), Task.created_at, Task.id))
        if limit:
            stmt = stmt.limit(limit)
        with self.db.session() as s:
            return s.scalars(stmt).unique().all()

    def counts(self) -> dict[str, int]:
        with self.db.session() as s:
            rows = s.execute(select(Task.status, func.count()).group_by(Task.status)).all()
        return {status: total for status, total in rows}
