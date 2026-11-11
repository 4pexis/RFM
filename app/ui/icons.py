"""Ícones vetoriais (Material Design Icons, via qtawesome)."""
from __future__ import annotations

import qtawesome as qta
from PySide6.QtGui import QIcon

from . import theme

DEFAULT_GAME_ICON = "gamepad-variant"

# Opções oferecidas no cadastro de jogos: (nome do ícone, rótulo).
GAME_ICONS: list[tuple[str, str]] = [
    ("gamepad-variant", "Controle"), ("sword", "Espada"), ("sword-cross", "Espadas cruzadas"),
    ("shield-sword", "Escudo"), ("crown", "Coroa"), ("fruit-cherries", "Fruta"), ("fish", "Peixe"),
    ("hook", "Anzol"), ("bee", "Abelha"), ("paw", "Pata"), ("dog", "Cachorro"), ("knife", "Faca"),
    ("ninja", "Ninja"), ("dice-5", "Dado"), ("sprout", "Broto"), ("star", "Estrela"),
    ("trophy", "Troféu"), ("diamond-stone", "Diamante"), ("pickaxe", "Picareta"), ("car", "Carro"),
    ("castle", "Castelo"), ("rocket-launch", "Foguete"), ("ghost", "Fantasma"), ("soccer", "Futebol"),
    ("puzzle", "Quebra-cabeça"), ("skull", "Caveira"), ("target", "Alvo"),
]
_GAME_ICON_NAMES = {name for name, _ in GAME_ICONS}


def icon(name: str, color: str = theme.TEXT, **options) -> QIcon:
    return qta.icon(f"mdi6.{name}", color=color, color_disabled=theme.MUTED, **options)


def nav_icon(name: str) -> QIcon:
    """Ícone do menu lateral: apagado quando inativo, branco quando selecionado."""
    return qta.icon(f"mdi6.{name}", color=theme.MUTED, color_active=theme.TEXT,
                    color_on="white", color_on_active="white")


def is_game_icon(name: str) -> bool:
    return name in _GAME_ICON_NAMES


def game_icon(name: str, color: str = theme.ACCENT) -> QIcon:
    """Ícone do jogo; valores desconhecidos (ex.: emojis de versões antigas) usam o padrão."""
    return icon(name if is_game_icon(name) else DEFAULT_GAME_ICON, color)
