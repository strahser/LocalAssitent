"""
Unit-тесты для qwen/dnd_uploader.py (DragAndDropUploader).

Офлайн-тесты: FakeDriver, без сети и без Selenium.
Запуск: python -m pytest tests/test_qwen_dnd_uploader.py -v
"""
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from qwen.dnd_uploader import DragAndDropUploader, MIME_TYPES


class FakeDriver:
    def __init__(self):
        self.elements = {}
        self.executed_scripts = []
        self.file_inputs = []

    def execute_script(self, script, *args):
        self.executed_scripts.append((script, args))
        return True

    def find_elements(self, by, selector):
        if selector == "input[type=file]":
            return self.file_inputs
        return self.elements.get(selector, [])


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


class TestDragAndDropUploader:
    def _make(self):
        driver = FakeDriver()
        return DragAndDropUploader(driver), driver

    def _tmp_file(self, content="hello world", ext=".txt"):
        fd, path = tempfile.mkstemp(suffix=ext)
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(content)
        return path

    def test_guess_mime_known(self):
        uploader, _ = self._make()
        assert uploader.guess_mime(".md") == "text/markdown"
        assert uploader.guess_mime(".py") == "text/x-python"
        assert uploader.guess_mime(".pdf") == "application/pdf"

    def test_guess_mime_unknown(self):
        uploader, _ = self._make()
        assert uploader.guess_mime(".zzz") == "application/octet-stream"

    def test_guess_mime_case_insensitive(self):
        uploader, _ = self._make()
        assert uploader.guess_mime(".TXT") == "text/plain"

    def test_build_drop_script_contains_components(self):
        uploader, _ = self._make()
        path = self._tmp_file("data", ".py")
        script = uploader.build_drop_script(path, "textarea")
        assert "DataTransfer" in script
        assert "DragEvent" in script
        assert "dragenter" in script
        assert "dragover" in script
        assert "drop" in script
        assert "atob(" in script
        assert "new File(" in script
        assert 'type: "text/x-python"' in script
        assert os.path.basename(path) in script
        os.remove(path)

    def test_build_drop_script_uses_selector(self):
        uploader, _ = self._make()
        path = self._tmp_file()
        script = uploader.build_drop_script(path, "#main")
        assert '"#main"' in script
        assert "document.querySelector(selector)" in script
        os.remove(path)

    def test_build_drop_script_base64_correct(self):
        import base64
        uploader, _ = self._make()
        path = self._tmp_file("abc123", ".txt")
        script = uploader.build_drop_script(path, "body")
        expected = base64.b64encode(b"abc123").decode("ascii")
        assert expected in script
        os.remove(path)

    def test_resolve_drop_selector_finds_textarea(self):
        uploader, driver = self._make()
        driver.elements["textarea"] = [FakeElement()]
        sel = uploader._resolve_drop_selector()
        assert sel == "textarea"

    def test_resolve_drop_selector_fallback_main(self):
        uploader, driver = self._make()
        sel = uploader._resolve_drop_selector()
        assert sel == "main"

    def test_upload_success_via_dnd(self):
        uploader, driver = self._make()
        path = self._tmp_file()
        driver.elements["textarea"] = [FakeElement()]
        assert uploader.upload(path) is True
        assert driver.executed_scripts  # execute_script вызван
        os.remove(path)

    def test_upload_missing_file_returns_false(self):
        uploader, driver = self._make()
        assert uploader.upload("C:\\nonexistent_file_xyz.txt") is False
        assert not driver.executed_scripts

    def test_upload_fallback_input_when_script_fails(self):
        driver = FakeDriver()

        class FailingDriver(FakeDriver):
            def execute_script(self, script, *args):
                self.executed_scripts.append((script, args))
                return False

        driver = FailingDriver()
        uploader = DragAndDropUploader(driver)
        fake_input = FakeElement()
        driver.file_inputs = [fake_input]
        path = self._tmp_file()
        assert uploader.upload(path) is True
        os.remove(path)


if __name__ == "__main__":
    import pytest
    sys.exit(pytest.main([__file__, "-q"]))
