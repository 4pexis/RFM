"""Módulo de acompanhamento: Pet Simulator 99."""
from app.game_modules.base import (  # noqa: F401
    K_ACHIEVEMENT, K_ITEM, K_LEVEL, K_OBJECTIVE, K_STAT, GameModule, Objective,
)


class PetSimulatorModule(GameModule):
    slug = "pet_simulator"
    name = "Pet Simulator 99"
    experience_id = "8737899170"
    category = "Simulador"
    description = "Simulador de coleta e evolução de pets."
    icon = "paw"
    OBJECTIVES = (
        Objective("zone", "Zona alcançada", K_STAT),
        Objective("rebirths", "Rebirths", K_STAT),
        Objective("diamonds", "Diamantes", K_STAT),
        Objective("huges", "Pets Huge", K_ITEM),
        Objective("rank", "Rank", K_LEVEL),
        Objective("masteries", "Maestrias", K_ACHIEVEMENT),
    )


MODULE = PetSimulatorModule()
