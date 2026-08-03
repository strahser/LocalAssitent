"""local_data_agent.py — агент поиска данных в локальных файлах.
Вместо собственной реализации _search_files используется штатный
инструмент tools.search.grep_search. Контракт результата:
AgentResult(ok, [{"path", "line", "snippet"}], error).

Совместимость: принимает и `query` (старое имя), и `pattern` (новое).
"""
from __future__ import annotations
import re
from typing import Any, Dict, List

from agents.base import AgentResult, BaseAgent
from tools.search import grep_search

# Расширения текстовых файлов (старое поведение агента).
TEXT_EXTENSIONS = (
    ".py", ".cs", ".xaml", ".csproj", ".json", ".xml", ".md", ".txt", ".config",
)

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
        query: str = "",
        root: str = ".",
        include: str = "",
        max_results: int = 30,
        **kwargs: Any,
    ) -> AgentResult:
        needle = pattern or query
        if not needle:
            return AgentResult(ok=False, data=[], error="не задан запрос (query/pattern)")
        if not include:
            include = ",".join(TEXT_EXTENSIONS)
        try:
            raw = grep_search(
                needle, root=root, include=include, max_results=max_results
            )
        except Exception as exc:  # noqa: BLE001
            return AgentResult(
                ok=False, data=[], error=f"{type(exc).__name__}: {exc}"
            )
        return AgentResult(ok=True, data=_parse_grep_output(raw), error=None)
