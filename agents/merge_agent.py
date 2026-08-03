"""
merge_agent.py — агент-обёртка над tools/merge_docs.merge_documents.

Собирает файлы проекта в один TXT для передачи внешнему ИИ.
tools.merge_docs импортируется лениво (внутри run).
"""
import os
from typing import List, Optional

from agents.base import AgentResult, BaseAgent

DEFAULT_MERGE_EXTENSIONS = [".cs", ".py", ".json", ".md"]


class MergeAgent(BaseAgent):
    """Сведение файлов проекта в один контекстный TXT."""

    name = "merge"
    description = "Merge project files into one context TXT (tools.merge_docs)"

    def run(
        self,
        root_dir: str = ".",
        output_file: str = "merged_context.txt",
        extensions: Optional[List[str]] = None,
        **kwargs,
    ) -> AgentResult:
        # CLI передаёт корень через --root -> alias для root_dir.
        root_dir = kwargs.get("root", root_dir)
        if extensions is None:
            extensions = DEFAULT_MERGE_EXTENSIONS

        if not os.path.isdir(root_dir):
            return AgentResult(False, None, f"not a directory: {root_dir}")

        try:
            from tools.merge_docs import merge_documents
            result = merge_documents(
                root_dir=root_dir,
                output_file=output_file,
                extensions=extensions,
            )
            return AgentResult(True, result)
        except Exception as exc:
            return AgentResult(False, None, f"merge failed: {exc}")
