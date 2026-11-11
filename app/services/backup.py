"""Backup e restauração do banco de dados.

SQLite: cópia consistente a quente (API de backup do SQLite).
PostgreSQL: use ``pg_dump``/``pg_restore`` no servidor (veja o README).
"""
from __future__ import annotations

import logging
import shutil
import sqlite3
from datetime import datetime
from pathlib import Path

from app.core import events as ev
from app.core.config import Settings
from app.core.events import EventBus
from app.core.security import AccessControl, Permission, ValidationError
from app.database.connection import Database

log = logging.getLogger(__name__)
_SQLITE_MAGIC = b"SQLite format 3\x00"


class BackupService:
    def __init__(self, settings: Settings, db: Database, events: EventBus, access: AccessControl) -> None:
        self.settings = settings
        self.db = db
        self.events = events
        self.access = access

    @property
    def supported(self) -> bool:
        return self.settings.sqlite_path is not None

    def _require_sqlite(self) -> Path:
        path = self.settings.sqlite_path
        if path is None:
            raise ValidationError("Backup integrado disponível apenas para SQLite. No PostgreSQL use pg_dump.")
        return path

    def list_backups(self) -> list[Path]:
        return sorted(self.settings.backup_dir.glob("rfm_*.db"), reverse=True)

    def last_backup_time(self) -> datetime | None:
        backups = self.list_backups()
        return datetime.fromtimestamp(backups[0].stat().st_mtime) if backups else None

    def create(self, label: str = "auto", keep: int | None = None) -> Path:
        source = self._require_sqlite()
        self.settings.backup_dir.mkdir(parents=True, exist_ok=True)
        target = self.settings.backup_dir / f"rfm_{datetime.now():%Y%m%d_%H%M%S}_{label}.db"
        src = sqlite3.connect(source)
        dst = sqlite3.connect(target)
        try:
            src.backup(dst)
        finally:
            dst.close()
            src.close()
        if keep:
            self.prune(keep)
        log.info("Backup criado", extra={"file": target.name})
        self.events.publish(ev.BACKUP_DONE, target)
        return target

    def prune(self, keep: int) -> int:
        """Mantém apenas os ``keep`` backups automáticos mais recentes."""
        auto = [p for p in self.list_backups() if p.stem.endswith("_auto")]
        for old in auto[max(1, keep):]:
            old.unlink(missing_ok=True)
        return max(0, len(auto) - max(1, keep))

    def restore(self, backup: Path) -> Path:
        """Substitui o banco atual pelo backup. Antes disso, salva uma cópia de
        segurança do estado atual. Retorna o caminho dessa cópia."""
        self.access.require(Permission.ADMIN)
        target = self._require_sqlite()
        backup = Path(backup)
        if not backup.is_file():
            raise ValidationError("Arquivo de backup não encontrado.")
        with open(backup, "rb") as handle:
            if handle.read(16) != _SQLITE_MAGIC:
                raise ValidationError("O arquivo selecionado não é um banco SQLite válido.")
        safety = self.create(label="antes_restauracao")
        self.db.dispose()
        for suffix in ("-wal", "-shm"):
            Path(str(target) + suffix).unlink(missing_ok=True)
        shutil.copy2(backup, target)
        self.db.reconnect()
        self.db.migrate()  # backups antigos são atualizados para o esquema atual
        log.info("Backup restaurado", extra={"file": backup.name})
        return safety
