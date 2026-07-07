from core.interfaces import BrowserDriver
from typing import Optional

class SendMessageUseCase:
    def __init__(self, driver: BrowserDriver):
        self.driver = driver

    def execute(self, prompt: str) -> Optional[str]:
        """Отправляет сообщение и возвращает ответ."""
        return self.driver.send_message(prompt)
