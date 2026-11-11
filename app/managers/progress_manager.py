"""PROGRESS MANAGER: níveis, conquistas, itens, objetivos e estatísticas."""
from __future__ import annotations

from typing import Any, Sequence

from sqlalchemy import func, select

from app.core import events as ev
from app.core.security import Permission, ValidationError, clean_text
from app.database.models import Account, AccountGame, Game, ProgressKind, ProgressRecord, utcnow
from app.database.repositories import ProgressRepository, like_pattern

from .base import BaseManager
from .game_manager import GameManager


def parse_number(value: object) -> float | None:
    """'1.500' / '1,5k' / '2m' -> número; texto livre -> None."""
    text = str(value or "").strip().lower().replace(" ", "")
    if not text:
        return None
    multiplier = 1.0
    if text[-1] in "kmb":
        multiplier = {"k": 1e3, "m": 1e6, "b": 1e9}[text[-1]]
        text = text[:-1]
    if "," in text and "." in text:  # 1.234,5 (pt-BR)
        text = text.replace(".", "").replace(",", ".")
    elif "," in text:
        text = text.replace(",", ".")
    elif text.count(".") == 1 and len(text.split(".")[1]) == 3 and multiplier == 1.0:
        text = text.replace(".", "")  # 1.500 = mil e quinhentos
    try:
        return float(text) * multiplier
    except ValueError:
        return None


class ProgressManager(BaseManager):
    def __init__(self, *args, games: GameManager, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.games = games

    def record(
        self, *, account_id: int, game_id: int | None, name: str, value: str,
        kind: str = ProgressKind.OBJECTIVE, notes: str = "",
    ) -> ProgressRecord:
        self.access.require(Permission.WRITE)
        name = clean_text(name, 128, "objetivo")
        value = clean_text(value, 255, "valor")
        if not name:
            raise ValidationError("Informe o objetivo/indicador.")
        if kind not in ProgressKind.LABELS:
            raise ValidationError("Tipo de registro inválido.")
        numeric = parse_number(value)
        with self.db.session() as s:
            account = s.get(Account, account_id)
            if account is None:
                raise ValidationError("Conta não encontrada.")
            game = s.get(Game, game_id) if game_id else None
            module = self.games.module_for(game)
            try:
                module.validate_progress(name, value, numeric)
            except ValidationError:
                raise
            except Exception as exc:  # falha do módulo não impede o registro manual
                module.report_error(exc)
            record = ProgressRepository(s).add(ProgressRecord(
                account_id=account_id, game_id=game_id, kind=kind, name=name, value=value,
                numeric_value=numeric, notes=clean_text(notes, 2000, "observações"),
            ))
            s.refresh(record)
            account.last_activity = utcnow()
            if kind == ProgressKind.LEVEL and numeric is not None:
                # O nível registrado passa a ser o nível da conta naquele jogo.
                link = s.get(AccountGame, (account_id, game_id)) if game_id else None
                if link is not None:
                    link.level = int(numeric)
                account.level = max(account.level, int(numeric))
            self._audit(s, "progress.record", "account", account_id,
                        f"{game.name if game else 'Geral'} · {name}: {value}")
        self.events.publish(ev.PROGRESS_CHANGED)
        return record

    def delete(self, record_id: int) -> None:
        self.access.require(Permission.DELETE)
        with self.db.session() as s:
            repo = ProgressRepository(s)
            record = repo.require(record_id)
            self._audit(s, "progress.delete", "account", record.account_id, f"{record.name}: {record.value}")
            repo.delete(record)
        self.events.publish(ev.PROGRESS_CHANGED)

    def search(
        self, text: str = "", account_id: int | None = None, game_id: int | None = None,
        kind: str | None = None, limit: int = 2000,
    ) -> Sequence[ProgressRecord]:
        stmt = select(ProgressRecord)
        if text:
            pattern = like_pattern(text.strip())
            stmt = stmt.join(Account, ProgressRecord.account_id == Account.id).where(
                ProgressRecord.name.ilike(pattern, escape="\\")
                | ProgressRecord.value.ilike(pattern, escape="\\")
                | Account.username.ilike(pattern, escape="\\")
            )
        if account_id is not None:
            stmt = stmt.where(ProgressRecord.account_id == account_id)
        if game_id is not None:
            stmt = stmt.where(ProgressRecord.game_id == game_id)
        if kind:
            stmt = stmt.where(ProgressRecord.kind == kind)
        stmt = stmt.order_by(ProgressRecord.recorded_at.desc(), ProgressRecord.id.desc()).limit(limit)
        with self.db.session() as s:
            return s.scalars(stmt).unique().all()

    def latest(self, account_id: int) -> Sequence[ProgressRecord]:
        """Valor mais recente de cada indicador da conta (por jogo)."""
        newest = (
            select(func.max(ProgressRecord.id))
            .where(ProgressRecord.account_id == account_id)
            .group_by(ProgressRecord.game_id, ProgressRecord.name)
        )
        with self.db.session() as s:
            return s.scalars(
                select(ProgressRecord).where(ProgressRecord.id.in_(newest))
                .order_by(ProgressRecord.game_id, ProgressRecord.name)
            ).unique().all()

    def game_statistics(self, game_id: int) -> dict[str, Any]:
        with self.db.session() as s:
            game = s.get(Game, game_id)
            records = s.scalars(select(ProgressRecord).where(ProgressRecord.game_id == game_id)).unique().all()
        module = self.games.module_for(game)
        try:
            return module.statistics(records)
        except Exception as exc:
            module.report_error(exc)
            return {"registros": len(records)}
