"""Teste de fumaça da interface: abre todas as telas sem exibir janelas."""
from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest  # noqa: E402

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication  # noqa: E402

from app.core import events as ev  # noqa: E402
from app.database.models import TaskStatus  # noqa: E402
from app.services.monitoring import Alert, ProcessInfo  # noqa: E402
from app.ui.accounts.page import AccountDialog, HistoryDialog  # noqa: E402
from app.ui.games.page import GameDialog  # noqa: E402
from app.ui.main_window import NAVIGATION, MainWindow  # noqa: E402
from app.ui.progress.page import ProgressDialog  # noqa: E402
from app.ui.sessions.page import SessionDialog  # noqa: E402
from app.ui.tasks.page import TaskDialog  # noqa: E402
from app.ui.theme import STYLESHEET  # noqa: E402


@pytest.fixture(scope="module")
def qt_app():
    app = QApplication.instance() or QApplication([])
    app.setStyleSheet(STYLESHEET)
    return app


def test_all_pages_render_with_data(qt_app, ctx, provider):
    game = next(g for g in ctx.games.all() if g.slug == "blox_fruits")
    account = ctx.accounts.create(username="ui_user", category="Lote A", game_ids=[game.id])
    task = ctx.tasks.create(account_id=account.id, game_id=game.id, description="tarefa de tela")
    ctx.tasks.set_status(task.id, TaskStatus.DONE)
    ctx.progress.record(account_id=account.id, game_id=game.id, name="Nível", value="900", kind="level")
    provider.processes = [ProcessInfo(4242, "RobloxPlayerBeta.exe", 1_700_000_000.0, 3.0, 900.0)]
    ctx.sessions.scan()
    session = ctx.sessions.open_sessions()[0]

    window = MainWindow(ctx)
    window.show()
    assert len(window.pages) == len(NAVIGATION) == 9
    for _ in range(3):  # o gráfico ao vivo precisa de pelo menos duas amostras
        ctx.events.publish(ev.HARDWARE_SNAPSHOT, ctx.monitor.collect(provider.processes, 1))
    ctx.events.publish(ev.HARDWARE_ALERT, Alert("cpu", 95, 90))
    for index in range(len(NAVIGATION)):
        window.show_page(index)
        qt_app.processEvents()

    accounts_page, tasks_page = window.pages[1], window.pages[4]
    assert [a.username for a in accounts_page.table.rows()] == ["ui_user"]
    accounts_page.search.setText("inexistente")
    accounts_page.refresh()
    assert accounts_page.table.rows() == []
    assert len(tasks_page.table.rows()) == 1
    assert window.monitoring.alerts.count() == 1
    assert window.pages[3].open_table.rows()[0].pid == 4242

    # Diálogos devolvem os valores esperados sem interação.
    assert AccountDialog(ctx, account).values()["game_ids"] == [game.id]
    assert GameDialog(ctx, game).values()["name"] == "Blox Fruits"
    assert len(GameDialog(ctx, game).values()["objectives"]) == len(game.objectives)
    assert TaskDialog(ctx, task).values()["account_id"] == account.id
    assert SessionDialog(ctx, session).values() == (None, None, "")
    assert ProgressDialog(ctx, account.id, game.id).values()["kind"] == "level"
    HistoryDialog(ctx, account)

    # Eventos de outras threads atualizam a tela atual.
    window.show_page(1)
    accounts_page.search.setText("")
    ctx.accounts.create(username="ui_user_2")
    qt_app.processEvents()
    assert len(accounts_page.table.rows()) == 2
    window.timer.stop()
    window.hide()
