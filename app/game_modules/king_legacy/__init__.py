"""Módulo de acompanhamento: King Legacy."""
from app.game_modules.base import (  # noqa: F401
    K_ACHIEVEMENT, K_ITEM, K_LEVEL, K_OBJECTIVE, K_STAT, GameModule, Objective,
)


class KingLegacyModule(GameModule):
    slug = "king_legacy"
    name = "King Legacy"
    experience_id = "4520749081"
    category = "RPG / Anime"
    description = "RPG de piratas com frutas, espadas e mares."
    icon = "crown"
    OBJECTIVES = (
        Objective("level", "Nível", K_LEVEL),
        Objective("sea", "Mar atual", K_STAT, max_value=3),
        Objective("beli", "Beli", K_STAT),
        Objective("gems", "Gemas", K_STAT),
        Objective("fruit", "Fruta equipada", K_ITEM),
        Objective("sword", "Espada principal", K_ITEM),
        Objective("bosses", "Chefes derrotados", K_ACHIEVEMENT),
    )


MODULE = KingLegacyModule()
