from typing import Optional, Tuple
from config import SELENIUM_CONFIG
from agent.selenium_client import SeleniumDeepSeekClient


class DeepSeekClient:
    def __init__(self, logger, timeout=180, email="", password=""):
        self.logger = logger
        self.timeout = timeout
        self.email = email
        self.password = password
        self.selenium_client = SeleniumDeepSeekClient(logger, SELENIUM_CONFIG)
        self.selenium_client.set_auth_credentials(email, password)

    def send_prompt(self, prompt: str) -> Optional[str]:
        """Отправляет промпт и возвращает только текст ответа."""
        result = self.selenium_client.send_message(prompt)
        if result is None:
            return None
        full_text, _ = result
        return full_text

    def send_prompt_with_code(self, prompt: str) -> Optional[Tuple[str, Optional[str]]]:
        """Отправляет промпт и возвращает (full_text, code_text)."""
        return self.selenium_client.send_message(prompt)

    def continue_chat(self, message: str) -> Optional[str]:
        """Продолжение диалога в существующем чате."""
        self.logger.log("💬 Продолжение диалога в существующем чате...")
        return self.send_prompt(message)

    def continue_chat_with_code(self, message: str) -> Optional[Tuple[str, Optional[str]]]:
        """Продолжение диалога с возвратом кода."""
        return self.send_prompt_with_code(message)

    def attach_files(self, file_paths: list) -> bool:
        """Прикрепляет файлы к сообщению."""
        return self.selenium_client.attach_files(file_paths)

    def new_chat(self):
        self.logger.log("🔄 Создание нового чата...")
        return self.selenium_client.new_chat()

    def copy_response(self):
        self.logger.log("📋 Копирование последнего ответа...")
        return self.selenium_client.copy_last_response()

    def close(self):
        if self.selenium_client:
            self.selenium_client.close()
