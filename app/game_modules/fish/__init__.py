"""Módulo de acompanhamento: Fisch."""
from app.game_modules.base import (  # noqa: F401
    K_ACHIEVEMENT, K_ITEM, K_LEVEL, K_OBJECTIVE, K_STAT, GameModule, Objective,
)


class FischModule(GameModule):
    slug = "fish"
    name = "Fisch"
    experience_id = "16732694052"
    category = "Simulador / Pesca"
    description = "Simulador de pesca com varas, ilhas e bestiário."
    icon = "fish"
    OBJECTIVES = (
        Objective("level", "Nível", K_LEVEL),
        Objective("coins", "Moedas (C$)", K_STAT),
        Objective("rod", "Vara equipada", K_ITEM),
        Objective("bestiary", "Bestiário (%)", K_STAT, max_value=100),
        Objective("rare_fish", "Peixes raros", K_ACHIEVEMENT),
        Objective("islands", "Ilhas desbloqueadas", K_OBJECTIVE),
    )


MODULE = FischModule()
