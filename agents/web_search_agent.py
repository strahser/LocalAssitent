"""
web_search_agent.py — агент веб-поиска через DuckDuckGo HTML.

Использует только стандартную библиотеку (urllib.request + html.parser),
без внешних зависимостей (bs4 не требуется). При сетевой ошибке
возвращает AgentResult(ok=False, error=...).
"""
import urllib.parse
import urllib.request
from html.parser import HTMLParser

from agents.base import AgentResult, BaseAgent

DDG_HTML_URL = "https://html.duckduckgo.com/html/"


class _DDGResultParser(HTMLParser):
    """Минимальный парсер результатов DuckDuckGo HTML."""

    def __init__(self):
        super().__init__()
        self.results = []
        self._in_result = False
        self._in_link = False
        self._in_snippet = False
        self._current = None
        self._buf = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        cls = attrs.get("class", "")
        if tag == "div" and "result" in cls.split():
            self._in_result = True
            self._current = {"title": "", "url": "", "snippet": ""}
            self.results.append(self._current)
        elif self._in_result and tag == "a" and "result__a" in cls.split():
            self._in_link = True
            self._buf = []
            if "href" in attrs:
                self._current["url"] = attrs["href"]
        elif self._in_result and tag == "a" and "result__snippet" in cls.split():
            self._in_snippet = True
            self._buf = []

    def handle_endtag(self, tag):
        if tag == "div" and self._in_result and self._current:
            if not any(self._current.values()):
                self.results.pop()
            self._in_result = False
        elif tag == "a" and self._in_link:
            self._current["title"] = " ".join("".join(self._buf).split())
            self._in_link = False
            self._buf = []
        elif tag == "a" and self._in_snippet:
            self._current["snippet"] = " ".join("".join(self._buf).split())
            self._in_snippet = False
            self._buf = []

    def handle_data(self, data):
        if self._in_link or self._in_snippet:
            self._buf.append(data)


def _fetch_ddg(query: str, max_results: int):
    """Запрос к DuckDuckGo HTML и парсинг результатов."""
    params = urllib.parse.urlencode({"q": query})
    url = f"{DDG_HTML_URL}?{params}"
    req = urllib.request.Request(
        url,
        headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"},
    )
    with urllib.request.urlopen(req, timeout=15) as resp:
        html = resp.read().decode("utf-8", errors="replace")

    parser = _DDGResultParser()
    parser.feed(html)
    parser.close()

    results = []
    for item in parser.results:
        url = item["url"]
        # URL может быть обёрткой DuckDuckGo (//duckduckgo.com/l/?uddg=...)
        if "uddg=" in url:
            try:
                parsed = urllib.parse.parse_qs(
                    urllib.parse.urlsplit(url).query
                )
                if "uddg" in parsed:
                    url = parsed["uddg"][0]
            except Exception:
                pass
        if item["title"] and url:
            results.append(
                {"title": item["title"], "url": url, "snippet": item["snippet"]}
            )
        if len(results) >= max_results:
            break
    return results


class WebSearchAgent(BaseAgent):
    """Поиск в вебе через DuckDuckGo (только stdlib)."""

    name = "web_search"
    description = "Web search via DuckDuckGo HTML (stdlib only)"

    def run(self, query: str, max_results: int = 5) -> AgentResult:
        if not query:
            return AgentResult(False, [], "query is required")
        try:
            results = _fetch_ddg(query, max_results)
        except Exception as exc:
            return AgentResult(False, [], f"search failed: {exc}")
        return AgentResult(True, results)
