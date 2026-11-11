"""Configurações ajustáveis em tempo de execução (tabela system_settings)."""
from __future__ import annotations

import threading
from typing import Any

from sqlalchemy import select

from app.core import events as ev
from app.core.security import (
    Permission, Role, ValidationError, hash_pin, protect, unprotect, verify_pin,
)
from app.database.models import SystemSetting

from .base import BaseManager

DEFAULTS: dict[str, Any] = {
    "monitor.interval_s": 3,
    "monitor.alerts_enabled": True,
    "monitor.cpu_alert": 90,
    "monitor.ram_alert": 90,
    "monitor.disk_alert": 90,
    "monitor.metric_retention_days": 14,
    "sessions.scan_interval_s": 5,
    "sessions.process_names": "RobloxPlayerBeta.exe",
    "sessions.idle_cpu_percent": 0.5,
    "sessions.idle_minutes": 10,
    "backup.enabled": True,
    "backup.interval_h": 24,
    "backup.keep": 10,
    "security.role": Role.ADMIN,
    "security.pin_hash": "",
    "ui.refresh_s": 5,
}
SECRET_KEYS = {"security.pin_hash"}


def _coerce(default: Any, raw: str) -> Any:
    if isinstance(default, bool):
        return raw.lower() in ("1", "true", "yes")
    if isinstance(default, int):
        return int(float(raw))
    if isinstance(default, float):
        return float(raw)
    return raw


class SettingsManager(BaseManager):
    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._cache: dict[str, Any] = {}
        self._lock = threading.Lock()
        self.reload()

    def reload(self) -> None:
        with self.db.session() as s:
            rows = {row.key: row for row in s.scalars(select(SystemSetting)).all()}
        cache = dict(DEFAULTS)
        for key, row in rows.items():
            if key in DEFAULTS:
                try:
                    raw = unprotect(row.value) if row.is_secret else row.value
                    cache[key] = _coerce(DEFAULTS[key], raw)
                except (ValueError, OSError):
                    self.log.warning("Configuração inválida ignorada: %s", key)
        with self._lock:
            self._cache = cache
        self.access.role = cache["security.role"]

    def get(self, key: str) -> Any:
        with self._lock:
            return self._cache[key]

    def all(self) -> dict[str, Any]:
        with self._lock:
            return dict(self._cache)

    def set_many(self, values: dict[str, Any], *, _internal: bool = False) -> None:
        if not _internal:
            self.access.require(Permission.ADMIN)
        with self.db.session() as s:
            for key, value in values.items():
                if key not in DEFAULTS:
                    raise ValidationError(f"Configuração desconhecida: {key}")
                value = _coerce(DEFAULTS[key], str(value))
                if isinstance(value, (int, float)) and not isinstance(value, bool) and value < 0:
                    raise ValidationError(f"O valor de {key} não pode ser negativo.")
                secret = key in SECRET_KEYS
                raw = protect(str(value)) if secret else str(value)
                row = s.get(SystemSetting, key)
                if row is None:
                    s.add(SystemSetting(key=key, value=raw, is_secret=secret))
                else:
                    row.value, row.is_secret = raw, secret
                self._audit(s, "settings.update", "setting", None, key if secret else f"{key}={value}")
        self.reload()
        self.events.publish(ev.SETTINGS_CHANGED)

    # ------------------------------------------------------------- perfil e PIN

    @property
    def has_pin(self) -> bool:
        return bool(self.get("security.pin_hash"))

    def set_pin(self, pin: str) -> None:
        self.access.require(Permission.ADMIN)
        if pin and len(pin) < 4:
            raise ValidationError("O PIN deve ter pelo menos 4 caracteres.")
        self.set_many({"security.pin_hash": hash_pin(pin) if pin else ""})

    def change_role(self, role: str, pin: str = "") -> None:
        """Trocar de perfil exige o PIN de administrador quando ele estiver definido
        e o perfil atual não for administrador."""
        if role not in Role.LABELS:
            raise ValidationError("Perfil inválido.")
        if self.access.role != Role.ADMIN and self.has_pin:
            if not verify_pin(pin, self.get("security.pin_hash")):
                raise ValidationError("PIN incorreto.")
        self.set_many({"security.role": role}, _internal=True)
