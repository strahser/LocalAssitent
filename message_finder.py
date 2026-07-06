# message_finder.py
from typing import List, Optional
from selenium.webdriver.remote.webelement import WebElement
from selenium.webdriver.common.by import By

class MessageFinder:
    def __init__(self, driver, config, logger=None):
        self.driver = driver
        self.config = config
        self.logger = logger

    def get_assistant_messages(self) -> List[WebElement]:
        """Возвращает все сообщения ассистента, перебирая альтернативные XPath."""
        selectors = self.config.selectors.get("assistant_messages", [])
        if isinstance(selectors, str):
            selectors = [selectors]

        all_messages = []
        for xpath in selectors:
            try:
                elements = self.driver.find_elements(By.XPATH, xpath)
                if elements:
                    all_messages.extend(elements)
            except Exception as e:
                if self.logger:
                    self.logger.log(f"Ошибка при поиске по XPath {xpath}: {e}", "WARNING")

        # Удаляем дубликаты (по уникальности элемента)
        seen = set()
        unique_messages = []
        for el in all_messages:
            if el.id not in seen:
                seen.add(el.id)
                unique_messages.append(el)
        return unique_messages

    def get_last_assistant_message(self) -> Optional[WebElement]:
        """Возвращает последнее сообщение ассистента."""
        messages = self.get_assistant_messages()
        return messages[-1] if messages else None