"""
qa_agent.py — Q&A через локальную Ollama.

Отправляет чат-запрос на http://localhost:11434/api/chat через urllib.
Модель берётся из env OLLAMA_MODEL или по умолчанию "qwen2.5:7b",
и может быть переопределена через конструктор (model=) — это
позволяет тестам подставлять фиктивное имя модели.
Offline-safe: таймаут 15с, при ошибке -> AgentResult(ok=False, error=...).
"""
import json
import os
import urllib.request

from agents.base import AgentResult, BaseAgent

OLLAMA_URL = "http://localhost:11434/api/chat"
DEFAULT_MODEL = "qwen2.5:7b"
TIMEOUT = 15


class QAAgent(BaseAgent):
    """Задаёт вопрос локальной модели Ollama (http://localhost:11434)."""

    name = "qa"
    description = "Ask a local Ollama model (localhost:11434)"

    def __init__(self, model: str = None):
        super().__init__()
        self.model = model or os.environ.get("OLLAMA_MODEL") or DEFAULT_MODEL

    def run(self, question: str = "", context: str = "", **kwargs) -> AgentResult:
        # CLI передаёт запрос через --query -> alias для question.
        if not question:
            question = kwargs.get("query", "")
        if not question:
            return AgentResult(False, "", "question is required")

        messages = []
        if context:
            messages.append(
                {"role": "system", "content": f"Context:\n{context}"}
            )
        messages.append({"role": "user", "content": question})

        payload = json.dumps(
            {"model": self.model, "messages": messages, "stream": False}
        ).encode("utf-8")

        req = urllib.request.Request(
            OLLAMA_URL,
            data=payload,
            headers={"Content-Type": "application/json"},
        )
        try:
            with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
                body = resp.read().decode("utf-8", errors="replace")
            data = json.loads(body)
            answer = (data.get("message") or {}).get("content", "")
        except Exception as exc:
            return AgentResult(
                False,
                "",
                f"ollama request failed ({OLLAMA_URL}): {exc}",
            )
        return AgentResult(True, answer)
