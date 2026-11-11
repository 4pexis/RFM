"""Módulo de acompanhamento: Bee Swarm Simulator."""
from app.game_modules.base import (  # noqa: F401
    K_ACHIEVEMENT, K_ITEM, K_LEVEL, K_OBJECTIVE, K_STAT, GameModule, Objective,
)


class BeeSwarmModule(GameModule):
    slug = "bee_swarm"
    name = "Bee Swarm Simulator"
    experience_id = "1537690962"
    category = "Simulador"
    description = "Simulador de colmeia: abelhas, mel e missões."
    icon = "bee"
    OBJECTIVES = (
        Objective("bees", "Quantidade de abelhas", K_STAT, max_value=50),
        Objective("hive_level", "Nível médio da colmeia", K_LEVEL, max_value=25),
        Objective("honey", "Mel", K_STAT),
        Objective("tickets", "Tickets", K_STAT),
        Objective("quests", "Missões concluídas", K_ACHIEVEMENT),
        Objective("gear", "Equipamentos", K_ITEM),
        Objective("gifted", "Abelhas gifted", K_STAT),
    )


MODULE = BeeSwarmModule()
