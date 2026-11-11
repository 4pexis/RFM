"""Módulo de acompanhamento: Shindo Life."""
from app.game_modules.base import (  # noqa: F401
    K_ACHIEVEMENT, K_ITEM, K_LEVEL, K_OBJECTIVE, K_STAT, GameModule, Objective,
)


class ShindoLifeModule(GameModule):
    slug = "shindo_life"
    name = "Shindo Life"
    experience_id = "4616652839"
    category = "RPG / Anime"
    description = "RPG ninja com bloodlines e modos."
    icon = "ninja"
    OBJECTIVES = (
        Objective("level", "Nível", K_LEVEL, max_value=1000),
        Objective("rank", "Rank / prestígio", K_STAT),
        Objective("ryo", "Ryo", K_STAT),
        Objective("bloodlines", "Bloodlines", K_ITEM),
        Objective("spins", "Spins", K_STAT),
        Objective("modes", "Modos desbloqueados", K_ACHIEVEMENT),
    )


MODULE = ShindoLifeModule()
