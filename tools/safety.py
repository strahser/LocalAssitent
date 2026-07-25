"""
Модуль безопасности для проверки путей файлов.
Предотвращает доступ за пределы корня проекта.
"""
import os

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def safe_join(relative_path: str) -> str:
    """
    Безопасно соединяет относительный путь с корнем проекта.
    Проверяет, что результат не выходит за пределы PROJECT_ROOT.
    
    Args:
        relative_path: Относительный путь к файлу
        
    Returns:
        Абсолютный путь к файлу
        
    Raises:
        ValueError: Если путь выходит за пределы корня проекта
    """
    abs_path = os.path.abspath(os.path.join(PROJECT_ROOT, relative_path))
    if not abs_path.startswith(PROJECT_ROOT):
        raise ValueError(f"Попытка доступа за пределы проекта: {relative_path}")
    return abs_path


def is_safe_path(path: str) -> bool:
    """
    Проверяет, безопасен ли путь (не выходит за пределы проекта).
    
    Args:
        path: Путь для проверки
        
    Returns:
        True если путь безопасен, False если нет
    """
    try:
        safe_join(path)
        return True
    except ValueError:
        return False
