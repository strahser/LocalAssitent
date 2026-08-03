"""
Unit-тесты для qwen/html_monitor.py (HtmlSnapshot, HtmlChangeMonitor).

Офлайн-тесты: FakeDriver вместо Selenium, без сети.
Запуск: python -m pytest tests/test_qwen_html_monitor.py -v
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from qwen.html_monitor import HtmlSnapshot, HtmlChangeMonitor


class FakeDriver:
    """Минимальный фейк драйвера: HTML/текст/элементы меняются вручную."""

    def __init__(self, html="<html><body><p>hello</p></body></html>"):
        self._html = html
        self._text = "hello"
        self.elements = {}          # css_selector -> [FakeElement]
        self.page_source = html
        self.executed_scripts = []

    def execute_script(self, script, *args):
        self.executed_scripts.append((script, args))
        if "outerHTML" in script:
            return self._html
        if "innerText" in script:
            return self._text
        if "document.body ? true" in script:
            return True
        return None

    def find_elements(self, by, selector):
        return self.elements.get(selector, [])

    def set_html(self, html, text=None):
        self._html = html
        self.page_source = html
        if text is not None:
            self._text = text


class FakeElement:
    text = ""

    def __init__(self, text=""):
        self.text = text

    def is_displayed(self):
        return True

    def click(self):
        pass

    def send_keys(self, value):
        pass

    def get_attribute(self, name):
        return None


class TestHtmlSnapshot:
    def test_to_dict_keys(self):
        snap = HtmlSnapshot("fp", 10, {"a": True}, html_len=100, ts=1.0)
        d = snap.to_dict()
        assert d["fingerprint"] == "fp"
        assert d["text_len"] == 10
        assert d["markers"] == {"a": True}
        assert d["html_len"] == 100
        assert d["ts"] == 1.0

    def test_defaults(self):
        snap = HtmlSnapshot("fp", 0, {})
        assert snap.html_len == 0
        assert snap.ts == 0.0
        assert snap.markers == {}


class TestHtmlChangeMonitor:
    def _make(self, html="<html><body>x</body></html>", text="x"):
        driver = FakeDriver(html=html)
        driver._text = text
        return HtmlChangeMonitor(driver, check_interval=0.05), driver

    def test_get_page_html_execute_script(self):
        monitor, driver = self._make("<html><body>A</body></html>")
        assert monitor.get_page_html() == "<html><body>A</body></html>"

    def test_get_page_text(self):
        monitor, driver = self._make()
        assert monitor.get_page_text() == "x"

    def test_fingerprint_stable(self):
        monitor, _ = self._make()
        fp1 = monitor.fingerprint("<html>same</html>")
        fp2 = monitor.fingerprint("<html>same</html>")
        assert fp1 == fp2
        assert len(fp1) == 64  # sha256 hex

    def test_fingerprint_differs(self):
        monitor, _ = self._make()
        fp1 = monitor.fingerprint("<html>A</html>")
        fp2 = monitor.fingerprint("<html>B</html>")
        assert fp1 != fp2

    def test_snapshot_tracks_html_change(self):
        monitor, driver = self._make("<html><body>v1</body></html>", "v1")
        snap1 = monitor.snapshot()
        driver.set_html("<html><body>v2</body></html>", "v2")
        snap2 = monitor.snapshot()
        assert snap1.fingerprint != snap2.fingerprint
        assert snap2.text_len == len("v2")

    def test_wait_for_change_detects(self):
        monitor, driver = self._make("<html><body>A</body></html>", "A")
        baseline = monitor.snapshot()
        driver.set_html("<html><body>B</body></html>", "B")
        result = monitor.wait_for_change(baseline, timeout=5, desc="test")
        assert result.fingerprint != baseline.fingerprint

    def test_wait_for_change_timeout_returns_baseline(self):
        monitor, driver = self._make("<html><body>A</body></html>", "A")
        baseline = monitor.snapshot()
        result = monitor.wait_for_change(baseline, timeout=0.3, desc="timeout")
        assert result.fingerprint == baseline.fingerprint

    def test_wait_for_change_marker_flips(self):
        monitor, driver = self._make("<html><body>A</body></html>", "A")
        baseline = monitor.snapshot()
        # Сначала маркера нет, затем появляется -> триггер change
        driver.elements[".thinking"] = []
        marker_queries = {"thinking": ".thinking"}
        # baseline.markers не содержит thinking=True, а после появления элемента -> True
        driver.elements[".thinking"] = [FakeElement()]
        result = monitor.wait_for_change(
            baseline, timeout=5, desc="marker", marker_queries=marker_queries
        )
        assert result.markers.get("thinking") is True

    def test_wait_for_stable_detects_stable(self):
        monitor, driver = self._make("<html><body>A</body></html>", "A")
        result = monitor.wait_for_stable(
            timeout=5, stable_duration=0.15, desc="stable"
        )
        assert result.fingerprint == monitor.fingerprint("<html><body>A</body></html>")

    def test_marker_found(self):
        monitor, driver = self._make()
        driver.elements[".copy"] = [FakeElement("copy")]
        assert monitor.marker(".copy") is True

    def test_marker_not_found(self):
        monitor, driver = self._make()
        assert monitor.marker(".nope") is False

    def test_marker_text(self):
        monitor, driver = self._make()
        driver.elements[".copy"] = [FakeElement("Copy answer")]
        assert monitor.marker_text(".copy") == "Copy answer"

    def test_log_stage_calls_logger(self):
        class L:
            def __init__(self):
                self.calls = []

            def log(self, msg, level="INFO"):
                self.calls.append((msg, level))

        logger = L()
        monitor, driver = self._make()
        monitor.logger = logger
        snap = monitor.snapshot()
        monitor.log_stage("file_received", snap, 1.5)
        assert any("file_received" in msg for msg, _ in logger.calls)


if __name__ == "__main__":
    import pytest
    sys.exit(pytest.main([__file__, "-q"]))
