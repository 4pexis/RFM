"""Agendador simples de tarefas periódicas em uma thread de serviço."""
from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass
from typing import Callable

log = logging.getLogger(__name__)


@dataclass
class Job:
    name: str
    func: Callable[[], None]
    interval: Callable[[], float]  # lido a cada ciclo: mudanças de configuração valem na hora
    next_run: float


class Scheduler:
    def __init__(self) -> None:
        self._jobs: list[Job] = []
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._lock = threading.Lock()

    def every(self, name: str, interval: float | Callable[[], float], func: Callable[[], None],
              first_delay: float = 0.0) -> None:
        getter = interval if callable(interval) else (lambda value=float(interval): value)
        with self._lock:
            self._jobs.append(Job(name, func, getter, time.monotonic() + first_delay))

    def start(self) -> None:
        if self._thread is None or not self._thread.is_alive():
            self._stop.clear()
            self._thread = threading.Thread(target=self._run, name="rfm-scheduler", daemon=True)
            self._thread.start()

    def stop(self, timeout: float = 5.0) -> None:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout)
            self._thread = None

    def run_pending(self) -> None:
        now = time.monotonic()
        with self._lock:
            due = [job for job in self._jobs if job.next_run <= now]
        for job in due:
            try:
                job.func()
            except Exception:
                log.exception("Falha na tarefa agendada %s", job.name)
            job.next_run = time.monotonic() + max(0.5, float(job.interval()))

    def _run(self) -> None:
        while not self._stop.wait(0.25):
            self.run_pending()
