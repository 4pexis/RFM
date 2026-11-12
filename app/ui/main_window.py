"""Janela principal: menu lateral + telas."""
from __future__ import annotations

from PySide6.QtCore import QObject, QSize, Qt, QTimer, Signal
from PySide6.QtGui import QCloseEvent, QIcon, QPixmap
from PySide6.QtWidgets import (
    QButtonGroup, QHBoxLayout, QLabel, QMainWindow, QPushButton, QStackedWidget, QSystemTrayIcon,
    QVBoxLayout, QWidget,
)

from app.core import events as ev
from app.core.bootstrap import AppContext
from app.core.config import APP_NAME, APP_SHORT, APP_VERSION, resource_root
from app.core.security import Role
from app.ui import theme
from app.ui.accounts.page import AccountsPage
from app.ui.dashboard.page import DashboardPage
from app.ui.games.page import GamesPage
from app.ui.icons import nav_icon
from app.ui.monitoring.page import MonitoringPage
from app.ui.progress.page import ProgressPage
from app.ui.reports.page import ReportsPage
from app.ui.sessions.page import SessionsPage
from app.ui.settings.page import SettingsPage
from app.ui.tasks.page import TasksPage
from app.ui.widgets import Page, label

NAVIGATION: list[tuple[str, str, type[Page]]] = [
    ("view-dashboard-outline", "Dashboard", DashboardPage),
    ("account-multiple-outline", "Contas", AccountsPage),
    ("gamepad-variant-outline", "Jogos", GamesPage),
    ("monitor", "Sessões", SessionsPage),
    ("clipboard-check-outline", "Tarefas", TasksPage),
    ("trending-up", "Progresso", ProgressPage),
    ("file-chart-outline", "Relatórios", ReportsPage),
    ("pulse", "Monitoramento", MonitoringPage),
    ("cog-outline", "Configurações", SettingsPage),
]


class EventBridge(QObject):
    """Leva eventos publicados em threads de serviço para a thread da interface."""

    received = Signal(str, object)

    def __init__(self, ctx: AppContext) -> None:
        super().__init__()
        ctx.events.subscribe("*", lambda event, payload: self.received.emit(event, payload))


def app_icon() -> QIcon:
    return QIcon(str(resource_root() / "assets" / "icon.ico"))


class MainWindow(QMainWindow):
    def __init__(self, ctx: AppContext) -> None:
        super().__init__()
        self.ctx = ctx
        self.setWindowTitle(APP_NAME)
        self.setWindowIcon(app_icon())
        self.resize(1440, 880)
        self.setMinimumSize(1100, 680)

        sidebar = QWidget()
        sidebar.setObjectName("sidebar")
        sidebar.setFixedWidth(220)
        side = QVBoxLayout(sidebar)
        side.setContentsMargins(14, 18, 14, 14)
        side.setSpacing(4)
        logo = QLabel()
        pixmap = QPixmap(str(resource_root() / "assets" / "logo.png"))
        if not pixmap.isNull():
            ratio = self.devicePixelRatioF()
            pixmap = pixmap.scaled(int(120 * ratio), int(120 * ratio), Qt.AspectRatioMode.KeepAspectRatio,
                                   Qt.TransformationMode.SmoothTransformation)
            pixmap.setDevicePixelRatio(ratio)
            logo.setPixmap(pixmap)
        else:
            logo.setText(APP_SHORT)
            logo.setObjectName("brand")
        logo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        side.addWidget(logo)
        name = label(APP_NAME, "brandSub")
        name.setAlignment(Qt.AlignmentFlag.AlignCenter)
        side.addWidget(name)
        side.addSpacing(16)

        self.stack = QStackedWidget()
        self.pages: list[Page] = []
        self.nav = QButtonGroup(self)
        for index, (icon, title, page_class) in enumerate(NAVIGATION):
            btn = QPushButton(f"  {title}")
            btn.setIcon(nav_icon(icon))
            btn.setIconSize(QSize(20, 20))
            btn.setObjectName("nav")
            btn.setCheckable(True)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            self.nav.addButton(btn, index)
            side.addWidget(btn)
            page = page_class(ctx)
            self.pages.append(page)
            self.stack.addWidget(page)
        self.monitoring = next(p for p in self.pages if isinstance(p, MonitoringPage))
        side.addStretch(1)
        self.role_label = label("", "muted")
        self.queue_label = label("", "muted")
        side.addWidget(self.queue_label)
        side.addWidget(self.role_label)
        side.addWidget(label(f"v{APP_VERSION}", "muted"))

        central = QWidget()
        layout = QHBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(sidebar)
        layout.addWidget(self.stack, 1)
        self.setCentralWidget(central)
        self.statusBar().showMessage("Pronto")
        # Ícone na bandeja: usado para as notificações de sessão do Windows.
        self.tray = QSystemTrayIcon(app_icon(), self)
        self.tray.setToolTip(APP_NAME)
        if QSystemTrayIcon.isSystemTrayAvailable():
            self.tray.show()

        self.nav.idClicked.connect(self.show_page)
        self.bridge = EventBridge(ctx)
        self.bridge.received.connect(self._on_event)
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._tick)
        self._apply_settings()
        self.timer.start()
        self.nav.button(0).setChecked(True)
        self.show_page(0)

    def show_page(self, index: int) -> None:
        self.stack.setCurrentIndex(index)
        self.pages[index].refresh()

    def _apply_settings(self) -> None:
        self.timer.setInterval(int(self.ctx.config.get("ui.refresh_s")) * 1000)
        role = self.ctx.access.role
        self.role_label.setText(f"Perfil: {Role.LABELS[role]}")
        self.role_label.setStyleSheet(f"color: {theme.MUTED if role == Role.ADMIN else theme.YELLOW};")

    def _tick(self) -> None:
        page = self.stack.currentWidget()
        if isinstance(page, Page) and page.auto_refresh and not self.isMinimized():
            page.refresh()

    def _on_event(self, event: str, payload: object) -> None:
        if event == ev.HARDWARE_SNAPSHOT:
            self.monitoring.on_snapshot(payload)
            return
        if event == ev.SESSION_ALERT:
            self.statusBar().showMessage(str(payload), 30_000)
            if self.tray.isVisible():
                self.tray.showMessage(APP_NAME, str(payload), QSystemTrayIcon.MessageIcon.Warning, 10_000)
            return
        if event == ev.HARDWARE_ALERT:
            self.monitoring.on_alert(payload)
            self.statusBar().showMessage(f"Alerta: {payload.message}", 15_000)
            return
        if event == ev.QUEUE_CHANGED:
            running = payload["running"]
            self.queue_label.setText(f"Executando: {running[0]}…" if running else "")
            return
        if event == ev.BACKUP_DONE:
            self.statusBar().showMessage(f"Backup criado: {payload.name}", 10_000)
        if event == ev.SETTINGS_CHANGED:
            self._apply_settings()
        page = self.stack.currentWidget()
        if isinstance(page, Page) and event in page.events:
            page.refresh()

    def closeEvent(self, event: QCloseEvent) -> None:
        self.timer.stop()
        self.tray.hide()
        self.ctx.shutdown()
        event.accept()
