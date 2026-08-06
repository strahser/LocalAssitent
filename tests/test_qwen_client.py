"""
Unit-тесты для qwen/client.py (QwenClient) — полный поток задачи.

Офлайн-тесты: FakeDriver, агенты монитора/аплоадера подменяются.
Запуск: python -m pytest tests/test_qwen_client.py -v
"""
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from qwen.client import QwenClient
from qwen.html_monitor import HtmlSnapshot
from qwen.selectors import QWEN_SELECTORS


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


class FakeDriver:
    """Фейк драйвера: HTML/текст/элементы + журнал execute_script."""

    def __init__(self, html="<html><body>hi</body></html>", text="hi"):
        self._html = html
        self._text = text
        self.elements = {}
        self.page_source = html
        self.executed_scripts = []
        self.url = ""

    def execute_script(self, script, *args):
        self.executed_scripts.append((script, args))
        if "nativeSetter" in script:
            # (el, text) → сохраняем вставленный текст для value-скрипта
            if len(args) >= 2:
                setattr(args[0], "_value", args[1])
            return True
        if "outerHTML" in script:
            return self._html
        if "innerText" in script:
            return self._text
        if "document.body ? true" in script:
            return True
        if "arguments[0].value" in script or "textContent" in script:
            el = args[0] if args else None
            return getattr(el, "_value", getattr(el, "text", ""))
        return None

    def find_elements(self, by, selector):
        return self.elements.get(selector, [])

    def get(self, url):
        self.url = url

    def quit(self):
        pass

    def close(self):
        pass

    def set_html(self, html, text=None):
        self._html = html
        self.page_source = html
        if text is not None:
            self._text = text


class FakeLogger:
    def __init__(self):
        self.messages = []

    def log(self, message, level="INFO"):
        self.messages.append((message, level))


class TestQwenClient:
    def _make_client(self, driver=None):
        logger = FakeLogger()
        client = QwenClient(logger, driver=driver)
        return client, logger

    def test_init_defaults(self):
        client, _ = self._make_client()
        assert client.url == "https://chat.qwen.ai"
        assert client.selectors == QWEN_SELECTORS
        assert client.monitor is None

    def test_connect_with_existing_driver_noop(self):
        driver = FakeDriver()
        client, _ = self._make_client(driver)
        client.connect()
        assert client.driver is driver
        assert client.monitor is not None
        assert client._uploader is not None

    def test_open_chat_sets_url(self):
        driver = FakeDriver()
        client, _ = self._make_client(driver)
        client.connect()
        client.open_chat()
        assert driver.url == "https://chat.qwen.ai"

    def test_send_task_file_delegates_to_uploader(self):
        driver = FakeDriver()
        client, _ = self._make_client(driver)
        client.connect()

        class FakeUploader:
            def __init__(self):
                self.called = False

            def upload(self, path):
                self.called = True
                return True

        client._uploader = FakeUploader()
        assert client.send_task_file("task.txt") is True
        assert client._uploader.called

    def test_wait_file_received_returns_snapshot(self):
        driver = FakeDriver()
        client, _ = self._make_client(driver)
        client.connect()
        driver.elements[QWEN_SELECTORS["file_chip"][0]] = [FakeElement("file chip")]
        snap = client.wait_file_received(timeout=5, file_name="")
        assert isinstance(snap, HtmlSnapshot)

    def test_send_prompt_inserts_and_sends(self):
        driver = FakeDriver()
        client, _ = self._make_client(driver)
        client.connect()
        # textarea найдена и видима
        textarea = FakeElement("")
        driver.elements["textarea"] = [textarea]
        # nativeSetter путь: execute_script вернёт None для value-скрипта,
        # поэтому проверяем что send_or_enter вызван через Enter
        assert client.send_prompt("Hello qwen") is True
        # execute_script вызывался для вставки (скрипт с nativeSetter)
        assert any("nativeSetter" in s for s, _ in driver.executed_scripts)

    def test_send_prompt_no_textarea_returns_false(self):
        driver = FakeDriver()
        client, _ = self._make_client(driver)
        client.connect()
        driver.elements.clear()
        assert client.send_prompt("x") is False

    def test_wait_thinking_started_change(self):
        driver = FakeDriver()
        client, _ = self._make_client(driver)
        client.connect()
        baseline_html = driver._html
        client.monitor.check_interval = 0.05
        driver.set_html("<html><body>thinking... spinner</body></html>", "thinking")
        snap = client.wait_thinking_started(timeout=5)
        assert snap.fingerprint != client.monitor.fingerprint(baseline_html)

    def test_wait_answer_ready_returns_snapshot(self):
        driver = FakeDriver()
        client, _ = self._make_client(driver)
        client.connect()
        client.monitor.check_interval = 0.05
        driver.elements[QWEN_SELECTORS["copy_answer_button"][0]] = [FakeElement("copy")]
        snap = client.wait_answer_ready(timeout=5, stable_duration=0.15)
        assert isinstance(snap, HtmlSnapshot)

    def test_extract_answer_copy_button_clipboard(self):
        driver = FakeDriver()
        client, _ = self._make_client(driver)
        client.connect()
        driver.elements[QWEN_SELECTORS["copy_answer_button"][0]] = [FakeElement("copy")]
        # client.py импортирует ClipboardManager лениво (from agent.clipboard)
        # внутри extract_answer → патчим класс в agent.clipboard.
        import agent.clipboard
        original = agent.clipboard.ClipboardManager

        class FakeClipboard:
            @staticmethod
            def get_text():
                return "ANSWER TEXT"

        agent.clipboard.ClipboardManager = FakeClipboard
        try:
            ans = client.extract_answer()
            assert ans == "ANSWER TEXT"
        finally:
            agent.clipboard.ClipboardManager = original

    def test_extract_answer_fallback_message_text(self):
        driver = FakeDriver()
        client, _ = self._make_client(driver)
        client.connect()
        # без кнопки copy, но есть сообщение ассистента
        sel = QWEN_SELECTORS["assistant_message"][0]
        driver.elements[sel] = [FakeElement("first"), FakeElement("final answer")]
        ans = client.extract_answer()
        assert ans == "final answer"

    def test_save_answer_writes_file(self):
        driver = FakeDriver()
        client, _ = self._make_client(driver)
        client.connect()
        tmpdir = tempfile.mkdtemp()
        out = os.path.join(tmpdir, "answer.md")
        path = client.save_answer("RESULT", out)
        assert os.path.exists(path)
        content = open(path, encoding="utf-8").read()
        assert "RESULT" in content
        assert "# Ответ Qwen" in content

    def test_normalize_answer_text_crlf(self):
        """CRLF и одиночные \r нормализуются в \n; дубли пустых строк убираются."""
        raw = "Первая строка\r\nВторая\r\r\n\r\nТретья"
        got = QwenClient.normalize_answer_text(raw)
        assert "\r" not in got
        assert "\n\n\n" not in got
        assert got == "Первая строка\nВторая\n\nТретья"

    def test_normalize_answer_text_empty(self):
        assert QwenClient.normalize_answer_text("") == ""
        assert QwenClient.normalize_answer_text(None) == ""

    def test_save_all_answers_writes_md(self):
        driver = FakeDriver()
        client, _ = self._make_client(driver)
        client.connect()
        tmpdir = tempfile.mkdtemp()
        out = os.path.join(tmpdir, "all.md")
        answers = [
            {"index": 1, "text": "Ответ один", "error": None},
            {"index": 2, "text": "Ответ два\r\nстрокой", "error": "copy button not found"},
        ]
        path = client.save_all_answers(answers, out, chat_id="abc-123")
        assert os.path.exists(path)
        content = open(path, encoding="utf-8").read()
        assert "abc-123" in content
        assert "## Ответ 1" in content
        assert "Ответ один" in content
        assert "## Ответ 2" in content
        assert "Ответ два" in content
        assert "copy button not found" in content

    def test_run_task_full_flow(self):
        driver = FakeDriver()
        client, _ = self._make_client(driver)
        client.connect()
        client.monitor.check_interval = 0.02
        # uploader: успешный дроп
        client._uploader = type("U", (), {"upload": lambda self, p: True})()

        tmpdir = tempfile.mkdtemp()
        task_file = os.path.join(tmpdir, "task.txt")
        with open(task_file, "w", encoding="utf-8") as f:
            f.write("task data")
        out = os.path.join(tmpdir, "out.md")

        # элементы для потока
        textarea = FakeElement("")
        driver.elements["textarea"] = [textarea]
        # чип файла появится после дропа
        driver.elements[QWEN_SELECTORS["file_chip"][0]] = [FakeElement("chip")]
        # индикатор думания после отправки
        driver.elements[QWEN_SELECTORS["thinking_indicator"][0]] = [FakeElement("spinner")]
        # кнопка copy после ответа
        driver.elements[QWEN_SELECTORS["copy_answer_button"][0]] = [FakeElement("copy")]
        # сообщение ассистента как fallback
        driver.elements[QWEN_SELECTORS["assistant_message"][0]] = [FakeElement("ANSWER")]

        import agent.clipboard
        original = agent.clipboard.ClipboardManager

        class FakeClipboard:
            @staticmethod
            def get_text():
                return "ANSWER FROM CLIPBOARD"

        agent.clipboard.ClipboardManager = FakeClipboard
        try:
            result = client.run_task(
                file_path=task_file,
                prompt="analyze",
                output_file=out,
                timeout_file=5,
                timeout_thinking=5,
                timeout_answer=5,
            )
        finally:
            agent.clipboard.ClipboardManager = original

        assert result["ok"] is True, result.get("error")
        assert result["stages"]["file_received"] > 0
        assert result["stages"]["thinking_started"] > 0
        assert result["stages"]["answer_ready"] > 0
        assert result["answer"] == "ANSWER FROM CLIPBOARD"
        assert os.path.exists(out)


if __name__ == "__main__":
    import pytest
    sys.exit(pytest.main([__file__, "-q"]))
