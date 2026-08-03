"""
base.py — базовые классы плагинной системы локальных агентов.

Содержит контракт: AgentResult (результат работы агента) и BaseAgent
(абстрактный интерфейс). Реестр (registry.py) автоматически находит
все подклассы BaseAgent, импортированные в пакете agents:
BaseAgent.__init_subclass__ регистрирует каждый подкласс по атрибуту name.
"""
from typing import Any, Dict


class AgentResult:
    """Результат работы агента: ok/data/error."""

    def __init__(self, ok: bool, data: Any, error: str = ""):
        self.ok = ok
        self.data = data
        self.error = error

    def __bool__(self) -> bool:
        return self.ok

    def to_dict(self) -> Dict[str, Any]:
        return {"ok": self.ok, "data": self.data, "error": self.error}

    def __repr__(self) -> str:
        return f"AgentResult(ok={self.ok}, error={self.error!r})"


class BaseAgent:
    """Абстрактный базовый агент. Подклассы переопределяют name/description/run.

    Каждый подкласс автоматически попадает в _registry по атрибуту name,
    поэтому registry.py не нужно знать о конкретных агентах заранее.
    """

    name = "base"
    description = "Base agent"
    _registry: Dict[str, type] = {}

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        BaseAgent._registry[cls.name] = cls

    def run(self, **kwargs) -> AgentResult:
        raise NotImplementedError(
            f"Agent '{self.name}' does not implement run(**kwargs)"
        )


# Сам базовый агент тоже регистрируем (name = "base"), чтобы list_agents()
# показывал его как доступного.
BaseAgent._registry[BaseAgent.name] = BaseAgent
