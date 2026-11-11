"""GAME MANAGER: catálogo de jogos e vínculo com os módulos (plugins)."""
from __future__ import annotations

import re
from typing import Any, Sequence

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core import events as ev
from app.core.security import Permission, ValidationError, clean_text, validate_experience_id
from app.database.models import AccountGame, Game, GameIntegration, IntegrationStatus, utcnow
from app.database.repositories import GameRepository
from app.game_modules.base import GameModule

from .base import BaseManager
from .plugin_manager import PluginManager


def slugify(name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_")
    if not slug:
        raise ValidationError("Nome de jogo inválido.")
    return slug[:64]


class GameManager(BaseManager):
    def __init__(self, *args, plugins: PluginManager, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.plugins = plugins

    def module_for(self, game: Game | None) -> GameModule:
        return self.plugins.get(game.slug if game else "")

    # ------------------------------------------------------- sincronia de plugins

    def sync_modules(self) -> int:
        """Garante um registro no catálogo para cada módulo carregado.

        Jogos já existentes mantêm os dados editados pelo usuário; apenas o
        estado da integração é atualizado. Retorna quantos jogos foram criados.
        """
        created = 0
        with self.db.session() as s:
            repo = GameRepository(s)
            for slug, module in self.plugins.modules.items():
                info = module.identify()
                game = repo.by_slug(slug)
                if game is None:
                    game = repo.add(Game(
                        name=info.name, slug=slug, experience_id=info.experience_id,
                        category=info.category, description=info.description, icon=info.icon,
                        objectives=[o.to_dict() for o in module.objectives()],
                    ))
                    created += 1
                game.module_name = slug
                if not game.icon.isascii():  # bancos antigos guardavam um emoji
                    game.icon = info.icon
                if game.integration_status != IntegrationStatus.DISABLED:
                    game.integration_status = IntegrationStatus.MODULE
                self._touch_integration(s, game, module.version, "")
            # Jogos cujo módulo deixou de existir voltam ao acompanhamento manual.
            for game in repo.list():
                if game.module_name and not self.plugins.has(game.module_name):
                    game.integration_status = IntegrationStatus.MANUAL
                    self._touch_integration(s, game, "", "módulo não encontrado")
        if created:
            self.events.publish(ev.GAMES_CHANGED)
        return created

    @staticmethod
    def _touch_integration(s: Session, game: Game, version: str, error: str) -> None:
        row = s.scalars(select(GameIntegration).where(GameIntegration.game_id == game.id)).first()
        if row is None:
            row = GameIntegration(game_id=game.id, module_name=game.module_name)
            s.add(row)
        row.module_name, row.version = game.module_name, version
        row.last_loaded, row.last_error = utcnow(), error
        row.enabled = game.integration_status != IntegrationStatus.DISABLED

    # ------------------------------------------------------------------ escrita

    def _apply(self, s: Session, game: Game, data: dict[str, Any]) -> None:
        if "name" in data:
            name = clean_text(data["name"], 128, "nome")
            if not name:
                raise ValidationError("Informe o nome do jogo.")
            clash = s.scalars(select(Game).where(func.lower(Game.name) == name.lower())).first()
            if clash is not None and clash.id != game.id:
                raise ValidationError(f"O jogo “{name}” já está cadastrado.")
            game.name = name
        if "experience_id" in data:
            game.experience_id = validate_experience_id(data["experience_id"])
        for key, size in (("category", 64), ("description", 2000), ("icon", 255)):
            if key in data:
                setattr(game, key, clean_text(data[key], size, key))
        if "integration_status" in data:
            if data["integration_status"] not in IntegrationStatus.LABELS:
                raise ValidationError("Status de integração inválido.")
            game.integration_status = data["integration_status"]
        if "objectives" in data:
            game.objectives = [
                {"key": slugify(o["name"]), "kind": "objective", "description": "", "max_value": None, **o}
                for o in data["objectives"] if str(o.get("name", "")).strip()
            ]

    def create(self, **data: Any) -> Game:
        self.access.require(Permission.WRITE)
        with self.db.session() as s:
            game = Game(objectives=[], module_name="", integration_status=IntegrationStatus.MANUAL)
            self._apply(s, game, {"name": "", **data})
            slug = base = slugify(game.name)
            repo, n = GameRepository(s), 2
            while repo.by_slug(slug) is not None:
                slug, n = f"{base[:60]}_{n}", n + 1
            game.slug = slug
            repo.add(game)
            self._audit(s, "game.create", "game", game.id, game.name)
        self.events.publish(ev.GAMES_CHANGED)
        return game

    def update(self, game_id: int, **data: Any) -> Game:
        self.access.require(Permission.WRITE)
        with self.db.session() as s:
            game = GameRepository(s).require(game_id)
            self._apply(s, game, data)
            self._audit(s, "game.update", "game", game.id, ", ".join(sorted(data)))
        self.events.publish(ev.GAMES_CHANGED)
        return game

    def delete(self, game_id: int) -> None:
        self.access.require(Permission.DELETE)
        with self.db.session() as s:
            repo = GameRepository(s)
            game = repo.require(game_id)
            if game.module_name and self.plugins.has(game.module_name):
                raise ValidationError(
                    "Este jogo pertence a um módulo instalado; desative a integração em vez de excluir."
                )
            self._audit(s, "game.delete", "game", game.id, game.name)
            repo.delete(game)
        self.events.publish(ev.GAMES_CHANGED)

    # ------------------------------------------------------------------ leitura

    def all(self) -> Sequence[Game]:
        with self.db.session() as s:
            return GameRepository(s).list(order_by=Game.name)

    def get(self, game_id: int) -> Game | None:
        with self.db.session() as s:
            return GameRepository(s).get(game_id)

    def account_counts(self) -> dict[int, int]:
        with self.db.session() as s:
            rows = s.execute(
                select(AccountGame.game_id, func.count()).group_by(AccountGame.game_id)
            ).all()
        return {game_id: total for game_id, total in rows}

    def objectives(self, game: Game | None) -> list[dict[str, Any]]:
        """Objetivos do catálogo; se vazio, os do módulo."""
        if game is None:
            return []
        return list(game.objectives or []) or [o.to_dict() for o in self.module_for(game).objectives()]
