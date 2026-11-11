"""CORE: monta e interliga todos os serviços da aplicação."""
from __future__ import annotations

import logging
from dataclasses import dataclass

from app.core.config import APP_NAME, APP_VERSION, Settings, load_settings
from app.core.events import EventBus
from app.core.logger import setup_logging
from app.core.security import AccessControl
from app.database.connection import Database
from app.managers.account_manager import AccountManager
from app.managers.game_manager import GameManager
from app.managers.plugin_manager import PluginManager
from app.managers.progress_manager import ProgressManager
from app.managers.report_manager import ReportManager
from app.managers.session_manager import SessionManager
from app.managers.settings_manager import SettingsManager
from app.managers.task_manager import TaskManager
from app.services.backup import BackupService
from app.services.monitoring import HardwareMonitor, ProcessProvider, PsutilProcessProvider
from app.services.scheduler import Scheduler
from app.workers.monitoring_worker import MonitoringWorker
from app.workers.task_worker import AdminTaskQueue

log = logging.getLogger(__name__)


@dataclass
class AppContext:
    settings: Settings
    db: Database
    events: EventBus
    access: AccessControl
    config: SettingsManager
    plugins: PluginManager
    accounts: AccountManager
    games: GameManager
    tasks: TaskManager
    progress: ProgressManager
    sessions: SessionManager
    reports: ReportManager
    monitor: HardwareMonitor
    backups: BackupService
    scheduler: Scheduler
    queue: AdminTaskQueue
    worker: MonitoringWorker

    def start_workers(self) -> None:
        self.queue.start()
        self.worker.register()
        self.scheduler.start()

    def shutdown(self) -> None:
        self.scheduler.stop()
        self.queue.stop()
        self.db.dispose()
        log.info("Aplicação encerrada")


def bootstrap(
    settings: Settings | None = None, *, migrate: bool = True,
    provider: ProcessProvider | None = None, configure_logging: bool = True,
) -> AppContext:
    settings = settings or load_settings()
    settings.ensure_dirs()
    if configure_logging:
        setup_logging(settings.log_dir, settings.log_level)
    log.info("Iniciando %s %s", APP_NAME, APP_VERSION, extra={"env": settings.env})

    db = Database(settings.database_url)
    if migrate:
        db.migrate()
    else:
        db.create_all()

    events = EventBus()
    access = AccessControl()
    common = (db, events, access)

    config = SettingsManager(*common)
    plugins = PluginManager()
    plugins.discover()
    games = GameManager(*common, plugins=plugins)
    games.sync_modules()

    sessions = SessionManager(*common, config=config, provider=provider or PsutilProcessProvider())
    monitor = HardwareMonitor(db, settings.data_dir)
    backups = BackupService(settings, db, events, access)
    scheduler = Scheduler()
    queue = AdminTaskQueue(events)
    worker = MonitoringWorker(scheduler, events, config, monitor, sessions, backups, queue)

    return AppContext(
        settings=settings, db=db, events=events, access=access, config=config, plugins=plugins,
        accounts=AccountManager(*common), games=games, tasks=TaskManager(*common, games=games),
        progress=ProgressManager(*common, games=games), sessions=sessions,
        reports=ReportManager(*common), monitor=monitor, backups=backups,
        scheduler=scheduler, queue=queue, worker=worker,
    )
