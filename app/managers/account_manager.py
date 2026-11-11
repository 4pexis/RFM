"""ACCOUNT MANAGER: cadastro, busca, importação/exportação e histórico de contas.

Apenas dados de organização são guardados (usuário, ID público, categoria...).
Senhas, cookies e tokens do Roblox não são solicitados nem armazenados.
"""
from __future__ import annotations

import csv
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable, Sequence

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core import events as ev
from app.core.security import (
    Permission, ValidationError, clean_text, normalize_tags, validate_user_id, validate_username,
)
from app.database.models import Account, AccountGame, AccountStatus, ActivityLog, Game, utcnow
from app.database.repositories import AccountRepository

from .base import BaseManager

CSV_FIELDS = ["username", "roblox_user_id", "category", "level", "status", "tags", "notes", "games"]
_ALIASES = {
    "usuario": "username", "usuário": "username", "nome": "username", "user": "username",
    "id": "roblox_user_id", "user_id": "roblox_user_id", "userid": "roblox_user_id",
    "categoria": "category", "nivel": "level", "nível": "level",
    "observacoes": "notes", "observações": "notes", "obs": "notes", "jogos": "games", "jogo": "games",
}
_STATUS_BY_LABEL = {label.lower(): key for key, label in AccountStatus.LABELS.items()}


@dataclass
class ImportResult:
    created: int = 0
    updated: int = 0
    errors: list[str] = field(default_factory=list)


class AccountManager(BaseManager):
    # ------------------------------------------------------------------ escrita

    def _apply(self, s: Session, account: Account, data: dict[str, Any]) -> None:
        if "username" in data:
            username = validate_username(data["username"])
            other = AccountRepository(s).by_username(username)
            if other is not None and other.id != account.id:
                raise ValidationError(f"Já existe uma conta com o usuário “{username}”.")
            account.username = username
        if "roblox_user_id" in data:
            account.roblox_user_id = validate_user_id(data["roblox_user_id"])
        if "category" in data:
            account.category = clean_text(data["category"], 64, "categoria")
        if "level" in data:
            try:
                level = int(data["level"] or 0)
            except (TypeError, ValueError) as exc:
                raise ValidationError("O nível deve ser um número inteiro.") from exc
            if level < 0:
                raise ValidationError("O nível não pode ser negativo.")
            account.level = level
        if "status" in data:
            status = str(data["status"] or AccountStatus.ACTIVE).strip()
            status = _STATUS_BY_LABEL.get(status.lower(), status.lower())
            if status not in AccountStatus.LABELS:
                raise ValidationError(f"Status inválido: {data['status']}")
            account.status = status
        if "notes" in data:
            account.notes = clean_text(data["notes"], 4000, "observações")
        if "tags" in data:
            account.tags = normalize_tags(data["tags"])

    def _set_games(self, s: Session, account: Account, game_ids: Iterable[int]) -> None:
        wanted = set(game_ids)
        for link in list(account.game_links):
            if link.game_id not in wanted:
                account.game_links.remove(link)
        current = {link.game_id for link in account.game_links}
        for game_id in wanted - current:
            game = s.get(Game, game_id)
            if game is None:
                raise ValidationError(f"Jogo {game_id} não encontrado.")
            account.game_links.append(AccountGame(game=game))

    def create(self, *, game_ids: Iterable[int] = (), **data: Any) -> Account:
        self.access.require(Permission.WRITE)
        with self.db.session() as s:
            account = Account(game_links=[])
            self._apply(s, account, {"username": "", "status": AccountStatus.ACTIVE, **data})
            s.add(account)
            self._set_games(s, account, game_ids)
            s.flush()
            self._audit(s, "account.create", "account", account.id, account.username)
        self.events.publish(ev.ACCOUNTS_CHANGED)
        return account

    def update(self, account_id: int, *, game_ids: Iterable[int] | None = None, **data: Any) -> Account:
        self.access.require(Permission.WRITE)
        with self.db.session() as s:
            account = AccountRepository(s).require(account_id)
            before = account.status
            self._apply(s, account, data)
            if game_ids is not None:
                self._set_games(s, account, game_ids)
            changes = ", ".join(sorted(data)) + (", games" if game_ids is not None else "")
            if account.status != before:
                changes += f" (status: {before} → {account.status})"
            self._audit(s, "account.update", "account", account.id, changes)
        self.events.publish(ev.ACCOUNTS_CHANGED)
        return account

    def delete(self, account_id: int) -> None:
        self.access.require(Permission.DELETE)
        with self.db.session() as s:
            repo = AccountRepository(s)
            account = repo.require(account_id)
            self._audit(s, "account.delete", "account", account.id, account.username)
            repo.delete(account)
        self.events.publish(ev.ACCOUNTS_CHANGED)

    def touch(self, account_id: int) -> None:
        """Atualiza a 'última atividade' (chamado por sessões, tarefas e progresso)."""
        with self.db.session() as s:
            account = s.get(Account, account_id)
            if account is not None:
                account.last_activity = utcnow()

    # ------------------------------------------------------------------ leitura

    def get(self, account_id: int) -> Account | None:
        with self.db.session() as s:
            return AccountRepository(s).get(account_id)

    def search(
        self, text: str = "", game_id: int | None = None,
        status: str | None = None, category: str | None = None,
    ) -> Sequence[Account]:
        with self.db.session() as s:
            return AccountRepository(s).search(text, game_id, status, category)

    def all(self) -> Sequence[Account]:
        return self.search()

    def categories(self) -> list[str]:
        with self.db.session() as s:
            rows = s.scalars(select(Account.category).distinct().order_by(Account.category)).all()
        return [c for c in rows if c]

    def count(self) -> int:
        with self.db.session() as s:
            return s.scalar(select(func.count()).select_from(Account)) or 0

    def history(self, account_id: int, limit: int = 200) -> Sequence[ActivityLog]:
        with self.db.session() as s:
            return s.scalars(
                select(ActivityLog)
                .where(ActivityLog.entity_type == "account", ActivityLog.entity_id == account_id)
                .order_by(ActivityLog.timestamp.desc()).limit(limit)
            ).all()

    # ---------------------------------------------------------------------- CSV

    def import_csv(self, path: str | Path) -> ImportResult:
        """Importa contas de um CSV (separador ',' ou ';').

        Colunas: username (obrigatória), roblox_user_id, category, level, status,
        tags, notes, games (nomes separados por '|'). Usuários já cadastrados
        são atualizados.
        """
        self.access.require(Permission.WRITE)
        result = ImportResult()
        with open(path, newline="", encoding="utf-8-sig") as handle:
            sample = handle.read(4096)
            handle.seek(0)
            delimiter = ";" if sample.count(";") > sample.count(",") else ","
            rows = list(csv.DictReader(handle, delimiter=delimiter))

        with self.db.session() as s:
            repo = AccountRepository(s)
            games = {g.name.lower(): g.id for g in s.scalars(select(Game)).all()}
            for line, raw in enumerate(rows, start=2):
                row: dict[str, str] = {}
                for key, value in raw.items():
                    name = (key or "").strip().lower()
                    row[_ALIASES.get(name, name)] = (value or "").strip()
                try:
                    username = validate_username(row.get("username", ""))
                    data = {k: row[k] for k in CSV_FIELDS[1:-1] if row.get(k, "") != ""}
                    game_ids = None
                    if row.get("games"):
                        names = [n.strip() for n in row["games"].split("|") if n.strip()]
                        unknown = [n for n in names if n.lower() not in games]
                        if unknown:
                            raise ValidationError(f"jogo(s) não cadastrado(s): {', '.join(unknown)}")
                        game_ids = [games[n.lower()] for n in names]
                    with s.begin_nested():  # erro em uma linha não desfaz as demais
                        account = repo.by_username(username)
                        created = account is None
                        if account is None:
                            account = Account(username=username, game_links=[])
                            s.add(account)
                        self._apply(s, account, data)
                        if game_ids is not None:
                            self._set_games(s, account, game_ids)
                        s.flush()
                    if created:
                        result.created += 1
                    else:
                        result.updated += 1
                except ValidationError as exc:
                    result.errors.append(f"Linha {line}: {exc}")
            self._audit(s, "account.import", "account", None,
                        f"{Path(path).name}: {result.created} novas, {result.updated} atualizadas, "
                        f"{len(result.errors)} erros")
        self.events.publish(ev.ACCOUNTS_CHANGED)
        return result

    def export_csv(self, path: str | Path, accounts: Sequence[Account] | None = None) -> int:
        accounts = self.all() if accounts is None else accounts
        with open(path, "w", newline="", encoding="utf-8-sig") as handle:
            writer = csv.writer(handle)
            writer.writerow(CSV_FIELDS)
            for a in accounts:
                writer.writerow([
                    a.username, a.roblox_user_id or "", a.category, a.level, a.status,
                    a.tags, a.notes, "|".join(sorted(g.name for g in a.games)),
                ])
        with self.db.session() as s:
            self._audit(s, "account.export", "account", None, f"{Path(path).name}: {len(accounts)} contas")
        return len(accounts)
