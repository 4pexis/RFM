"""Módulo de acompanhamento: Grow a Garden."""
from app.game_modules.base import (  # noqa: F401
    K_ACHIEVEMENT, K_ITEM, K_LEVEL, K_OBJECTIVE, K_STAT, GameModule, Objective,
)


class GrowAGardenModule(GameModule):
    slug = "grow_a_garden"
    name = "Grow a Garden"
    experience_id = "126884695634066"
    category = "Simulador / Fazenda"
    description = "Simulador de jardim: plante, colha e venda."
    icon = "sprout"
    OBJECTIVES = (
        Objective("sheckles", "Sheckles", K_STAT),
        Objective("seeds", "Sementes raras", K_ITEM),
        Objective("pets", "Pets", K_ITEM),
        Objective("mutations", "Mutações obtidas", K_ACHIEVEMENT),
        Objective("gear", "Ferramentas", K_ITEM),
    )


MODULE = GrowAGardenModule()
