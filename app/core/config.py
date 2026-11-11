"""Configuração por ambiente (.env / variáveis de ambiente)."""
from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

APP_NAME = "Roblox Farm Manager"
APP_SHORT = "RFM"
APP_VERSION = "0.1.0"


def project_root() -> Path:
    """Pasta do projeto (ou do executável, quando empacotado)."""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parents[2]


def resource_root() -> Path:
    """Pasta dos recursos embutidos (migrações, assets)."""
    if getattr(sys, "frozen", False):
        return Path(getattr(sys, "_MEIPASS", project_root()))
    return project_root()


@dataclass(frozen=True)
class Settings:
    env: str
    data_dir: Path
    database_url: str
    log_level: str

    @property
    def is_sqlite(self) -> bool:
        return self.database_url.startswith("sqlite")

    @property
    def sqlite_path(self) -> Path | None:
        if not self.is_sqlite or ":memory:" in self.database_url:
            return None
        return Path(self.database_url.split("///", 1)[1])

    @property
    def backup_dir(self) -> Path:
        return self.data_dir / "backups"

    @property
    def log_dir(self) -> Path:
        return self.data_dir / "logs"

    def ensure_dirs(self) -> None:
        for path in (self.data_dir, self.backup_dir, self.log_dir):
            path.mkdir(parents=True, exist_ok=True)


def load_settings() -> Settings:
    load_dotenv(project_root() / ".env")
    env = os.getenv("RFM_ENV", "development")
    default_dir = (
        Path(os.getenv("LOCALAPPDATA", str(Path.home()))) / APP_SHORT
        if getattr(sys, "frozen", False)
        else project_root() / "data"
    )
    data_dir = Path(os.getenv("RFM_DATA_DIR") or default_dir).resolve()
    database_url = os.getenv("RFM_DATABASE_URL") or f"sqlite:///{(data_dir / 'rfm.db').as_posix()}"
    return Settings(
        env=env,
        data_dir=data_dir,
        database_url=database_url,
        log_level=os.getenv("RFM_LOG_LEVEL", "INFO").upper(),
    )
