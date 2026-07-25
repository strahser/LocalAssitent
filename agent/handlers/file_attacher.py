"""
FileAttacher - отвечает за прикрепление файлов к сообщению.
"""
import os
import time
from typing import List

from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.remote.webdriver import WebDriver

from agent.clipboard import ClipboardManager
from detection.element_finder import ElementFinder


class FileAttacher:
    def __init__(self, driver: WebDriver, logger, element_finder: ElementFinder,
                 clipboard: ClipboardManager):
        self.driver = driver
        self.logger = logger
        self.finder = element_finder
        self.clipboard = clipboard

    def attach(self, file_paths: List[str]) -> bool:
        if not file_paths:
            self.logger.log("⚠️ Список файлов пуст.")
            return True

        abs_paths = self._resolve_file_paths(file_paths)
        if not abs_paths:
            self.logger.log("❌ Ни один из указанных файлов не найден.", "ERROR")
            return False
        if len(abs_paths) < len(file_paths):
            self.logger.log(f"⚠️ {len(file_paths) - len(abs_paths)} файлов не найдено, пропущены.", "WARNING")

        self.logger.log(f"📎 Прикрепление {len(abs_paths)} файлов...")

        file_input = self.finder.find_file_input()
        if file_input:
            self.logger.log(f"✅ Найден input[type='file'], отправляем пути...")
            try:
                self.driver.execute_script(
                    "arguments[0].style.display = 'block'; arguments[0].style.visibility = 'visible';",
                    file_input
                )
                time.sleep(0.2)
                file_input.send_keys("\n".join(abs_paths))
                time.sleep(2)
                self.logger.log("✅ Файлы отправлены через input[type='file'].")
                return True
            except Exception as e:
                self.logger.log(f"⚠️ Ошибка отправки через input[type='file']: {e}", "WARNING")

        self.logger.log("🔄 Пробуем через клик по кнопке аттача...")
        attach_btn = self.finder.find_attach_button()
        if attach_btn:
            try:
                attach_btn.click()
                time.sleep(1)
                file_input = self.finder.find_file_input()
                if file_input:
                    self.driver.execute_script(
                        "arguments[0].style.display = 'block'; arguments[0].style.visibility = 'visible';",
                        file_input
                    )
                    file_input.send_keys("\n".join(abs_paths))
                    time.sleep(2)
                    self.logger.log("✅ Файлы прикреплены после клика по кнопке.")
                    return True
                else:
                    self.logger.log("⚠️ input[type='file'] не появился после клика.", "WARNING")
                    return False
            except Exception as e:
                self.logger.log(f"❌ Ошибка при клике по кнопке аттача: {e}", "ERROR")
                return False
        else:
            self.logger.log("❌ Кнопка аттача не найдена.", "ERROR")
            return False

    def paste_from_clipboard(self) -> bool:
        if not self.clipboard.has_files():
            self.logger.log("⚠️ В буфере обмена нет файлов.", "WARNING")
            return False

        files = self.clipboard.get_files()
        if not files:
            self.logger.log("⚠️ Не удалось получить файлы из буфера обмена.", "WARNING")
            return False

        self.logger.log(f"📎 Найдено {len(files)} файлов в буфере обмена:")
        for f in files:
            self.logger.log(f"   - {f}")

        input_box = self.finder.find_input_box()
        if not input_box:
            self.logger.log("❌ Поле ввода не найдено.", "ERROR")
            return False

        input_box.click()
        time.sleep(0.3)

        try:
            ActionChains(self.driver) \
                .key_down(Keys.CONTROL) \
                .send_keys("v") \
                .key_up(Keys.CONTROL) \
                .perform()
            time.sleep(2)
            self.logger.log("✅ Ctrl+V выполнен. Файлы должны быть прикреплены.")
            return True
        except Exception as e:
            self.logger.log(f"❌ Ошибка при выполнении Ctrl+V: {e}", "ERROR")
            return False

    def _resolve_file_paths(self, file_paths: List[str]) -> List[str]:
        base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        resolved = []
        for f in file_paths:
            abs_cwd = os.path.abspath(f)
            if os.path.exists(abs_cwd):
                resolved.append(abs_cwd)
                continue
            abs_base = os.path.join(base, f)
            if os.path.exists(abs_base):
                resolved.append(abs_base)
                continue
            self.logger.log(f"⚠️ Файл не найден: {f}", "WARNING")
        return resolved
