"""
html_monitor.py — мониторинг стадий чата по изменениям HTML.

HtmlSnapshot — зафиксированное состояние страницы (отпечаток, длина текста,
маркеры). HtmlChangeMonitor — опрос DOM через драйвер: ожидание изменения
(wait_for_change) и стабилизации (wait_for_stable), проверка маркеров
по CSS-селекторам. Selenium импортируется лениво (внутри методов), чтобы
модуль безопасно импортировался офлайн и в тестах без selenium.
"""
import hashlib
import time

from qwen.selectors import QWEN_SELECTORS


class HtmlSnapshot:
    """Зафиксированное состояние страницы."""

    def __init__(self, fingerprint: str, text_len: int, markers: dict,
                 html_len: int = 0, ts: float = 0.0):
        self.fingerprint = fingerprint
        self.text_len = text_len
        self.markers = markers
        self.html_len = html_len
        self.ts = ts

    def to_dict(self) -> dict:
        return {
            "fingerprint": self.fingerprint,
            "text_len": self.text_len,
            "markers": self.markers,
            "html_len": self.html_len,
            "ts": self.ts,
        }


class HtmlChangeMonitor:
    """Опрашивает HTML страницы и фиксирует переходы между стадиями."""

    def __init__(self, driver, logger=None, check_interval: float = 0.5,
                 selectors: dict = None):
        self.driver = driver
        self.logger = logger
        self.check_interval = check_interval
        self.selectors = selectors if selectors is not None else QWEN_SELECTORS

    # === Чтение страницы ===

    def get_page_html(self) -> str:
        """Полный HTML страницы: execute_script с фолбэком на page_source."""
        try:
            html = self.driver.execute_script(
                "return document.documentElement.outerHTML;"
            )
            if html:
                return html
        except Exception:
            pass
        try:
            return self.driver.page_source or ""
        except Exception:
            return ""

    def get_page_text(self) -> str:
        """Видимый текст страницы (body.innerText) или ''."""
        try:
            text = self.driver.execute_script(
                "return document.body ? document.body.innerText : '';"
            )
            return text or ""
        except Exception:
            return ""

    # === Отпечаток ===

    def fingerprint(self, html: str) -> str:
        """SHA-256 отпечаток HTML-строки."""
        return hashlib.sha256(html.encode("utf-8", errors="replace")).hexdigest()

    # === Снимки ===

    def snapshot(self, markers: dict = None) -> HtmlSnapshot:
        """Текущий снимок страницы с переданными маркерами."""
        html = self.get_page_html()
        text = self.get_page_text()
        return HtmlSnapshot(
            fingerprint=self.fingerprint(html),
            text_len=len(text),
            markers=markers or {},
            html_len=len(html),
            ts=time.time(),
        )

    # === Маркеры ===

    def marker(self, css_selector: str) -> bool:
        """True, если по CSS-селектору есть хотя бы один элемент."""
        from selenium.webdriver.common.by import By
        try:
            return bool(self.driver.find_elements(By.CSS_SELECTOR, css_selector))
        except Exception:
            return False

    def marker_text(self, css_selector: str) -> str:
        """Текст первого совпадения по селектору или ''."""
        from selenium.webdriver.common.by import By
        try:
            els = self.driver.find_elements(By.CSS_SELECTOR, css_selector)
            if els:
                return els[0].text or ""
        except Exception:
            pass
        return ""

    def _eval_markers(self, marker_queries: dict) -> dict:
        """Оценивает {имя: селектор|список} в {имя: bool}."""
        result = {}
        if not marker_queries:
            return result
        for name, query in marker_queries.items():
            selectors = query if isinstance(query, (list, tuple)) else [query]
            result[name] = any(self.marker(sel) for sel in selectors)
        return result

    # === Ожидания ===

    def wait_for_change(self, baseline: HtmlSnapshot, timeout: float,
                        desc: str = "", marker_queries: dict = None) -> HtmlSnapshot:
        """Ждёт, пока отпечаток изменится ИЛИ маркер «переключится» в True."""
        if self.logger:
            self.logger.log(f"⏳ waiting change: {desc}")
        start = time.time()
        while time.time() - start < timeout:
            snap = self.snapshot(markers=self._eval_markers(marker_queries))
            changed = snap.fingerprint != baseline.fingerprint
            if not changed and marker_queries:
                for name, present in snap.markers.items():
                    if present and not baseline.markers.get(name):
                        changed = True
                        break
            if changed:
                if self.logger:
                    self.logger.log(
                        f"✅ change detected: {desc} "
                        f"(text_len {snap.text_len}, html_len {snap.html_len})"
                    )
                return snap
            time.sleep(self.check_interval)
        if self.logger:
            self.logger.log(f"ERROR: timeout waiting change: {desc}", "ERROR")
        return baseline

    def wait_for_stable(self, timeout: float, stable_duration: float = 2.0,
                        desc: str = "", marker_queries: dict = None) -> HtmlSnapshot:
        """Ждёт, пока отпечаток и маркеры не меняются stable_duration секунд."""
        if self.logger:
            self.logger.log(f"⏳ waiting stable: {desc}")
        start = time.time()
        last_fp = None
        last_markers = None
        stable_since = None
        last_snap = None
        while time.time() - start < timeout:
            markers = self._eval_markers(marker_queries)
            snap = self.snapshot(markers=markers)
            if snap.fingerprint != last_fp or markers != last_markers:
                last_fp = snap.fingerprint
                last_markers = markers
                stable_since = time.time()
            markers_ok = True
            if marker_queries:
                markers_ok = all(markers.get(name) for name in marker_queries)
            if (stable_since is not None
                    and time.time() - stable_since >= stable_duration
                    and markers_ok):
                if self.logger:
                    self.logger.log(
                        f"✅ stable: {desc} "
                        f"(text_len {snap.text_len}, html_len {snap.html_len})"
                    )
                return snap
            last_snap = snap
            time.sleep(self.check_interval)
        if self.logger:
            self.logger.log(f"ERROR: timeout waiting stable: {desc}", "ERROR")
        return last_snap if last_snap is not None else self.snapshot()

    # === Логирование стадий ===

    def log_stage(self, stage: str, snapshot: HtmlSnapshot, elapsed: float) -> None:
        """Фиксирует завершение стадии в логе."""
        if self.logger:
            self.logger.log(
                f"🏁 STAGE: {stage} (t={elapsed:.1f}s, text_len={snapshot.text_len})"
            )
