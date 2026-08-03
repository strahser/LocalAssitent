"""
dnd_uploader.py — загрузка файла в chat.qwen.ai через drag-and-drop.

DragAndDropUploader строит JS-скрипт, который создаёт File из base64-данных
и рассылает DragEvent (dragenter/dragover/drop) с DataTransfer на целевой
элемент. Если скрипт не сработал (вернул falsy) — фолбэк на input[type=file]
через send_keys. Selenium импортируется лениво (внутри методов).
"""
import base64
import json
import os
import time

from qwen.selectors import QWEN_SELECTORS


MIME_TYPES = {
    ".txt": "text/plain",
    ".md": "text/markdown",
    ".py": "text/x-python",
    ".json": "application/json",
    ".cs": "text/plain",
    ".xaml": "application/xaml+xml",
    ".xml": "application/xml",
    ".csv": "text/csv",
    ".pdf": "application/pdf",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".html": "text/html",
    ".htm": "text/html",
    ".js": "text/javascript",
    ".ts": "text/plain",
    ".css": "text/css",
    ".svg": "image/svg+xml",
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
}


class DragAndDropUploader:
    """Загрузка файла drag-and-drop'ом с фолбэком на input[type=file]."""

    def __init__(self, driver, logger=None, selectors: dict = None):
        self.driver = driver
        self.logger = logger
        self.selectors = selectors if selectors is not None else QWEN_SELECTORS

    def guess_mime(self, ext: str) -> str:
        """MIME-тип по расширению; по умолчанию application/octet-stream."""
        return MIME_TYPES.get(ext.lower(), "application/octet-stream")

    def build_drop_script(self, file_path: str, drop_selector: str) -> str:
        """JS: base64 -> File -> DataTransfer -> DragEvent на drop-таргете."""
        with open(file_path, "rb") as f:
            b64 = base64.b64encode(f.read()).decode("ascii")
        name = os.path.basename(file_path)
        mime = self.guess_mime(os.path.splitext(name)[1])
        sel_json = json.dumps(drop_selector or "")
        b64_json = json.dumps(b64)
        name_json = json.dumps(name)
        mime_json = json.dumps(mime)
        return (
            "(function() {\n"
            "  try {\n"
            f"    const selector = {sel_json};\n"
            "    const target = selector ? document.querySelector(selector) : null;\n"
            "    const dropTarget = target || document.body;\n"
            f"    const bin = atob({b64_json});\n"
            "    const arr = new Uint8Array(bin.length);\n"
            "    for (let i = 0; i < bin.length; i++) { arr[i] = bin.charCodeAt(i); }\n"
            f"    const file = new File([arr], {name_json}, {{ type: {mime_json} }});\n"
            "    const dt = new DataTransfer();\n"
            "    dt.items.add(file);\n"
            "    const opts = { bubbles: true, cancelable: true, dataTransfer: dt };\n"
            "    dropTarget.dispatchEvent(new DragEvent('dragenter', opts));\n"
            "    dropTarget.dispatchEvent(new DragEvent('dragover', opts));\n"
            "    dropTarget.dispatchEvent(new DragEvent('drop', opts));\n"
            "    return true;\n"
            "  } catch (e) {\n"
            "    return false;\n"
            "  }\n"
            "})();\n"
        )

    def _resolve_drop_selector(self) -> str:
        """Текстовое поле по selectors['input_textarea'], иначе 'main'."""
        from selenium.webdriver.common.by import By
        for sel in self.selectors.get("input_textarea", []):
            try:
                if self.driver.find_elements(By.CSS_SELECTOR, sel):
                    return sel
            except Exception:
                continue
        return "main"

    def upload(self, file_path: str, drop_selector: str = None) -> bool:
        """Сбрасывает файл drag-and-drop'ом; при неудаче — input[type=file]."""
        if not os.path.exists(file_path):
            if self.logger:
                self.logger.log(f"❌ Файл не найден: {file_path}", "ERROR")
            return False

        if drop_selector is None:
            drop_selector = self._resolve_drop_selector()

        if self.logger:
            self.logger.log(f"📎 drop file: {file_path} -> {drop_selector}")

        script = self.build_drop_script(file_path, drop_selector)
        try:
            result = self.driver.execute_script(script)
        except Exception as e:
            if self.logger:
                self.logger.log(f"⚠️ execute_script drop failed: {e}", "WARNING")
            result = None

        time.sleep(1.0)

        if result:
            if self.logger:
                self.logger.log("✅ dropped")
            return True

        if self.logger:
            self.logger.log("⚠️ drop не сработал, фолбэк input[type=file]", "WARNING")
        return self._fallback_input(file_path)

    def _fallback_input(self, file_path: str) -> bool:
        """Фолбэк: send_keys в input[type=file]."""
        from selenium.webdriver.common.by import By
        try:
            inputs = self.driver.find_elements(By.CSS_SELECTOR, "input[type=file]")
            if inputs:
                inputs[0].send_keys(os.path.abspath(file_path))
                time.sleep(0.5)
                if self.logger:
                    self.logger.log("✅ fallback: файл задан через input[type=file]")
                return True
            if self.logger:
                self.logger.log("❌ fallback: input[type=file] не найден", "ERROR")
        except Exception as e:
            if self.logger:
                self.logger.log(f"❌ fallback failed: {e}", "ERROR")
        return False
