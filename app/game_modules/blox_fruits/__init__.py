"""Módulo de acompanhamento: Blox Fruits."""
from app.game_modules.base import (  # noqa: F401
    K_ACHIEVEMENT, K_ITEM, K_LEVEL, K_OBJECTIVE, K_STAT, GameModule, Objective,
)


class BloxFruitsModule(GameModule):
    slug = "blox_fruits"
    name = "Blox Fruits"
    experience_id = "2753915549"
    category = "RPG / Anime"
    description = "RPG de mundo aberto inspirado em One Piece."
    icon = "fruit-cherries"
    OBJECTIVES = (
        Objective("level", "Nível", K_LEVEL, max_value=2800),
        Objective("sea", "Mar atual (1-3)", K_STAT, max_value=3),
        Objective("beli", "Beli", K_STAT),
        Objective("fragments", "Fragmentos", K_STAT),
        Objective("fruit", "Fruta equipada", K_ITEM),
        Objective("fruit_mastery", "Maestria da fruta", K_STAT, max_value=600),
        Objective("sword_mastery", "Maestria da espada", K_STAT, max_value=600),
        Objective("race", "Raça / despertar", K_OBJECTIVE),
        Objective("bounty", "Recompensa / Honra", K_STAT),
        Objective("raids", "Raids concluídas", K_ACHIEVEMENT),
    )


MODULE = BloxFruitsModule()
