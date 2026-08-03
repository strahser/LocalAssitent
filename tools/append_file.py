"""append_file.py — безопасное добавление текста в конец файла.
Путь разрешается только через tools.safety.safe_join: попытка выйти
за пределы корня проекта бросает ValueError.
"""
from __future__ import annotations
import os
from tools.registry import register
from tools.safety import safe_join
@register("append_file")
def append_file(path: str, content: str, create: bool = True) -> str:
    """Дописывает `content` в конец файла.
    create=True: при отсутствии файл создаётся (вместе с каталогами);
    create=False: при отсутствии файла возвращается ошибка без создания.
    """
    abs_path = safe_join(path)
    if not os.path.isfile(abs_path) and not create:
        return f"Ошибка: файл не найден: {path}"
    parent = os.path.dirname(abs_path)
    if parent:
        os.makedirs(parent, exist_ok=True)
    with open(abs_path, "a", encoding="utf-8") as fh:
        fh.write(content)
    return f"OK: файл дополнен {path}"
