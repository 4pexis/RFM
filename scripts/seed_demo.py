"""Preenche o banco com dados FICTÍCIOS de demonstração.

    python scripts/seed_demo.py [quantidade_de_contas]

Use apenas em um banco de testes (ex.: defina RFM_DATA_DIR para outra pasta).
"""
from __future__ import annotations

import random
import sys
from datetime import timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.bootstrap import bootstrap  # noqa: E402
from app.database.models import (  # noqa: E402
    AccountStatus, PlaySession, SessionStatus, Task, TaskPriority, TaskStatus, utcnow,
)


def main(total: int = 500) -> None:
    random.seed(7)
    ctx = bootstrap()
    if ctx.accounts.count():
        print("O banco já possui contas — nada foi alterado.")
        return
    games = list(ctx.games.all())
    statuses = [AccountStatus.ACTIVE] * 6 + [AccountStatus.PAUSED] * 2 + [
        AccountStatus.TRACKING, AccountStatus.DONE, AccountStatus.ERROR, AccountStatus.ARCHIVED]
    accounts = []
    for i in range(1, total + 1):
        linked = random.sample(games, random.randint(1, 3))
        accounts.append(ctx.accounts.create(
            username=f"demo_farm_{i:04d}", roblox_user_id=1_000_000 + i,
            category=f"Lote {chr(65 + i % 5)}", status=random.choice(statuses),
            tags=random.choice(["", "main", "alt", "alt,evento", "vip"]),
            game_ids=[g.id for g in linked],
        ))
    now = utcnow()
    for account in random.sample(accounts, min(len(accounts), 150)):
        game = random.choice(account.games)
        for obj in random.sample(ctx.games.objectives(game), 2):
            numeric = obj["kind"] in ("level", "stat")
            top = int(obj.get("max_value") or 5000)
            value = str(random.randint(1, top)) if numeric else random.choice(["Obtido", "Raro", "Concluído"])
            ctx.progress.record(account_id=account.id, game_id=game.id, name=obj["name"],
                                kind=obj["kind"], value=value)
    with ctx.db.session() as s:
        for account in random.sample(accounts, min(len(accounts), 120)):
            game = random.choice(account.games)
            for _ in range(random.randint(1, 3)):  # sessões encerradas nos últimos 14 dias
                start = now - timedelta(days=random.uniform(0, 14))
                seconds = random.randint(600, 4 * 3600)
                s.add(PlaySession(
                    account_id=account.id, game_id=game.id, manual=True, process_name="(manual)",
                    status=SessionStatus.ENDED, started_at=start,
                    ended_at=start + timedelta(seconds=seconds), duration_s=seconds,
                ))
            status = random.choice([TaskStatus.PENDING, TaskStatus.PENDING, TaskStatus.RUNNING,
                                    TaskStatus.DONE, TaskStatus.DONE, TaskStatus.DONE, TaskStatus.PAUSED])
            created = now - timedelta(days=random.uniform(0, 7))
            s.add(Task(
                account_id=account.id, game_id=game.id, type=random.choice(["Progressão", "Coleta", "Evento"]),
                description=f"Acompanhar {random.choice(ctx.games.objectives(game))['name'].lower()}",
                priority=random.choice(list(TaskPriority.LABELS)), status=status, created_at=created,
                started_at=created if status != TaskStatus.PENDING else None,
                finished_at=created + timedelta(hours=random.uniform(1, 20)) if status == TaskStatus.DONE else None,
                result="ok" if status == TaskStatus.DONE else "",
            ))
    print(f"{total} contas de demonstração criadas em {ctx.settings.database_url}")
    ctx.shutdown()


if __name__ == "__main__":
    main(int(sys.argv[1]) if len(sys.argv) > 1 else 500)
