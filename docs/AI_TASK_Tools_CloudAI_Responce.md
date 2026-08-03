# Ответ Qwen

**Дата:** 2026-08-03T15:20:02
**Источник:** AI_TASK_Tools_CloudAI_Responce.md

---

Завершено размышление
4.1 План-кратко
инструмент
роль
аргументы
как подключён
tools/registry.py
единый реестр инструментов
register(name), get_tool(name), list_tools(), run_tool(name, *args, **kwargs)
новый файл; используется tools/cli.py, tools/__init__.py и новыми инструментами
tools/cli.py
CLI python -m tools
--list, <name>, флаги --param val / --param=val / --flag; _build_kwargs() маппит их в kwargs, позиционные — в *args
новый файл; вызывается из tools/__main__.py
tools/__main__.py
точка входа python -m tools
нет (sys.exit(main()))
новый файл
tools/edit_file.py
замена первого вхождения текста в файле
path, old_text, new_text, force=False
новый файл; @register("edit_file"), путь только через tools.safety.safe_join
tools/append_file.py
добавление текста в конец файла
path, content, create=True
новый файл; @register("append_file"), путь только через safe_join
tools/delete_file.py
удаление файла (каталоги не удаляются)
path
новый файл; @register("delete_file"), путь только через safe_join
tools/__init__.py
импорт и регистрация всех инструментов, единый __all__
старый API сохранён полностью + новые имена
ИЗМЕНЁН; «старые» инструменты регистрируются вызовами register(name)(fn), их модули не правятся
agents/local_data_agent.py
агент local_data: поиск данных в файлах проекта
pattern, root=".", include="*.py", max_results=30
ИЗМЕНЁН: внутренний _search_files заменён на tools.search.grep_search; контракт AgentResult(ok, data=[{"path","line","snippet"}], error) сохранён
tests/test_tools_registry.py
тесты реестра: get/list/run, авторегистрация, KeyError на неизвестный инструмент
pytest, tmp_path, monkeypatch корня
новый файл, 8 тестов
tests/test_tools_edit_append_delete.py
тесты edit/append/delete + безопасность (уход из корня → ValueError)
pytest, tmp_path, monkeypatch корня
новый файл, 12 тестов
tools/read_file.py, tools/write_file.py, tools/search.py, tools/list_dir.py, tools/execute.py, tools/safety.py, tools/merge_docs.py
существующая функциональность
сигнатуры не меняются
НЕ изменяются; регистрируются в tools/__init__.py
4.2 Комплект файлов
tools/registry.py
python
1
2
3
4
5
6
7
8
9
10
11
12
13
14
15
16
17
18
19
20
21
22
23
24
25
26
27
28
29
30
31
32
33
34
35
36
37
38
39
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
// END OF FILE
tools/cli.py
python
1
2
3
4
5
6
7
8
9
10
11
12
13
14
15
16
17
18
19
20
21
22
23
24
25
26
27
28
29
30
31
32
33
34
35
36
37
38
39
40
"""cli.py — командная строка пакета tools: `python -m tools ...`.
По образцу agents/cli.py: `--list` выводит список инструментов,
запуск инструмента по имени, маппинг CLI-флагов в kwargs через
_build_kwargs().
"""
from __future__ import annotations
import argparse
import sys
from typing import Any, Dict, List, Optional, Sequence
from tools.registry import get_tool, list_tools
def _coerce_value(value: str) -> Any:
    """Преобразует CLI-строку в int/bool, если это однозначно возможно."""
    if isinstance(value, str):
        stripped = value.strip()
        if stripped.lstrip("-").isdigit():
            return int(stripped)
        if stripped.lower() in ("true", "false"):
            return stripped.lower() == "true"
    return value
def _build_kwargs(extra: Sequence[str]) -> Dict[str, Any]:
    """Маппит флаги `--param value` / `--param=value` / `--flag` в kwargs.
    Позиционные аргументы собираются в список под ключом '_positional'.
    """
    kwargs: Dict[str, Any] = {}
    positional: List[str] = []
    tokens = list(extra)
    i = 0
    while i < len(tokens):
        token = tokens[i]
        if token.startswith("--"):
            key = token[2:]
            if "=" in key:
tools/main.py
python
1
2
3
4
5
6
7
8
"""__main__.py — точка входа: `python -m tools`."""
import sys
from tools.cli import main
if __name__ == "__main__":
    sys.exit(main())
// END OF FILE
tools/edit_file.py
python
1
2
3
4
5
6
7
8
9
10
11
12
13
14
15
16
17
18
19
20
21
22
23
24
25
26
27
28
29
30
31
32
33
34
35
36
37
38
39
40
41
42
43
44
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
// END OF FILE
tools/append_file.py
python
1
2
3
4
5
6
7
8
9
10
11
12
13
14
15
16
17
18
19
20
21
22
23
24
25
26
27
28
29
30
31
32
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
// END OF FILE
tools/delete_file.py
python
1
2
3
4
5
6
7
8
9
10
11
12
13
14
15
16
17
18
19
20
21
22
23
24
25
26
27
28
29
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
// END OF FILE
tools/init.py
python
1
2
3
4
5
6
7
8
9
10
11
12
13
14
15
16
17
18
19
20
21
22
23
24
25
26
27
28
29
30
31
32
33
34
35
36
37
38
39
40
41
42
43
44
45
46
47
48
49
50
51
52
"""tools — плагинная система инструментов LocalAssistant.
Импорт пакета регистрирует все инструменты (старые и новые) в реестре
tools.registry, чтобы `python -m tools --list` видел их все.
"""
from tools.registry import get_tool, list_tools, register, run_tool
from tools.read_file import read_file
from tools.write_file import write_file
from tools.search import glob_search, grep_search
from tools.list_dir import list_dir
from tools.execute import check_code_safety, execute_code
from tools.safety import is_safe_path, safe_join
from tools.merge_docs import merge_documents
# новые инструменты: регистрируются сами через @register при импорте модулей
from tools.edit_file import edit_file
from tools.append_file import append_file
from tools.delete_file import delete_file
# явная регистрация «старых» инструментов (их модули не изменяются)
register("read_file")(read_file)
register("write_file")(write_file)
register("grep_search")(grep_search)
register("glob_search")(glob_search)
register("list_dir")(list_dir)
register("execute_code")(execute_code)
register("merge_documents")(merge_documents)
__all__ = [
    # старый API — имена сохранены
    "read_file",
    "write_file",
    "grep_search",
    "glob_search",
    "list_dir",
    "check_code_safety",
    "execute_code",
    "safe_join",
    "is_safe_path",
    "merge_documents",
    # новые инструменты
    "edit_file",
    "append_file",
    "delete_file",
    # реестр
    "register",
    "get_tool",
    "list_tools",
    "run_tool",
]
// END OF FILE
agents/local_data_agent.py
python
1
2
3
4
5
6
7
8
9
10
11
12
13
14
15
16
17
18
19
20
21
22
23
24
25
26
27
28
29
30
31
32
33
34
35
36
37
38
39
40
41
42
43
44
45
46
47
48
49
50
51
52
53
54
55
56
57
58
59
60
61
62
63
64
65
66
"""local_data_agent.py — агент поиска данных в локальных файлах.
Вместо собственной реализации _search_files используется штатный
инструмент tools.search.grep_search. Контракт результата:
AgentResult(ok, [{"path", "line", "snippet"}], error).
"""
from __future__ import annotations
import re
from typing import Any, Dict, List
from agents.base import AgentResult, BaseAgent
from tools.search import grep_search
_LINE_RE = re.compile(r"^(?P<path>.+?):(?P<line>\d+):\s?(?P<snippet>.*)$")
def _parse_grep_output(raw: str) -> List[Dict[str, Any]]:
    """Разбирает текстовый вывод grep_search в список словарей.
    Распознаются строки вида `path:line: snippet`; остальные строки
    (заголовки, «ничего не найдено» и т.п.) пропускаются.
    """
    items: List[Dict[str, Any]] = []
    for line in raw.splitlines():
        line = line.rstrip()
        if not line:
            continue
        match = _LINE_RE.match(line)
        if match:
            items.append(
                {
                    "path": match.group("path"),
                    "line": int(match.group("line")),
                    "snippet": match.group("snippet"),
                }
            )
    return items
class LocalDataAgent(BaseAgent):
    """Ищет строки в файлах проекта по регулярному выражению."""
    name = "local_data"
    description = "Поиск данных в локальных файлах проекта (grep_search)."
    def run(
        self,
        pattern: str = "",
        root: str = ".",
        include: str = "*.py",
        max_results: int = 30,
        **kwargs: Any,
    ) -> AgentResult:
        if not pattern:
            return AgentResult(ok=False, data=[], error="не задан pattern")
        try:
            raw = grep_search(
                pattern, root=root, include=include, max_results=max_results
            )
        except Exception as exc:  # noqa: BLE001
            return AgentResult(
                ok=False, data=[], error=f"{type(exc).__name__}: {exc}"
            )
        return AgentResult(ok=True, data=_parse_grep_output(raw), error=None)
// END OF FILE
tests/test_tools_registry.py
python
1
2
3
4
5
6
7
8
9
10
11
12
13
14
15
16
17
18
19
20
21
22
23
24
25
26
27
28
29
30
31
32
33
34
35
36
37
38
39
40
"""Тесты реестра инструментов tools (офлайн, сеть не требуется)."""
from __future__ import annotations
import pytest
import tools  # noqa: F401 — импорт включает регистрацию всех инструментов
from tools.registry import get_tool, list_tools, register, run_tool
EXPECTED_TOOLS = (
    "append_file",
    "delete_file",
    "edit_file",
    "execute_code",
    "glob_search",
    "grep_search",
    "list_dir",
    "merge_documents",
    "read_file",
    "write_file",
)
@pytest.fixture
def sandbox(tmp_path, monkeypatch):
    """Временно объявляет корнем проекта временный каталог."""
    import tools.safety as safety
    patched = False
    for attr in list(vars(safety)):
        upper = attr.upper()
        if "ROOT" in upper or upper in ("BASE_DIR", "BASEDIR"):
            monkeypatch.setattr(safety, attr, tmp_path)
            patched = True
    if not patched:
        monkeypatch.setattr(safety, "PROJECT_ROOT", tmp_path, raising=False)
    return tmp_path
def test_list_tools_contains_all_expected():
    names = list_tools()
tests/test_tools_edit_append_delete.py
python
1
2
3
4
5
6
7
8
9
10
11
12
13
14
15
16
17
18
19
20
21
22
23
24
25
26
27
28
29
30
31
32
33
34
35
36
37
38
39
40
"""Тесты новых инструментов edit_file / append_file / delete_file (офлайн)."""
from __future__ import annotations
import pytest
import tools.safety as safety
from tools.append_file import append_file
from tools.delete_file import delete_file
from tools.edit_file import edit_file
@pytest.fixture
def sandbox(tmp_path, monkeypatch):
    """Переносит корень проекта во временный каталог."""
    patched = False
    for attr in list(vars(safety)):
        upper = attr.upper()
        if "ROOT" in upper or upper in ("BASE_DIR", "BASEDIR"):
            monkeypatch.setattr(safety, attr, tmp_path)
            patched = True
    if not patched:
        monkeypatch.setattr(safety, "PROJECT_ROOT", tmp_path, raising=False)
    return tmp_path
def test_edit_file_replaces_first_occurrence(sandbox):
    (sandbox / "a.txt").write_text("hello hello\n", encoding="utf-8")
    result = edit_file("a.txt", "hello", "bye")
    assert result.startswith("OK")
    assert (sandbox / "a.txt").read_text(encoding="utf-8") == "bye hello\n"
def test_edit_file_creates_with_force(sandbox):
    result = edit_file("new.txt", "", "content\n", force=True)
    assert result.startswith("OK")
    assert (sandbox / "new.txt").read_text(encoding="utf-8") == "content\n"
def test_edit_file_missing_file_without_force(sandbox):
    result = edit_file("nope.txt", "a", "b")
4.3 Контракт полноты
SUMMARY
total_files: 10
tools/registry.py: 38 строк | END OK
tools/cli.py: 102 строки | END OK
tools/main.py: 7 строк | END OK
tools/edit_file.py: 43 строки | END OK
tools/append_file.py: 31 строка | END OK
tools/delete_file.py: 28 строк | END OK
tools/init.py: 51 строка | END OK
agents/local_data_agent.py: 65 строк | END OK
tests/test_tools_registry.py: 84 строки | END OK
tests/test_tools_edit_append_delete.py: 101 строка | END OK
tools/read_file.py: не изменялся
tools/write_file.py: не изменялся
tools/search.py: не изменялся
tools/list_dir.py: не изменялся
tools/execute.py: не изменялся
tools/safety.py: не изменялся
tools/merge_docs.py: не изменялся
agents/base.py: не изменялся
agents/registry.py: не изменялся
agents/cli.py: не изменялся
agents/main.py: не изменялся
agents/init.py: не изменялся
