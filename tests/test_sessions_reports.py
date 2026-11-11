from __future__ import annotations

from datetime import timedelta

import pytest

from app.core.security import ValidationError
from app.database.models import PlaySession, SessionStatus, TaskStatus, utcnow
from app.services.monitoring import HardwareMonitor, ProcessInfo

ROBLOX = "RobloxPlayerBeta.exe"


def proc(pid: int, cpu: float = 5.0, mem: float = 800.0, name: str = ROBLOX) -> ProcessInfo:
    return ProcessInfo(pid=pid, name=name, create_time=1_700_000_000.0 + pid, cpu_percent=cpu, memory_mb=mem)


def test_detects_and_closes_sessions(ctx, provider):
    provider.processes = [proc(100), proc(200, mem=1200), proc(300, name="notepad.exe")]
    assert ctx.sessions.scan() is True
    sessions = ctx.sessions.open_sessions()
    assert sorted(s.pid for s in sessions) == [100, 200]  # só processos Roblox
    assert ctx.sessions.scan() is False  # nada mudou

    provider.processes = [proc(100, cpu=15, mem=950)]
    assert ctx.sessions.scan() is True
    still_open = ctx.sessions.open_sessions()
    assert [s.pid for s in still_open] == [100]
    assert still_open[0].memory_peak_mb == 950 and still_open[0].cpu_avg == pytest.approx(10.0)
    closed = ctx.sessions.history()
    assert [s.pid for s in closed] == [200] and closed[0].status == SessionStatus.ENDED

    # PID reutilizado por outro processo = nova sessão
    provider.processes = [ProcessInfo(100, ROBLOX, 1_800_000_000.0, 1.0, 500.0)]
    ctx.sessions.scan()
    assert len(ctx.sessions.history()) == 2 and len(ctx.sessions.open_sessions()) == 1


def test_idle_detection_and_manual_flags(ctx, provider):
    provider.processes = [proc(1, cpu=0.0)]
    ctx.sessions.scan()
    session = ctx.sessions.open_sessions()[0]
    assert session.status == SessionStatus.ACTIVE
    with ctx.db.session() as s:  # simula 11 minutos sem atividade
        s.get(PlaySession, session.id).idle_since = utcnow() - timedelta(minutes=11)
    ctx.sessions.scan()
    assert ctx.sessions.open_sessions()[0].status == SessionStatus.IDLE
    assert len(ctx.sessions.problems()) == 1

    provider.processes = [proc(1, cpu=20.0)]
    ctx.sessions.scan()
    assert ctx.sessions.open_sessions()[0].status == SessionStatus.ACTIVE

    ctx.sessions.set_problem(session.id, True)
    ctx.sessions.scan()
    assert ctx.sessions.open_sessions()[0].status == SessionStatus.PROBLEM  # marcação manual é mantida


def test_assign_manual_session_and_reports(ctx, provider):
    game = next(g for g in ctx.games.all() if g.slug == "fish")
    account = ctx.accounts.create(username="sessao_user", game_ids=[game.id])

    provider.processes = [proc(10)]
    ctx.sessions.scan()
    detected = ctx.sessions.open_sessions()[0]
    assigned = ctx.sessions.assign(detected.id, account.id, game.id)
    assert assigned.account.username == "sessao_user" and assigned.game.name == "Fisch"

    manual = ctx.sessions.start_manual(account.id, game.id, "acompanhamento manual")
    with ctx.db.session() as s:  # a sessão manual começou há 2 horas
        s.get(PlaySession, manual.id).started_at = utcnow() - timedelta(hours=2)
    ended = ctx.sessions.end(manual.id)
    assert ended.status == SessionStatus.ENDED and 7190 <= ended.duration_s <= 7210
    ctx.sessions.scan()
    assert ctx.sessions.history()[0].id == manual.id  # manuais não são afetadas pela varredura

    task = ctx.tasks.create(account_id=account.id, game_id=game.id, description="pescar")
    ctx.tasks.set_status(task.id, TaskStatus.DONE)
    ctx.progress.record(account_id=account.id, game_id=game.id, name="Moedas (C$)", value="10k")

    summary = ctx.reports.summary()
    assert (summary.total_accounts, summary.total_games, summary.active_accounts) == (1, 12, 1)
    assert (summary.done_tasks, summary.pending_tasks, summary.open_sessions) == (1, 0, 1)
    assert summary.total_seconds >= 7190

    start, end = utcnow() - timedelta(days=1), utcnow() + timedelta(minutes=1)
    row = ctx.reports.time_report(start, end, "account")[0]
    assert (row.label, row.sessions, row.tasks_done, row.progress_records) == ("sessao_user", 2, 1, 1)
    assert row.seconds >= 7190
    assert ctx.reports.time_report(start, end, "game")[0].label == "Fisch"
    # Só a parte de cada sessão dentro do período é contada: na última hora, a
    # sessão detectada (aberta desde 2023) e a manual (2 h) valem ~1 h cada.
    partial = ctx.reports.time_report(utcnow() - timedelta(hours=1), end, "account")[0]
    assert 7190 <= partial.seconds <= 7330
    assert 86400 + 7190 <= row.seconds <= 86400 + 7330

    assert dict(ctx.reports.accounts_per_game())["Fisch"] == 1
    assert ctx.reports.status_distribution() == [("Ativa", 1)]
    assert ctx.reports.weekly_productivity()[-1][1] == 1
    assert ctx.reports.daily_activity()[-1][1] > 0
    assert dict(ctx.reports.progress_per_game())["Fisch"] == 1


def test_launch_urls(ctx):
    deep, web = ctx.sessions.experience_urls("2753915549")
    assert deep == "roblox://experiences/start?placeId=2753915549"
    assert web == "https://www.roblox.com/games/2753915549"
    for bad in ("", "12; calc.exe", "abc"):
        with pytest.raises(ValidationError):
            ctx.sessions.experience_urls(bad)


def test_hardware_monitor(ctx):
    snap = ctx.monitor.collect([proc(1)], session_count=1)
    assert 0 <= snap.cpu_percent <= 100 and 0 < snap.memory_percent <= 100 and snap.disk_total_gb > 0
    ctx.monitor.persist(snap)
    assert len(ctx.monitor.history()) == 1
    alerts = HardwareMonitor.check_alerts(snap, cpu=0, ram=1, disk=101)
    assert [a.resource for a in alerts] == ["ram"]  # 0 desativa; 101 nunca dispara
    assert "Memória RAM" in alerts[0].message
