"""Módulo de acompanhamento: Anime Adventures."""
from app.game_modules.base import (  # noqa: F401
    K_ACHIEVEMENT, K_ITEM, K_LEVEL, K_OBJECTIVE, K_STAT, GameModule, Objective,
)


class AnimeAdventuresModule(GameModule):
    slug = "anime_adventures"
    name = "Anime Adventures"
    experience_id = "8304191830"
    category = "Tower Defense"
    description = "Tower defense com unidades de anime."
    icon = "sword-cross"
    OBJECTIVES = (
        Objective("level", "Nível", K_LEVEL),
        Objective("gems", "Gemas", K_STAT),
        Objective("units", "Unidades míticas/secretas", K_ITEM),
        Objective("story", "Modo história (mundo)", K_OBJECTIVE),
        Objective("infinite", "Recorde no modo infinito", K_STAT),
        Objective("raids", "Raids concluídas", K_ACHIEVEMENT),
    )


MODULE = AnimeAdventuresModule()
