from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.bootstrap import AppContext, bootstrap  # noqa: E402
from app.core.config import Settings  # noqa: E402
from app.services.monitoring import ProcessInfo  # noqa: E402


class FakeProvider:
    """Substitui o psutil: os testes controlam quais 'processos' existem."""

    def __init__(self) -> None:
        self.processes: list[ProcessInfo] = []

    def list(self, names: set[str]) -> list[ProcessInfo]:
        wanted = {n.lower() for n in names}
        return [p for p in self.processes if p.name.lower() in wanted]


@pytest.fixture
def provider() -> FakeProvider:
    return FakeProvider()


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    return Settings(
        env="test", data_dir=tmp_path,
        database_url=f"sqlite:///{(tmp_path / 'rfm.db').as_posix()}", log_level="WARNING",
    )


@pytest.fixture
def ctx(settings: Settings, provider: FakeProvider) -> AppContext:
    context = bootstrap(settings, migrate=False, provider=provider, configure_logging=False)
    yield context
    context.shutdown()
