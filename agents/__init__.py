"""
agents — пакет локальных агентов (поиск, парсинг, локальные данные, Q&A, браузер, merge).

Импорт пакета регистрирует все подклассы BaseAgent в реестре,
поэтому registry.list_agents() сразу видит всех агентов.

Опциональные зависимости (selenium, Ollama) НЕ импортируются на уровне
модулей: browser_agent импортирует selenium лениво, qa_agent ходит в
Ollama по HTTP через stdlib, поэтому пакет безопасно импортировать
без сети и без selenium.
"""
from agents.base import AgentResult, BaseAgent
from agents.web_search_agent import WebSearchAgent
from agents.page_parser_agent import PageParserAgent
from agents.local_data_agent import LocalDataAgent
from agents.qa_agent import QAAgent
from agents.browser_agent import BrowserAgent
from agents.merge_agent import MergeAgent
from agents.registry import get_agent, list_agents, run_agent

__all__ = [
    "AgentResult",
    "BaseAgent",
    "WebSearchAgent",
    "PageParserAgent",
    "LocalDataAgent",
    "QAAgent",
    "BrowserAgent",
    "MergeAgent",
    "get_agent",
    "list_agents",
    "run_agent",
]
