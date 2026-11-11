"""MONITORING: leitura de CPU, memória, disco e processos acompanhados.

Usa somente as APIs públicas do sistema operacional (psutil): lista processos
pelo nome e lê seus contadores de uso. Nada é lido ou escrito dentro deles.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Protocol, Sequence

import psutil
from sqlalchemy import delete, select

from app.database.connection import Database
from app.database.models import HardwareMetric, utcnow

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class ProcessInfo:
    pid: int
    name: str
    create_time: float
    cpu_percent: float  # % do total da máquina
    memory_mb: float


class ProcessProvider(Protocol):
    def list(self, names: set[str]) -> list[ProcessInfo]: ...


class PsutilProcessProvider:
    def __init__(self) -> None:
        self._cache: dict[tuple[int, float], psutil.Process] = {}
        self._cpus = psutil.cpu_count() or 1

    def list(self, names: set[str]) -> list[ProcessInfo]:
        wanted = {n.lower() for n in names}
        found: list[ProcessInfo] = []
        seen: set[tuple[int, float]] = set()
        for proc in psutil.process_iter(["pid", "name", "create_time"]):
            try:
                name = proc.info["name"] or ""
                if name.lower() not in wanted:
                    continue
                key = (proc.info["pid"], proc.info["create_time"])
                # O mesmo objeto precisa ser reutilizado para o cálculo de CPU entre leituras.
                tracked = self._cache.setdefault(key, proc)
                found.append(ProcessInfo(
                    pid=key[0], name=name, create_time=key[1],
                    cpu_percent=round(tracked.cpu_percent(None) / self._cpus, 2),
                    memory_mb=round(tracked.memory_info().rss / 1_048_576, 1),
                ))
                seen.add(key)
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
        for key in set(self._cache) - seen:
            del self._cache[key]
        return found


@dataclass(frozen=True)
class HardwareSnapshot:
    timestamp: datetime
    cpu_percent: float
    memory_percent: float
    memory_used_gb: float
    memory_total_gb: float
    disk_percent: float
    disk_free_gb: float
    disk_total_gb: float
    processes: Sequence[ProcessInfo] = field(default_factory=tuple)
    session_count: int = 0


@dataclass(frozen=True)
class Alert:
    resource: str  # cpu | ram | disk
    value: float
    threshold: float

    @property
    def message(self) -> str:
        label = {"cpu": "CPU", "ram": "Memória RAM", "disk": "Disco"}[self.resource]
        return f"{label} em {self.value:.0f}% (limite: {self.threshold:.0f}%)"


class HardwareMonitor:
    def __init__(self, db: Database, disk_path: Path) -> None:
        self.db = db
        self.disk_root = disk_path.anchor or str(disk_path)
        psutil.cpu_percent(None)  # primeira leitura apenas inicializa o contador

    def collect(self, processes: Sequence[ProcessInfo] = (), session_count: int = 0) -> HardwareSnapshot:
        memory = psutil.virtual_memory()
        disk = psutil.disk_usage(self.disk_root)
        gb = 1024 ** 3
        return HardwareSnapshot(
            timestamp=utcnow(),
            cpu_percent=psutil.cpu_percent(None),
            memory_percent=memory.percent,
            memory_used_gb=round(memory.used / gb, 1),
            memory_total_gb=round(memory.total / gb, 1),
            disk_percent=disk.percent,
            disk_free_gb=round(disk.free / gb, 1),
            disk_total_gb=round(disk.total / gb, 1),
            processes=tuple(processes),
            session_count=session_count,
        )

    @staticmethod
    def check_alerts(snap: HardwareSnapshot, cpu: float, ram: float, disk: float) -> list[Alert]:
        checks = (("cpu", snap.cpu_percent, cpu), ("ram", snap.memory_percent, ram),
                  ("disk", snap.disk_percent, disk))
        return [Alert(name, value, limit) for name, value, limit in checks if limit > 0 and value >= limit]

    def persist(self, snap: HardwareSnapshot) -> None:
        with self.db.session() as s:
            s.add(HardwareMetric(
                timestamp=snap.timestamp, cpu_percent=snap.cpu_percent,
                memory_percent=snap.memory_percent, disk_percent=snap.disk_percent,
                disk_free_gb=snap.disk_free_gb, tracked_processes=len(snap.processes),
                session_count=snap.session_count,
            ))

    def history(self, hours: int = 24) -> Sequence[HardwareMetric]:
        since = utcnow() - timedelta(hours=hours)
        with self.db.session() as s:
            return s.scalars(
                select(HardwareMetric).where(HardwareMetric.timestamp >= since)
                .order_by(HardwareMetric.timestamp)
            ).all()

    def prune(self, retention_days: int) -> int:
        limit = utcnow() - timedelta(days=max(1, retention_days))
        with self.db.session() as s:
            return s.execute(delete(HardwareMetric).where(HardwareMetric.timestamp < limit)).rowcount or 0
