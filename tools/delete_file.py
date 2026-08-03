"""delete_file.py — безопасное удаление файла.
Путь разрешается только через tools.safety.safe_join: попытка выйти
за пределы корня проекта бросает ValueError.
"""
from __future__ import annotations
import os
from tools.registry import register
from tools.safety import safe_join
@register("delete_file")
def delete_file(path: str) -> str:
    """Удаляет файл. Каталог не удаляется.
    Если файла нет, возвращает сообщение об ошибке без исключения.
    """
    abs_path = safe_join(path)
    if os.path.isdir(abs_path):
        return f"Ошибка: {path} — каталог, удаление запрещено"
    if not os.path.isfile(abs_path):
        return f"Ошибка: файл не найден: {path}"
    os.remove(abs_path)
    return f"OK: файл удалён {path}"
