"""PLUGIN MANAGER: descobre e carrega os módulos em ``app/game_modules``."""
from __future__ import annotations

import importlib
import logging
import pkgutil

import app.game_modules as game_modules_pkg
from app.game_modules.base import GameModule, GenericGameModule

log = logging.getLogger(__name__)


class PluginManager:
    def __init__(self) -> None:
        self.modules: dict[str, GameModule] = {}
        self.load_errors: dict[str, str] = {}
        self._generic = GenericGameModule()

    def discover(self) -> dict[str, GameModule]:
        """Importa cada subpacote; um módulo com defeito não impede os demais."""
        self.modules.clear()
        self.load_errors.clear()
        for info in pkgutil.iter_modules(game_modules_pkg.__path__):
            if not info.ispkg:
                continue
            try:
                package = importlib.import_module(f"{game_modules_pkg.__name__}.{info.name}")
                module = getattr(package, "MODULE", None)
                if not isinstance(module, GameModule) or not module.slug:
                    raise TypeError("o pacote não define MODULE (instância de GameModule com slug)")
                self.modules[module.slug] = module
            except Exception as exc:
                self.load_errors[info.name] = str(exc)
                log.exception("Falha ao carregar o módulo de jogo %s", info.name)
        log.info("Módulos de jogo carregados", extra={"count": len(self.modules)})
        return self.modules

    def get(self, slug: str) -> GameModule:
        """Módulo do jogo ou o genérico, para jogos cadastrados manualmente."""
        return self.modules.get(slug, self._generic)

    def has(self, slug: str) -> bool:
        return slug in self.modules
