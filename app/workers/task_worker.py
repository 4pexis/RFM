"""Fila de tarefas administrativas com prioridade e controle de concorrência.

Executa em segundo plano operações do próprio RFM (backup, importação de CSV,
exportações, limpeza de métricas) sem travar a interface.
"""
from __future__ import annotations

import itertools
import logging
import queue
import threading
from concurrent.futures import Future
from dataclasses import dataclass, field
from typing import Any, Callable

from app.core import events as ev
from app.core.events import EventBus

log = logging.getLogger(__name__)

PRIORITY_HIGH, PRIORITY_NORMAL, PRIORITY_LOW = 0, 5, 9
_STOP_PRIORITY = 1_000_000


@dataclass(order=True)
class _Item:
    priority: int
    order: int
    name: str = field(compare=False)
    func: Callable[[], Any] | None = field(compare=False)
    future: Future = field(compare=False)


class AdminTaskQueue:
    def __init__(self, events: EventBus, max_workers: int = 2) -> None:
        self.events = events
        self._queue: queue.PriorityQueue[_Item] = queue.PriorityQueue()
        self._counter = itertools.count()
        self._running: set[str] = set()
        self._lock = threading.Lock()
        self._threads = [
            threading.Thread(target=self._work, name=f"rfm-admin-{i}", daemon=True)
            for i in range(max(1, max_workers))
        ]
        self._started = False

    def start(self) -> None:
        if not self._started:
            self._started = True
            for thread in self._threads:
                thread.start()

    def submit(self, name: str, func: Callable[[], Any], priority: int = PRIORITY_NORMAL) -> Future:
        """Menor número = maior prioridade; empates seguem a ordem de chegada."""
        future: Future = Future()
        self._queue.put(_Item(priority, next(self._counter), name, func, future))
        self.events.publish(ev.QUEUE_CHANGED, self.status())
        return future

    def status(self) -> dict[str, Any]:
        with self._lock:
            return {"waiting": self._queue.qsize(), "running": sorted(self._running)}

    def stop(self) -> None:
        if self._started:
            for _ in self._threads:  # sentinela: executada depois de tudo que já está na fila
                self._queue.put(_Item(_STOP_PRIORITY, next(self._counter), "", None, Future()))
            self._started = False

    def _work(self) -> None:
        while True:
            item = self._queue.get()
            if item.func is None:
                return
            if not item.future.set_running_or_notify_cancel():
                continue
            with self._lock:
                self._running.add(item.name)
            self.events.publish(ev.QUEUE_CHANGED, self.status())
            try:
                item.future.set_result(item.func())
            except Exception as exc:
                log.exception("Falha na tarefa administrativa %s", item.name)
                item.future.set_exception(exc)
            finally:
                with self._lock:
                    self._running.discard(item.name)
                self.events.publish(ev.QUEUE_CHANGED, self.status())
