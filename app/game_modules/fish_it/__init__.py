"""Módulo de acompanhamento: Fish It."""
from app.game_modules.base import (  # noqa: F401
    K_ACHIEVEMENT, K_ITEM, K_LEVEL, K_OBJECTIVE, K_STAT, GameModule, Objective,
)


class FishItModule(GameModule):
    slug = "fish_it"
    name = "Fish It"
    experience_id = "121864768012064"
    category = "Simulador / Pesca"
    description = "Simulador de pesca com varas e ilhas."
    icon = "hook"
    OBJECTIVES = (
        Objective("level", "Nível", K_LEVEL),
        Objective("coins", "Moedas", K_STAT),
        Objective("rod", "Vara equipada", K_ITEM),
        Objective("rare_fish", "Peixes raros", K_ACHIEVEMENT),
        Objective("islands", "Ilhas desbloqueadas", K_OBJECTIVE),
    )


MODULE = FishItModule()
