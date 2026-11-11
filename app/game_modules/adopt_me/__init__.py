"""Módulo de acompanhamento: Adopt Me!."""
from app.game_modules.base import (  # noqa: F401
    K_ACHIEVEMENT, K_ITEM, K_LEVEL, K_OBJECTIVE, K_STAT, GameModule, Objective,
)


class AdoptMeModule(GameModule):
    slug = "adopt_me"
    name = "Adopt Me!"
    experience_id = "920587237"
    category = "Roleplay / Pets"
    description = "Adoção, criação e troca de pets."
    icon = "dog"
    OBJECTIVES = (
        Objective("bucks", "Bucks", K_STAT),
        Objective("pets", "Pets importantes", K_ITEM),
        Objective("neons", "Pets neon / mega", K_ITEM),
        Objective("age_tasks", "Tarefas de crescimento", K_OBJECTIVE),
        Objective("login_streak", "Sequência de login", K_STAT),
    )


MODULE = AdoptMeModule()
