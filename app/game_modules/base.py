"""Interface comum dos módulos de jogo.

Cada jogo vive em uma pasta própria dentro de ``app/game_modules`` e expõe uma
variável ``MODULE`` com uma instância de :class:`GameModule`. Para adicionar um
jogo basta criar a pasta — o núcleo não precisa ser alterado.

Os módulos são apenas de ACOMPANHAMENTO: descrevem objetivos, validam e resumem
os registros feitos no RFM. Eles não interagem com o cliente Roblox, não leem
memória, não injetam código e não automatizam jogabilidade.
"""
from __future__ import annotations

import logging
from dataclasses import asdict, dataclass
from typing import Any, Iterable

from app.core.security import ValidationError

K_LEVEL, K_ACHIEVEMENT, K_ITEM, K_OBJECTIVE, K_STAT = "level", "achievement", "item", "objective", "stat"


@dataclass(frozen=True)
class Objective:
    key: str
    name: str
    kind: str = K_OBJECTIVE
    description: str = ""
    max_value: float | None = None  # limite para valores numéricos (ex.: nível máximo)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class GameInfo:
    slug: str
    name: str
    experience_id: str
    category: str
    description: str
    icon: str
    version: str


class GameModule:
    slug: str = ""
    name: str = ""
    experience_id: str = ""  # Place ID público da experiência
    category: str = ""
    description: str = ""
    icon: str = "gamepad-variant"  # nome em app/ui/icons.py
    version: str = "1.0"
    OBJECTIVES: tuple[Objective, ...] = ()
    TASK_TYPES: tuple[str, ...] = ("Geral", "Progressão", "Coleta", "Evento", "Verificação")

    def __init__(self) -> None:
        self.log = logging.getLogger(f"rfm.game.{self.slug}")
        self.errors: list[str] = []

    # 1. Identificar o jogo
    def identify(self) -> GameInfo:
        return GameInfo(self.slug, self.name, self.experience_id, self.category,
                        self.description, self.icon, self.version)

    # 2. Listar objetivos
    def objectives(self) -> list[Objective]:
        return list(self.OBJECTIVES)

    def objective(self, key_or_name: str) -> Objective | None:
        for obj in self.OBJECTIVES:
            if key_or_name in (obj.key, obj.name):
                return obj
        return None

    # 3. Consultar dados disponíveis por integrações autorizadas
    def fetch_available_data(self, username: str, roblox_user_id: int | None) -> dict[str, Any]:
        """Ponto de extensão para APIs oficiais/autorizadas. Por padrão não há
        integração: os dados são registrados manualmente no RFM."""
        return {}

    # 4. Registrar progresso (validação antes de gravar)
    def validate_progress(self, name: str, value: str, numeric_value: float | None) -> None:
        obj = self.objective(name)
        if obj is None:
            return
        if obj.kind in (K_LEVEL, K_STAT) and numeric_value is None:
            raise ValidationError(f"“{obj.name}” exige um valor numérico.")
        if numeric_value is not None:
            if numeric_value < 0:
                raise ValidationError(f"“{obj.name}” não pode ser negativo.")
            if obj.max_value is not None and numeric_value > obj.max_value:
                raise ValidationError(f"“{obj.name}” não pode passar de {obj.max_value:g}.")

    # 5. Validar tarefas
    def validate_task(self, task_type: str, description: str) -> None:
        if not description.strip():
            raise ValidationError("Descreva a tarefa.")

    def task_types(self) -> list[str]:
        return list(self.TASK_TYPES)

    # 6. Gerar estatísticas
    def statistics(self, records: Iterable[Any]) -> dict[str, Any]:
        """Resumo dos registros de progresso (objetos com kind/name/numeric_value/account_id)."""
        records = list(records)
        best: dict[str, float] = {}
        for rec in records:
            if rec.numeric_value is not None:
                best[rec.name] = max(best.get(rec.name, 0.0), rec.numeric_value)
        return {
            "registros": len(records),
            "contas": len({rec.account_id for rec in records}),
            "maiores_valores": best,
        }

    # 7. Registrar erros
    def report_error(self, error: Exception | str) -> None:
        message = str(error)
        self.errors.append(message)
        del self.errors[:-50]
        self.log.error("Erro no módulo %s: %s", self.slug, message)


class GenericGameModule(GameModule):
    """Módulo usado por jogos cadastrados manualmente (sem pasta própria)."""

    slug = "generic"
    name = "Genérico"
    OBJECTIVES = (
        Objective("level", "Nível", K_LEVEL),
        Objective("items", "Itens importantes", K_ITEM),
        Objective("achievements", "Conquistas", K_ACHIEVEMENT),
    )
