# ТЗ для облачного ИИ: унификация пакета `tools/` в плагинную систему (LocalAssitent)

> Формат: по шаблону cloud-ai-bridge/docs/task-template.md.
> Отвечай СТРОГО по секции «4. Формат ответа» с контрактом полноты.

---

## 1. Контекст

- **Проект:** `e:\ПлагиныРевит\LocalAssitent` — локальный ассистент на Python 3.10+ (pip, pytest).
- **Ветка / коммит:** `v1`, рабочие изменения не закоммичены (tree чист, кроме этого ТЗ).
- **Задача — одна:** унифицировать модули `tools/` по образцу уже унифицированного пакета `agents/`.
- **Сборка/тесты:** `python -m pytest tests -q` → сейчас 90 passed (эталон базы; сеть не требуется).
- **Кодировка:** все исходники UTF-8 (без BOM). Имена публичных функций НЕ переименовывать.

### Уже есть рабочий образец: пакет `agents/` (плагинная система)

- `agents/base.py` — `BaseAgent` + `AgentResult`; авторегистрация подклассов через `__init_subclass__` по атрибуту `name` в `BaseAgent._registry`.
- `agents/registry.py` — `get_agent(name)`, `list_agents()`, `run_agent(name, **kwargs)`.
- `agents/cli.py` — argparse: `python -m agents --list` и `python -m agents <name> --param val`; `_build_kwargs()` маппит CLI-флаги в kwargs.
- `agents/__main__.py` — точка входа `python -m agents`.
- `agents/__init__.py` — импортирует все агенты, чтобы они зарегистрировались.

**Цель:** сделать с `tools/` то же самое — единый реестр, единый CLI `python -m tools`, новые инструменты редактирования файлов, и связать агента `local_data` с `grep_search`.

## 2. Цель (одна задача)

Превратить набор разрозненных модулей `tools/` в единую плагинную систему по образцу `agents/`:
реестр + автозапуск через `python -m tools`, добавить безопасные инструменты
`edit_file` / `append_file` / `delete_file` (через `tools.safety.safe_join`), связать
`agents/local_data_agent.py` с `tools.search.grep_search`, сохранить все существующие
публичные API и контракт `AgentResult`, добавить offline-тесты. В конце — **все тесты
остаются зелёными (90+), `python -m tools --list` и `python -m agents --list` работают.**

---

## 3. Входные данные — инвентарь (НЕ полный код)

### 3.1 Существующие модули `tools/` (смотри их в проекте)

| Путь | Строк | Экспортируемые функции |
|------|------:|------------------------|
| tools/__init__.py | 11 | read_file, grep_search, glob_search, list_dir, execute_code, write_file, merge_documents |
| tools/read_file.py | 37 | `read_file(path, offset=0, limit=2000) -> str` |
| tools/write_file.py | 28 | `write_file(path, content, force=False) -> str` |
| tools/search.py | 60 | `grep_search(pattern, root=".", include="*.py", max_results=30) -> str`, `glob_search(pattern, root=".") -> str` |
| tools/list_dir.py | 36 | `list_dir(path=".", max_depth=2, show_hidden=False) -> str` |
| tools/execute.py | 69 | `check_code_safety(code) -> str`, `execute_code(code, timeout=30) -> str` |
| tools/safety.py | 39 | `safe_join(relative_path) -> str` (бросает ValueError), `is_safe_path(path) -> bool` |
| tools/merge_docs.py | 256 | `merge_documents(...)`, `collect_files(...)` и др. |

### 3.2 Пакет `agents/` — эталон для подражания (смотри в проекте)

| Файл | Строк | Роль-образец |
|------|------:|--------------|
| agents/base.py | 53 | класс `BaseAgent` + авторегистрация |
| agents/registry.py | 27 | реестр `get_/list/run_` |
| agents/cli.py | 139 | argparse CLI + `_build_kwargs` |
| agents/__main__.py | 7 | `sys.exit(main())` |
| agents/__init__.py | 33 | импорт всех модулей для регистрации |

### 3.3 Целевые НОВЫЕ файлы (создать)

| Файл | Что внутри |
|------|-----------|
| tools/registry.py | реестр инструментов по образцу agents/registry.py |
| tools/cli.py | argparse CLI `python -m tools ...` по образцу agents/cli.py |
| tools/__main__.py | точка входа `python -m tools` |
| tools/edit_file.py | редактирование файла безопасным путём (см. ниже контракт) |
| tools/append_file.py | добавление текста в конец файла |
| tools/delete_file.py | удаление файла |

### 3.4 Файлы-потребители (ИЗМЕНИТЬ)

| Файл | Что меняется |
|------|--------------|
| tools/__init__.py | добавить реестр + новые инструменты в `__all__`, сохранить старые имена |
| agents/local_data_agent.py | заменить внутренний `_search_files` на вызов `tools.search.grep_search` (сохранить контракт: `AgentResult(ok, [{"path","line","snippet"}], error)`) |

### 3.5 Тесты (добавить)

| Файл | Что проверить |
|------|--------------|
| tests/test_tools_registry.py | registry: get/list/run, авторегистрация, неизвестный инструмент -> KeyError |
| tests/test_tools_edit_append_delete.py | edit/append/delete через tmp_path, безопасность (попытка уйти из корня -> ValueError) |

---

## 4. Формат ответа (СТРОГО)

Только секции ниже, без лишнего текста:

### 4.1 План-кратко
Таблица: «инструмент | роль | аргументы | как подключён».
- (без "…" и пропусков — если файл не меняется, так и напиши в SUMMARY)

### 4.2 Комплект файлов (для КАЖДОГО изменяемого/нового файла)

```
### tools/registry.py
```python
<ПОЛНЫЙ содержимое файла>
```

### tools/cli.py
```python
<ПОЛНОЕ содержимое>
```
… и так для каждого файла из п.3.3 + 3.4 + 3.5. Полный файл, не дифф, если
файл небольшой (<150 строк). Если файл большой (>150) — дай полный код блоками
с маркером `// END OF FILE` в конце каждого файла.
```

- Каждый файл в ответе **заканчивается строкой `// END OF FILE`**.
- Кодировка исходников — UTF-8. Средник файлов давать в формате `tools/...` и `tests/...`.

### 4.3 Контракт полноты (в самом конце ответа)

```markdown
### SUMMARY
total_files: N
tools/registry.py: <число> строк | END OK
tools/cli.py: <число> строк | END OK
tools/__main__.py: <число> строк | END OK
tools/edit_file.py: <число> строк | END OK
tools/append_file.py: <число> строк | END OK
tools/delete_file.py: <число> строк | END OK
tools/__init__.py: <число> строк | END OK
agents/local_data_agent.py: <число> строк | END OK
tests/test_tools_registry.py: <число> строк | END OK
tests/test_tools_edit_append_delete.py: <число> строк | END OK
```
**Правило:** файл без маркера `END OK` не принимается.

---

## 5. Ограничения (что НЕ делать)

- ❌ НЕ переименовывать публичные API существующих модулей (`merge_documents`, `grep_search`, `safe_join` и т.д.).
- ❌ НЕ ломать импорты существующего кода (`from tools.search import grep_search` и т.д.).
- ❌ НЕ добавлять сетевых/тяжёлых зависимостей в `tools/` — всё должно импортироваться офлайн (как в `agents/`).
- ❌ НЕ удалять ни один существующий файл `tools/`; править только те, что указаны.
- ❌ НЕ использовать `cd`/абсолютные пути вне `PROJECT_ROOT` — только через `safe_join`.
- ✅ ВАЖНО: `tools/cli.py` должен уметь `python -m tools --list` и запуск инструмента по имени (аргументы маппятся через функцию по образцу `_build_kwargs`).
- ✅ Русские докстринги/комментарии допустимы, идентификаторы — английские.

---

## 6. Эталон формата (образец успешного ответа)

```
### tools/registry.py
```python
"""registry.py — реестр инструментов."""
from __future__ import annotations
from typing import Callable, Dict, List

_TOOLS: Dict[str, Callable] = {}

def register(name: str) -> Callable:
    """Декоратор: регистрирует инструмент в реестре."""

    def decorator(fn: Callable) -> Callable:
        _TOOLS[name] = fn
        return fn
    return decorator

def get_tool(name: str) -> Callable:
    if name not in _TOOLS:
        raise KeyError(f"Unknown tool: {name}")
    return _TOOLS[name]

def list_tools() -> List[str]:
    return sorted(_TOOLS)

// END OF FILE
```
```

...и так для каждого файла (секции `### tools/cli.py`, `### tools/__main__.py`, и т.д.)

---

## Чек-лист после реализации локально (делает ассистент, не ты)
1. `python -m pytest tests/ -q` → 90+ passed (новые тесты обязательны).
2. `python -m tools --list` и `python -m agents --list` выводят список.
3. `python -m tools read_file tools/safety.py` работает.
4. Сборка/импорт пакета `tools` без сети не падает.