"""
registry.py — реестр локальных агентов.

Реестр автоматически обнаруживает все подклассы BaseAgent (они
регистрируются в BaseAgent._registry через __init_subclass__ при импорте
модулей пакета agents — см. agents/__init__.py).
"""
from typing import List

from agents.base import AgentResult, BaseAgent


def get_agent(name: str) -> BaseAgent:
    """Возвращает экземпляр агента по имени. KeyError, если агент неизвестен."""
    if name not in BaseAgent._registry:
        raise KeyError(f"Unknown agent: {name}")
    return BaseAgent._registry[name]()


def list_agents() -> List[str]:
    """Отсортированный список имён доступных агентов."""
    return sorted(BaseAgent._registry)


def run_agent(name: str, **kwargs) -> AgentResult:
    """Запускает агента по имени с переданными аргументами."""
    return get_agent(name).run(**kwargs)
