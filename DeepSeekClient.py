# DeepSeekClient.py
from config import SELENIUM_CONFIG
from selenium_client import SeleniumDeepSeekClient


class DeepSeekClient:
    """
    Клиент для взаимодействия с DeepSeek через Selenium.
    """
    def __init__(self, logger, timeout=180):
        self.logger = logger
        self.timeout = timeout
        # Создаём Selenium-клиент с настройками из SELENIUM_CONFIG
        self.selenium_client = SeleniumDeepSeekClient(logger, SELENIUM_CONFIG)

    def _run_script(self, args, input_text=None):
        # Этот метод больше не нужен, так как мы используем прямой вызов selenium_client
        # Но для обратной совместимости оставим заглушку или перенаправим
        # Однако в текущей архитектуре вызовы идут напрямую к selenium_client
        # Поэтому переопределим методы send_prompt, new_chat, copy_response
        pass

    def send_prompt(self, prompt):
        """Отправляет промпт и возвращает ответ."""
        self.logger.log("📤 Отправка запроса в DeepSeek...")
        return self.selenium_client.send_message(prompt)

    def new_chat(self):
        """Создаёт новый чат."""
        self.logger.log("🔄 Создание нового чата...")
        return self.selenium_client.new_chat()

    def copy_response(self):
        """Копирует последний ответ."""
        self.logger.log("📋 Копирование последнего ответа...")
        return self.selenium_client.copy_last_response()

    def close(self):
        """Закрывает клиент."""
        if self.selenium_client:
            self.selenium_client.close()