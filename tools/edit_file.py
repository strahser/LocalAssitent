"""edit_file.py — безопасное редактирование файла (поиск с заменой).
Путь разрешается только через tools.safety.safe_join: попытка выйти
за пределы корня проекта бросает ValueError.
"""
from __future__ import annotations
import os
from tools.registry import register
from tools.safety import safe_join
@register("edit_file")
def edit_file(path: str, old_text: str, new_text: str, force: bool = False) -> str:
    """Заменяет первое вхождение `old_text` в файле на `new_text`.
    Если файла нет: force=False — ошибка, force=True — файл создаётся.
    Если `old_text` — пустая строка, `new_text` дописывается в конец.
    """
    abs_path = safe_join(path)
    if not os.path.isfile(abs_path):
        if not force:
            return f"Ошибка: файл не найден: {path}"
        content = ""
    else:
        with open(abs_path, "r", encoding="utf-8") as fh:
            content = fh.read()
    if old_text:
        if old_text not in content:
            return f"Ошибка: искомый текст не найден в {path}"
        content = content.replace(old_text, new_text, 1)
    else:
        content += new_text
    parent = os.path.dirname(abs_path)
    if parent:
        os.makedirs(parent, exist_ok=True)
    with open(abs_path, "w", encoding="utf-8") as fh:
        fh.write(content)
    return f"OK: файл изменён {path}"
