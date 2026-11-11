"""Módulo de acompanhamento: Murder Mystery 2."""
from app.game_modules.base import (  # noqa: F401
    K_ACHIEVEMENT, K_ITEM, K_LEVEL, K_OBJECTIVE, K_STAT, GameModule, Objective,
)


class MurderMysteryModule(GameModule):
    slug = "murder_mystery"
    name = "Murder Mystery 2"
    experience_id = "142823291"
    category = "Mistério"
    description = "Jogo de dedução: inocentes, xerife e assassino."
    icon = "knife"
    OBJECTIVES = (
        Objective("level", "Nível", K_LEVEL, max_value=100),
        Objective("coins", "Moedas", K_STAT),
        Objective("godlys", "Itens Godly", K_ITEM),
        Objective("wins", "Vitórias", K_STAT),
        Objective("prestige", "Prestígio", K_STAT),
    )


MODULE = MurderMysteryModule()
