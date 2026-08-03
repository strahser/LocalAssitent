"""
tests/test_agents.py — pytest-тесты для пакета agents/.

Ни один тест не обращается к сети и не импортирует selenium на верхнем
уровне: транспорт (urllib.request.urlopen) подменяется через monkeypatch,
а selenium блокируется через подмену builtins.__import__.
"""
import builtins
import json
import os
import sys
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest

from agents.base import AgentResult, BaseAgent
from agents.browser_agent import BrowserAgent
from agents.local_data_agent import LocalDataAgent
from agents.merge_agent import MergeAgent
from agents.page_parser_agent import PageParserAgent
from agents.qa_agent import QAAgent
from agents.registry import get_agent, list_agents, run_agent
from agents.web_search_agent import WebSearchAgent


# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------

class FakeResponse:
    """Фейковый ответ urllib: контекстный менеджер с .read() -> bytes."""

    def __init__(self, body: bytes):
        self._body = body

    def read(self):
        return self._body

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def patch_urlopen(monkeypatch, body: bytes):
    monkeypatch.setattr(
        urllib.request, "urlopen", lambda *a, **k: FakeResponse(body)
    )


def patch_urlopen_error(monkeypatch, exc=None):
    exc = exc or OSError("network down")

    def _boom(*a, **k):
        raise exc

    monkeypatch.setattr(urllib.request, "urlopen", _boom)


def _block_selenium_import(monkeypatch):
    """Запрещаем импорт selenium, даже если он установлен в окружении."""
    real_import = builtins.__import__

    def fake_import(name, *args, **kwargs):
        if name == "selenium" or name.startswith("selenium."):
            raise ImportError("No module named 'selenium'")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fake_import)


# ---------------------------------------------------------------------------
# Base / registry
# ---------------------------------------------------------------------------

def test_agent_result_basics():
    ok = AgentResult(True, [1, 2], "")
    assert ok
    assert ok.to_dict() == {"ok": True, "data": [1, 2], "error": ""}
    assert not AgentResult(False, None, "err")
    assert AgentResult(False, None, "err").to_dict()["ok"] is False


def test_base_agent_raises():
    with pytest.raises(NotImplementedError):
        BaseAgent().run()


def test_registry_includes_all_agents():
    names = list_agents()
    for expected in ("web_search", "page_parser", "local_data", "qa",
                     "browser", "merge", "base"):
        assert expected in names, f"missing agent: {expected}"
    assert names == sorted(names)


def test_registry_get_agent_instances():
    assert isinstance(get_agent("web_search"), WebSearchAgent)
    assert isinstance(get_agent("qa"), QAAgent)
    assert isinstance(get_agent("base"), BaseAgent)


def test_registry_unknown_agent_raises_keyerror():
    with pytest.raises(KeyError):
        get_agent("definitely_not_an_agent")


def test_run_agent_dispatches_without_network(monkeypatch, tmp_path):
    # local_data не требует сети.
    (tmp_path / "main.py").write_text("def x():\n    pass\n", encoding="utf-8")
    result = run_agent("local_data", query="def", root=str(tmp_path))
    assert isinstance(result, AgentResult)
    assert result.ok


# ---------------------------------------------------------------------------
# WebSearchAgent
# ---------------------------------------------------------------------------

DDG_HTML = b"""
<html><body>
<div class="result">
  <a class="result__a" href="//duckduckgo.com/l/?uddg=https%3A%2F%2Fexample.com">Example Title</a>
  <a class="result__snippet">Some snippet</a>
</div>
</body></html>
"""


def test_web_search_parses_results(monkeypatch):
    patch_urlopen(monkeypatch, DDG_HTML)
    result = WebSearchAgent().run(query="hello world", max_results=5)
    assert result.ok
    assert len(result.data) == 1
    first = result.data[0]
    assert first["title"] == "Example Title"
    assert first["url"] == "https://example.com"
    assert "snippet" in first


def test_web_search_offline_error(monkeypatch):
    patch_urlopen_error(monkeypatch)
    result = WebSearchAgent().run(query="hello")
    assert result.ok is False
    assert "search failed" in result.error


def test_web_search_requires_query():
    result = WebSearchAgent().run(query="")
    assert result.ok is False


# ---------------------------------------------------------------------------
# PageParserAgent
# ---------------------------------------------------------------------------

PAGE_HTML = b"""
<html><head><title>My Page</title></head>
<body>
<p>Hello world</p>
<table><tr><td>a</td><td>b</td></tr></table>
<a href="/x">link</a>
</body></html>
"""


def test_page_parser_extracts_content(monkeypatch):
    patch_urlopen(monkeypatch, PAGE_HTML)
    result = PageParserAgent().run(url="https://example.org", max_chars=5000)
    assert result.ok
    data = result.data
    assert data["title"] == "My Page"
    assert "Hello world" in data["text"]
    # tables = [ [row1, row2, ...] ] — каждая таблица это список строк.
    assert data["tables"] == [[["a", "b"]]]
    assert ["a", "b"] in data["tables"][0]
    assert any("/x" in link["url"] for link in data["links"])


def test_page_parser_offline_error(monkeypatch):
    patch_urlopen_error(monkeypatch)
    result = PageParserAgent().run(url="https://example.org")
    assert result.ok is False
    assert "fetch failed" in result.error


def test_page_parser_requires_url():
    result = PageParserAgent().run(url="")
    assert result.ok is False


# ---------------------------------------------------------------------------
# LocalDataAgent
# ---------------------------------------------------------------------------

def test_local_data_finds_keyword(tmp_path):
    (tmp_path / "main.py").write_text(
        "def alpha():\n    pass\n", encoding="utf-8"
    )
    result = LocalDataAgent().run(query="alpha", root=str(tmp_path))
    assert result.ok
    assert len(result.data) == 1
    assert result.data[0]["path"].endswith("main.py")


def test_local_data_skips_excluded_dirs(tmp_path):
    (tmp_path / "keep.py").write_text("needle_value\n", encoding="utf-8")
    excluded = tmp_path / "__pycache__"
    excluded.mkdir()
    (excluded / "skip.py").write_text("needle_value\n", encoding="utf-8")
    result = LocalDataAgent().run(query="needle_value", root=str(tmp_path))
    assert result.ok
    paths = [item["path"] for item in result.data]
    assert any("keep.py" in p for p in paths)
    assert not any("__pycache__" in p for p in paths)


def test_local_data_requires_query(tmp_path):
    result = LocalDataAgent().run(query="", root=str(tmp_path))
    assert result.ok is False


# ---------------------------------------------------------------------------
# QAAgent
# ---------------------------------------------------------------------------

def test_qa_agent_model_param():
    assert QAAgent(model="fake-model").model == "fake-model"


def test_qa_agent_success(monkeypatch):
    payload = json.dumps({"message": {"content": "hi there"}}).encode("utf-8")
    patch_urlopen(monkeypatch, payload)
    result = QAAgent(model="fake-model").run(question="hello?")
    assert result.ok
    assert result.data == "hi there"


def test_qa_agent_offline_error(monkeypatch):
    patch_urlopen_error(monkeypatch)
    result = QAAgent(model="fake-model").run(question="hello?")
    assert result.ok is False
    assert "ollama" in result.error.lower()


def test_qa_agent_requires_question():
    result = QAAgent(model="fake-model").run(question="")
    assert result.ok is False


# ---------------------------------------------------------------------------
# MergeAgent
# ---------------------------------------------------------------------------

def test_merge_agent_creates_output(tmp_path):
    (tmp_path / "a.py").write_text("x=1\n", encoding="utf-8")
    out_file = os.path.join(str(tmp_path), "out.txt")
    result = MergeAgent().run(
        root_dir=str(tmp_path),
        output_file=out_file,
        extensions=[".py"],
    )
    assert result.ok
    assert os.path.exists(out_file)


# ---------------------------------------------------------------------------
# BrowserAgent (без selenium)
# ---------------------------------------------------------------------------

def test_browser_agent_import_works_without_selenium():
    # Модуль импортируется без selenium на верхнем уровне — это уже проверка.
    import agents.browser_agent  # noqa: F401
    assert True


def test_browser_agent_returns_graceful_error_without_selenium(monkeypatch):
    _block_selenium_import(monkeypatch)
    result = BrowserAgent().run(action="open", url="https://example.com")
    assert result.ok is False
    assert "selenium" in result.error.lower()


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def test_cli_imports_and_defines_main():
    from agents.cli import build_parser, main
    assert callable(main)
    parser = build_parser()
    assert parser is not None
    # --list и --help печатают список агентов (без сети).
    assert parser.parse_args(["--list"]).list is True


def test_cli_list_prints_agents(capsys):
    from agents.cli import main
    rc = main(["--list"])
    captured = capsys.readouterr()
    assert rc == 0
    for name in ("web_search", "page_parser", "local_data", "qa",
                 "browser", "merge", "base"):
        assert f"{name}:" in captured.out


def test_cli_unknown_agent_returns_1(capsys):
    from agents.cli import main
    rc = main(["definitely_not_an_agent", "--query", "x"])
    captured = capsys.readouterr()
    assert rc == 1
    assert "ERROR" in captured.err
