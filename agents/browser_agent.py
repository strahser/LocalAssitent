"""
browser_agent.py — управление браузером через Selenium (тонкая обёртка).

Selenium импортируется ЛЕНИВО (внутри run), чтобы импорт модуля и тесты
работали без установленного selenium. При отсутствии selenium или ошибке
драйвера возвращается AgentResult(ok=False, error=...).
"""
from agents.base import AgentResult, BaseAgent


class BrowserAgent(BaseAgent):
    """Тонкая обёртка над Selenium: open / screenshot / extract_text."""

    name = "browser"
    description = "Control a browser via Selenium (open / screenshot / extract_text)"

    def run(self, action: str = "open", url: str = "", **kwargs) -> AgentResult:
        # Ленивый импорт: selenium не обязателен для импорта модуля.
        try:
            from selenium import webdriver
            from selenium.webdriver.edge.options import Options as EdgeOptions
        except ImportError as exc:
            return AgentResult(
                False, None, f"selenium is not installed: {exc}"
            )

        try:
            options = EdgeOptions()
            options.add_argument("--headless")
            driver = webdriver.Edge(options=options)
        except Exception as exc:
            return AgentResult(False, None, f"failed to start browser driver: {exc}")

        try:
            if action == "open":
                if not url:
                    return AgentResult(False, None, "url is required for action=open")
                driver.get(url)
                return AgentResult(True, {"url": url, "title": driver.title})

            if action == "screenshot":
                path = kwargs.get("path") or kwargs.get("output_file") or "screenshot.png"
                driver.save_screenshot(path)
                return AgentResult(True, {"path": path})

            if action == "extract_text":
                text = driver.find_element("tag name", "body").text
                return AgentResult(True, {"text": text})

            return AgentResult(False, None, f"unknown action: {action}")
        except Exception as exc:
            return AgentResult(False, None, f"browser action failed: {exc}")
        finally:
            try:
                driver.quit()
            except Exception:
                pass
