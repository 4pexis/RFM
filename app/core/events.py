"""Barramento de eventos interno (publish/subscribe), seguro entre threads."""
from __future__ import annotations

import logging
import threading
from collections import defaultdict
from typing import Any, Callable

Handler = Callable[[str, Any], None]
log = logging.getLogger(__name__)

# Nomes de eventos usados pela aplicação.
ACCOUNTS_CHANGED = "accounts.changed"
GAMES_CHANGED = "games.changed"
TASKS_CHANGED = "tasks.changed"
PROGRESS_CHANGED = "progress.changed"
SESSIONS_CHANGED = "sessions.changed"
SETTINGS_CHANGED = "settings.changed"
HARDWARE_SNAPSHOT = "hardware.snapshot"
HARDWARE_ALERT = "hardware.alert"
BACKUP_DONE = "backup.done"
QUEUE_CHANGED = "queue.changed"


class EventBus:
    def __init__(self) -> None:
        self._handlers: dict[str, list[Handler]] = defaultdict(list)
        self._lock = threading.Lock()

    def subscribe(self, event: str, handler: Handler) -> None:
        """Use event="*" para receber todos os eventos."""
        with self._lock:
            self._handlers[event].append(handler)

    def unsubscribe(self, event: str, handler: Handler) -> None:
        with self._lock:
            if handler in self._handlers.get(event, []):
                self._handlers[event].remove(handler)

    def publish(self, event: str, payload: Any = None) -> None:
        with self._lock:
            handlers = list(self._handlers.get(event, ())) + list(self._handlers.get("*", ()))
        for handler in handlers:
            try:
                handler(event, payload)
            except Exception:  # um assinante com erro não derruba os demais
                log.exception("Erro em assinante do evento %s", event)
