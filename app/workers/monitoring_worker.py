"""Tarefas periódicas de monitoramento: hardware, sessões, backups e limpeza."""
from __future__ import annotations

import logging
import time
from datetime import datetime, timedelta

from app.core import events as ev
from app.core.events import EventBus
from app.managers.session_manager import SessionManager
from app.managers.settings_manager import SettingsManager
from app.services.backup import BackupService
from app.services.monitoring import HardwareMonitor
from app.services.scheduler import Scheduler
from app.workers.task_worker import PRIORITY_LOW, AdminTaskQueue

log = logging.getLogger(__name__)
METRIC_PERSIST_S = 60  # grava uma amostra por minuto no banco
ALERT_REPEAT_S = 300  # não repete o mesmo alerta antes de 5 minutos


class MonitoringWorker:
    def __init__(
        self, scheduler: Scheduler, events: EventBus, config: SettingsManager,
        monitor: HardwareMonitor, sessions: SessionManager, backups: BackupService,
        queue: AdminTaskQueue,
    ) -> None:
        self.scheduler, self.events, self.config = scheduler, events, config
        self.monitor, self.sessions, self.backups, self.queue = monitor, sessions, backups, queue
        self._last_persist = 0.0
        self._last_alert: dict[str, float] = {}

    def register(self) -> None:
        cfg = self.config.get
        self.scheduler.every("sessions", lambda: cfg("sessions.scan_interval_s"), self.scan_sessions)
        self.scheduler.every("hardware", lambda: cfg("monitor.interval_s"), self.collect_hardware, 0.5)
        self.scheduler.every("backup", 600, self.maybe_backup, first_delay=60)
        self.scheduler.every("prune", 6 * 3600, self.prune_metrics, first_delay=120)

    def scan_sessions(self) -> None:
        self.sessions.scan()

    def collect_hardware(self) -> None:
        snap = self.monitor.collect(self.sessions.last_processes, self.sessions.open_count())
        self.events.publish(ev.HARDWARE_SNAPSHOT, snap)
        now = time.monotonic()
        if now - self._last_persist >= METRIC_PERSIST_S:
            self._last_persist = now
            self.monitor.persist(snap)
        if self.config.get("monitor.alerts_enabled"):
            alerts = self.monitor.check_alerts(
                snap, self.config.get("monitor.cpu_alert"),
                self.config.get("monitor.ram_alert"), self.config.get("monitor.disk_alert"),
            )
            for alert in alerts:
                if now - self._last_alert.get(alert.resource, -ALERT_REPEAT_S) >= ALERT_REPEAT_S:
                    self._last_alert[alert.resource] = now
                    log.warning("Alerta de hardware: %s", alert.message)
                    self.events.publish(ev.HARDWARE_ALERT, alert)

    def maybe_backup(self) -> None:
        if not self.backups.supported or not self.config.get("backup.enabled"):
            return
        last = self.backups.last_backup_time()
        interval = timedelta(hours=max(1, self.config.get("backup.interval_h")))
        if last is None or datetime.now() - last >= interval:
            keep = self.config.get("backup.keep")
            self.queue.submit("Backup automático", lambda: self.backups.create("auto", keep), PRIORITY_LOW)

    def prune_metrics(self) -> None:
        days = self.config.get("monitor.metric_retention_days")
        self.queue.submit("Limpeza de métricas", lambda: self.monitor.prune(days), PRIORITY_LOW)
