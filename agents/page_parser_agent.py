"""
page_parser_agent.py — агент парсинга веб-страницы.

Скачивает страницу через urllib и извлекает: заголовок, текстовые
абзацы, ссылки и таблицы. Только стандартная библиотека.
Offline-safe: сетевая ошибка -> AgentResult(ok=False, error=...).
"""
import urllib.request
from html.parser import HTMLParser

from agents.base import AgentResult, BaseAgent


class _PageParser(HTMLParser):
    """Извлекает title, абзацы, ссылки и таблицы из HTML."""

    def __init__(self):
        super().__init__()
        self.title = ""
        self.paragraphs = []
        self.links = []
        self.tables = []

        self._in_title = False
        self._buf = []
        self._in_paragraph = False
        self._in_link = False
        self._link_href = ""
        self._in_table = False
        self._in_row = False
        self._in_cell = False
        self._current_row = []
        self._current_cell = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "title":
            self._in_title = True
            self._buf = []
        elif tag == "p":
            self._in_paragraph = True
            self._buf = []
        elif tag == "a" and "href" in attrs:
            self._in_link = True
            self._link_href = attrs["href"]
            self._buf = []
        elif tag == "table":
            self._in_table = True
            self.tables.append([])
        elif self._in_table and tag in ("tr",):
            self._in_row = True
            self._current_row = []
        elif self._in_table and tag in ("td", "th"):
            self._in_cell = True
            self._current_cell = []

    def handle_endtag(self, tag):
        if tag == "title" and self._in_title:
            self.title = " ".join("".join(self._buf).split())
            self._in_title = False
        elif tag == "p" and self._in_paragraph:
            text = " ".join("".join(self._buf).split())
            if text:
                self.paragraphs.append(text)
            self._in_paragraph = False
        elif tag == "a" and self._in_link:
            text = " ".join("".join(self._buf).split())
            if text and self._link_href:
                self.links.append({"text": text, "url": self._link_href})
            self._in_link = False
            self._link_href = ""
        elif tag == "td" or tag == "th":
            if self._in_cell and self._in_table:
                self._current_row.append(" ".join("".join(self._current_cell).split()))
                self._in_cell = False
                self._current_cell = []
        elif tag == "tr":
            if self._in_row and self._in_table and self.tables:
                self.tables[-1].append(list(self._current_row))
                self._current_row = []
                self._in_row = False
        elif tag == "table":
            self._in_table = False

    def handle_data(self, data):
        if self._in_title or self._in_paragraph or self._in_link:
            self._buf.append(data)
        if self._in_cell:
            self._current_cell.append(data)


def _fetch_page(url: str):
    req = urllib.request.Request(
        url,
        headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"},
    )
    with urllib.request.urlopen(req, timeout=15) as resp:
        html = resp.read().decode("utf-8", errors="replace")

    parser = _PageParser()
    parser.feed(html)
    parser.close()
    return {
        "title": parser.title,
        "text": parser.paragraphs,
        "links": parser.links,
        "tables": parser.tables,
    }


class PageParserAgent(BaseAgent):
    """Скачивает страницу и извлекает title/text/links/tables."""

    name = "page_parser"
    description = "Fetch a URL and extract title, text, links, tables"

    def run(self, url: str, max_chars: int = 5000) -> AgentResult:
        if not url:
            return AgentResult(False, {}, "url is required")
        try:
            data = _fetch_page(url)
        except Exception as exc:
            return AgentResult(False, {}, f"fetch failed: {exc}")

        # Обрезаем текст по max_chars, чтобы не возвращать гигантские данные.
        total = sum(len(p) for p in data["text"])
        if total > max_chars:
            trimmed = []
            used = 0
            for p in data["text"]:
                if used >= max_chars:
                    break
                trimmed.append(p[: max_chars - used])
                used += len(p)
            data["text"] = trimmed
        return AgentResult(True, data)
