"""
QwenClient – обёртка над SeleniumQwenClient (chat.qwen.ai).
API зеркалирует agent/DeepSeekClient.py:
    send_prompt / send_prompt_with_code / continue_chat / continue_chat_with_code
    attach_files / paste_files_from_clipboard / new_chat / select_model / close
"""
from typing import Optional, Tuple

from config import SeleniumConfig, QWEN_URL, DEFAULT_QWEN_MODEL, EDGE_USER_DATA_DIR
from detection.qwen_selectors import QWEN_SELECTORS
from agent.client import SeleniumQwenClient


def build_qwen_config() -> SeleniumConfig:
    """SeleniumConfig с селекторами Qwen."""
    return SeleniumConfig(
        debug_port=9222,
        edge_user_data_dir=EDGE_USER_DATA_DIR,
        deepseek_url=QWEN_URL,
        selenium_timeout=300,
        stable_timeout=180,
        stable_duration=3,
        check_interval=1,
        response_strategy="combined",
        selectors=QWEN_SELECTORS,
    )


class QwenClient:
    def __init__(self, logger, timeout=240, email="", password="", model=DEFAULT_QWEN_MODEL):
        self.logger = logger
        self.timeout = timeout
        self.email = email
        self.password = password
        self.model = model
        self.selenium_client = SeleniumQwenClient(logger, build_qwen_config())
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

    def select_model(self, name: str = None) -> bool:
        """Выбирает модель в UI Qwen (dropdown model-selector)."""
        model = name or self.model
        return self.selenium_client.select_model(model)

    def attach_files(self, file_paths: list) -> bool:
        """Прикрепляет файлы к сообщению."""
        return self.selenium_client.attach_files(file_paths)

    def attach_files_drop(self, file_paths: list) -> bool:
        """Прикрепляет файл drag-and-drop (DataTransfer) — работает в Qwen."""
        return self.selenium_client.attach_files_drop(file_paths)

    def send_message_with_attached_file(self, message: str):
        """Отправляет короткий промпт после прикрепления файла (Qwen-путь)."""
        return self.selenium_client.send_message_with_attached_file(message)

    def paste_files_from_clipboard(self) -> bool:
        """Вставляет файлы из буфера обмена через Ctrl+V."""
        return self.selenium_client.paste_files_from_clipboard()

    def new_chat(self):
        self.logger.log("🔄 Создание нового чата...")
        return self.selenium_client.new_chat()

    def close(self):
        if self.selenium_client:
            self.selenium_client.close()
