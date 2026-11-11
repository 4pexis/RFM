"""Módulo de acompanhamento: Sol's RNG."""
from app.game_modules.base import (  # noqa: F401
    K_ACHIEVEMENT, K_ITEM, K_LEVEL, K_OBJECTIVE, K_STAT, GameModule, Objective,
)


class SolsRngModule(GameModule):
    slug = "sols_rng"
    name = "Sol's RNG"
    experience_id = "15532962292"
    category = "RNG"
    description = "Jogo de sorte: role auras cada vez mais raras."
    icon = "dice-5"
    OBJECTIVES = (
        Objective("rolls", "Rolls totais", K_STAT),
        Objective("best_aura", "Melhor aura", K_ITEM),
        Objective("rarest", "Raridade da melhor aura (1 em N)", K_STAT),
        Objective("luck", "Sorte base", K_STAT),
        Objective("gear", "Luvas / equipamentos", K_ITEM),
        Objective("achievements", "Conquistas", K_ACHIEVEMENT),
    )


MODULE = SolsRngModule()
