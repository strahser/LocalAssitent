"""
local_data_agent.py — поиск по локальным файлам проекта.

Обходит директорию (os.walk), пропуская служебные каталоги,
и ищет в текстовых файлах строки, содержащие ключевое слово.
Возвращает список {"path", "line", "snippet"}.
"""
import os
from typing import List

from agents.base import AgentResult, BaseAgent

EXCLUDE_DIRS = {
    "__pycache__", ".git", ".venv", "venv", "node_modules",
    "build", "dist", ".opencode", ".idea",
}
TEXT_EXTENSIONS = {
    ".py", ".cs", ".xaml", ".csproj", ".json", ".xml", ".md", ".txt", ".config",
}


def _search_files(root: str, query: str, max_results: int) -> List[dict]:
    root = os.path.abspath(root)
    results = []
    query_lower = query.lower()
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in EXCLUDE_DIRS]
        for fn in filenames:
            if not fn.lower().endswith(tuple(TEXT_EXTENSIONS)):
                continue
            fp = os.path.join(dirpath, fn)
            try:
                with open(fp, "r", encoding="utf-8", errors="replace") as f:
                    for i, line in enumerate(f, start=1):
                        if query_lower in line.lower():
                            results.append(
                                {
                                    "path": fp,
                                    "line": i,
                                    "snippet": line.strip()[:200],
                                }
                            )
                            if len(results) >= max_results:
                                return results
            except OSError:
                continue
    return results


class LocalDataAgent(BaseAgent):
    """Поиск ключевого слова в локальных текстовых файлах."""

    name = "local_data"
    description = "Search local project files for a keyword"

    def run(self, query: str, root: str = ".", max_results: int = 10) -> AgentResult:
        if not query:
            return AgentResult(False, [], "query is required")
        if not os.path.isdir(root):
            return AgentResult(False, [], f"not a directory: {root}")
        try:
            results = _search_files(root, query, max_results)
        except Exception as exc:
            return AgentResult(False, [], f"search failed: {exc}")
        return AgentResult(True, results)
