from __future__ import annotations

import sys
import threading
import time

import pytest
from sqlalchemy import inspect

from app.core.bootstrap import bootstrap
from app.core.events import EventBus
from app.core.security import (
    Role, ValidationError, hash_pin, normalize_tags, protect, unprotect, verify_pin,
)
from app.database.connection import Database
from app.database.models import Base
from app.database.transfer import copy_database
from app.services.scheduler import Scheduler
from app.workers.task_worker import PRIORITY_HIGH, PRIORITY_LOW, AdminTaskQueue


def test_migrations_match_models(tmp_path):
    """O esquema criado pelo Alembic deve ser igual ao dos modelos."""
    from alembic.autogenerate import compare_metadata
    from alembic.migration import MigrationContext

    db = Database(f"sqlite:///{(tmp_path / 'm.db').as_posix()}")
    db.migrate()
    db.migrate()  # idempotente
    assert set(Base.metadata.tables) <= set(inspect(db.engine).get_table_names())
    with db.engine.connect() as conn:
        diff = compare_metadata(MigrationContext.configure(conn), Base.metadata)
    db.dispose()
    assert diff == []


def test_backup_and_restore(settings, provider):
    ctx = bootstrap(settings, migrate=True, provider=provider, configure_logging=False)
    try:
        ctx.accounts.create(username="antes_backup")
        backup = ctx.backups.create("manual")
        ctx.accounts.create(username="depois_backup")
        assert ctx.accounts.count() == 2

        safety = ctx.backups.restore(backup)
        assert [a.username for a in ctx.accounts.all()] == ["antes_backup"]
        assert safety.exists() and len(ctx.backups.list_backups()) == 2

        fake = settings.backup_dir / "rfm_fake.db"
        fake.write_text("isto não é um banco")
        with pytest.raises(ValidationError):
            ctx.backups.restore(fake)

        for _ in range(4):
            ctx.backups.create("auto")
            time.sleep(1.05)  # nome do arquivo tem resolução de 1 segundo
        ctx.backups.prune(2)
        names = [p.name for p in ctx.backups.list_backups()]
        assert sum(n.endswith("_auto.db") for n in names) == 2
        assert any("manual" in n for n in names)  # backups manuais nunca são apagados
    finally:
        ctx.shutdown()


def test_copy_database_between_engines(ctx, tmp_path):
    """Mesma rotina usada na migração SQLite -> PostgreSQL."""
    game = ctx.games.all()[0]
    account = ctx.accounts.create(username="migrada", game_ids=[game.id])
    ctx.tasks.create(account_id=account.id, description="levar junto")
    target_url = f"sqlite:///{(tmp_path / 'destino.db').as_posix()}"
    copied = copy_database(ctx.settings.database_url, target_url)
    assert copied["accounts"] == 1 and copied["games"] == 12 and copied["tasks"] == 1
    assert copied["account_games"] == 1
    with pytest.raises(RuntimeError):
        copy_database(ctx.settings.database_url, target_url)  # destino precisa estar vazio


def test_security_helpers():
    stored = hash_pin("1234")
    assert verify_pin("1234", stored) and not verify_pin("0000", stored) and not verify_pin("1234", "x")
    secret = protect("valor secreto ç")
    assert unprotect(secret) == "valor secreto ç"
    if sys.platform == "win32":
        assert secret.startswith("dpapi:") and "secreto" not in secret
    assert normalize_tags(" B, a;b ,, C ") == "a,b,c"


def test_role_change_requires_pin(ctx):
    ctx.config.set_pin("4321")
    ctx.config.change_role(Role.VIEWER)
    with pytest.raises(ValidationError):
        ctx.config.change_role(Role.ADMIN, "0000")
    assert ctx.access.role == Role.VIEWER
    ctx.config.change_role(Role.ADMIN, "4321")
    assert ctx.access.role == Role.ADMIN
    with ctx.db.session() as s:  # o PIN nunca fica em texto puro no banco
        from app.database.models import SystemSetting
        raw = s.get(SystemSetting, "security.pin_hash").value
    assert "4321" not in raw


def test_settings_persist_and_validate(ctx):
    ctx.config.set_many({"monitor.cpu_alert": 75, "backup.enabled": False})
    ctx.config.reload()
    assert ctx.config.get("monitor.cpu_alert") == 75 and ctx.config.get("backup.enabled") is False
    with pytest.raises(ValidationError):
        ctx.config.set_many({"nao.existe": 1})
    with pytest.raises(ValidationError):
        ctx.config.set_many({"backup.keep": -1})


def test_event_bus_isolates_failures():
    bus, seen = EventBus(), []
    bus.subscribe("x", lambda e, p: 1 / 0)
    bus.subscribe("x", lambda e, p: seen.append(p))
    bus.subscribe("*", lambda e, p: seen.append(e))
    bus.publish("x", 42)
    assert seen == [42, "x"]


def test_admin_queue_priority_and_errors():
    queue, order, gate = AdminTaskQueue(EventBus(), max_workers=1), [], threading.Event()
    queue.start()
    blocker = queue.submit("bloqueio", gate.wait)
    low = queue.submit("baixa", lambda: order.append("baixa"), PRIORITY_LOW)
    high = queue.submit("alta", lambda: order.append("alta"), PRIORITY_HIGH)
    failing = queue.submit("erro", lambda: 1 / 0)
    gate.set()
    for future in (blocker, low, high):
        future.result(timeout=5)
    with pytest.raises(ZeroDivisionError):
        failing.result(timeout=5)
    assert order == ["alta", "baixa"]
    queue.stop()


def test_admin_queue_stops_all_workers():
    queue = AdminTaskQueue(EventBus(), max_workers=3)
    queue.start()
    assert queue.submit("soma", lambda: 1 + 1).result(timeout=5) == 2
    queue.stop()
    for thread in queue._threads:
        thread.join(timeout=5)
        assert not thread.is_alive()


def test_scheduler_runs_jobs_and_survives_errors():
    scheduler, calls = Scheduler(), []
    scheduler.every("ok", 0.5, lambda: calls.append(1))
    scheduler.every("falha", 0.5, lambda: 1 / 0)
    scheduler.start()
    time.sleep(1.6)
    scheduler.stop()
    assert 2 <= len(calls) <= 4
