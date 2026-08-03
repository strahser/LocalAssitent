"""registry.py — реестр инструментов LocalAssistant.
По образцу agents/registry.py: единый реестр `_TOOLS`, функции
get/list/run. Регистрация — декоратором @register(name) либо явным
вызовом register(name)(fn) в tools/__init__.py.
"""
from __future__ import annotations
from typing import Any, Callable, Dict, List
_TOOLS: Dict[str, Callable] = {}
def register(name: str) -> Callable:
    """Декоратор: регистрирует инструмент в реестре."""
    def decorator(fn: Callable) -> Callable:
        _TOOLS[name] = fn
        return fn
    return decorator
def get_tool(name: str) -> Callable:
    """Вернуть инструмент по имени; бросает KeyError, если его нет."""
    if name not in _TOOLS:
        raise KeyError(f"Unknown tool: {name}")
    return _TOOLS[name]
def list_tools() -> List[str]:
    """Отсортированный список имён всех зарегистрированных инструментов."""
    return sorted(_TOOLS)
def run_tool(name: str, *args: Any, **kwargs: Any) -> Any:
    """Найти инструмент по имени и вызвать его с заданными аргументами."""
    return get_tool(name)(*args, **kwargs)
