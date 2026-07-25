"""
SeleniumDeepSeekClient - фасад, использующий специализированные обработчики.
"""
import time
from typing import Optional, Tuple

from selenium.webdriver.common.by import By

from agent.auth import DeepSeekAuth
from agent.browser.manager import BrowserManager
from agent.clipboard import ClipboardManager
from agent.handlers.file_attacher import FileAttacher
from agent.handlers.message_sender import MessageSender
from agent.handlers.response_reader import ResponseReader
from detection.action_panel import ActionPanelFinder
from detection.element_finder import ElementFinder


class SeleniumDeepSeekClient:
    def __init__(self, logger, config):
        self.logger = logger
        self.config = config

        self.browser = BrowserManager(logger, config)
        self.driver = self.browser.start()

        self.clipboard = ClipboardManager()
        self.finder = ElementFinder(self.driver, logger, config.selectors)
        self.panel_finder = ActionPanelFinder(self.driver, config, logger=self.logger)

        self.sender = MessageSender(self.driver, logger, self.finder)
        self.reader = ResponseReader(self.driver, logger, config, self.finder, self.clipboard)
        self.attacher = FileAttacher(self.driver, logger, self.finder, self.clipboard)

        self._email = ""
        self._password = ""

        auth = DeepSeekAuth(self.driver, self.logger)
        logged_in = auth.ensure_logged_in(
            email=self._email,
            password=self._password,
            timeout=120
        )
        if not logged_in:
            self.logger.log("Could not log in.", "ERROR")

    def set_auth_credentials(self, email: str, password: str):
        self._email = email
        self._password = password

    def send_message(self, message: str) -> Optional[Tuple[str, Optional[str]]]:
        self.logger.log("📤 Отправка запроса в DeepSeek...")

        old_messages = self.reader.get_assistant_messages()
        count_before = len(old_messages)
        self.logger.log(f"До отправки: {count_before} сообщений ассистента.")

        if not self.sender.send(message):
            return None

        new_message = self.reader.wait_for_new_message(count_before, self.config.selenium_timeout)
        if not new_message:
            return None

        ready = self.reader.wait_ready(new_message, self.config.stable_timeout)
        if not ready:
            self.logger.log("⚠️ Ответ не подтверждён как готовый, но попытаемся скопировать.", "WARNING")

        full_text = self.reader.get_full_text(new_message)
        code_text = self.reader.get_code_from_message(new_message)

        if full_text:
            return (full_text, code_text)

        self.logger.log("❌ Не удалось получить текст ответа.", "ERROR")
        return None

    def send_prompt_legacy(self, message: str) -> Optional[str]:
        result = self.send_message(message)
        if result is None:
            return None
        full_text, _ = result
        return full_text

    def attach_files(self, file_paths: list) -> bool:
        return self.attacher.attach(file_paths)

    def paste_files_from_clipboard(self) -> bool:
        return self.attacher.paste_from_clipboard()

    def new_chat(self):
        self.logger.log("🔄 Создание нового чата...")
        selectors = self.config.selectors.get("new_chat_xpath", [])
        if isinstance(selectors, str):
            selectors = [selectors]
        for xpath in selectors:
            try:
                elements = self.driver.find_elements(By.XPATH, xpath)
                if elements:
                    elements[0].click()
                    self.logger.log("✅ Новый чат создан.")
                    time.sleep(2)
                    return True
            except Exception:
                pass
        self.logger.log("⚠️ Кнопка 'New chat' не найдена, просто переходим на страницу чата...")
        self.driver.get("https://chat.deepseek.com/a/chat")
        time.sleep(4)
        return True

    def close(self):
        self.browser.close()
