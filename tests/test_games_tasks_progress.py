from __future__ import annotations

import pytest

from app.core.security import ValidationError
from app.database.models import IntegrationStatus, ProgressKind, TaskPriority, TaskStatus
from app.managers.progress_manager import parse_number

INITIAL_GAMES = {
    "Blox Fruits", "King Legacy", "Fisch", "Bee Swarm Simulator", "Pet Simulator 99", "Adopt Me!",
    "Murder Mystery 2", "Shindo Life", "Sol's RNG", "Grow a Garden", "Fish It", "Anime Adventures",
}


def test_initial_catalog_from_modules(ctx):
    games = ctx.games.all()
    assert {g.name for g in games} == INITIAL_GAMES
    assert not ctx.plugins.load_errors
    assert all(g.integration_status == IntegrationStatus.MODULE and g.objectives for g in games)
    assert ctx.games.sync_modules() == 0  # idempotente
    assert len(ctx.games.all()) == 12


def test_custom_game_without_touching_core(ctx):
    game = ctx.games.create(name="Jogo Novo", experience_id="123456", category="Teste",
                            objectives=[{"name": "Fase atual"}])
    assert game.slug == "jogo_novo" and game.integration_status == IntegrationStatus.MANUAL
    assert ctx.games.objectives(game)[0]["name"] == "Fase atual"
    with pytest.raises(ValidationError):
        ctx.games.create(name="jogo novo")  # duplicado
    with pytest.raises(ValidationError):
        ctx.games.create(name="Outro", experience_id="12ab")
    ctx.games.delete(game.id)
    module_game = next(g for g in ctx.games.all() if g.slug == "fish")
    with pytest.raises(ValidationError):
        ctx.games.delete(module_game.id)  # jogos de módulo não são excluídos


def test_task_lifecycle_and_queue(ctx):
    account = ctx.accounts.create(username="tarefeiro")
    game = ctx.games.all()[0]
    low = ctx.tasks.create(account_id=account.id, game_id=game.id, description="baixa",
                           priority=TaskPriority.LOW)
    urgent = ctx.tasks.create(description="urgente", priority=TaskPriority.URGENT)
    normal = ctx.tasks.create(description="normal")
    assert [t.id for t in ctx.tasks.queue()] == [urgent.id, normal.id, low.id]

    with pytest.raises(ValidationError):
        ctx.tasks.create(description="   ")
    with pytest.raises(ValidationError):
        ctx.tasks.set_status(low.id, TaskStatus.PAUSED)  # pendente não pausa

    running = ctx.tasks.set_status(low.id, TaskStatus.RUNNING)
    assert running.started_at is not None and running.account.username == "tarefeiro"
    done = ctx.tasks.set_status(low.id, TaskStatus.DONE, result="feito")
    assert done.finished_at is not None and done.result == "feito"
    assert ctx.tasks.counts() == {TaskStatus.PENDING: 2, TaskStatus.DONE: 1}
    assert [t.id for t in ctx.tasks.search("tarefeiro")] == [low.id]  # busca pelo usuário
    assert len(ctx.tasks.search(open_only=True)) == 2
    assert ctx.accounts.get(account.id).last_activity is not None

    reopened = ctx.tasks.set_status(low.id, TaskStatus.PENDING)
    assert reopened.started_at is None and reopened.finished_at is None


def test_progress_records(ctx):
    game = next(g for g in ctx.games.all() if g.slug == "blox_fruits")
    account = ctx.accounts.create(username="progresso", game_ids=[game.id])
    ctx.progress.record(account_id=account.id, game_id=game.id, name="Nível", value="700",
                        kind=ProgressKind.LEVEL)
    ctx.progress.record(account_id=account.id, game_id=game.id, name="Nível", value="1.500",
                        kind=ProgressKind.LEVEL)
    ctx.progress.record(account_id=account.id, game_id=game.id, name="Fruta equipada", value="Buddha",
                        kind=ProgressKind.ITEM)

    with pytest.raises(ValidationError):  # o módulo conhece o nível máximo
        ctx.progress.record(account_id=account.id, game_id=game.id, name="Nível", value="99999",
                            kind=ProgressKind.LEVEL)
    with pytest.raises(ValidationError):
        ctx.progress.record(account_id=account.id, game_id=game.id, name="Nível", value="alto",
                            kind=ProgressKind.LEVEL)

    refreshed = ctx.accounts.get(account.id)
    assert refreshed.level == 1500 and refreshed.game_links[0].level == 1500
    latest = {r.name: r.value for r in ctx.progress.latest(account.id)}
    assert latest == {"Nível": "1.500", "Fruta equipada": "Buddha"}
    assert len(ctx.progress.search(game_id=game.id)) == 3
    assert len(ctx.progress.search("buddha")) == 1
    stats = ctx.progress.game_statistics(game.id)
    assert stats["registros"] == 3 and stats["maiores_valores"]["Nível"] == 1500


@pytest.mark.parametrize("text,expected", [
    ("1500", 1500), ("1.500", 1500), ("1,5k", 1500), ("2m", 2_000_000), ("1.234,5", 1234.5),
    ("3.5", 3.5), ("Buddha", None), ("", None),
])
def test_parse_number(text, expected):
    assert parse_number(text) == expected
