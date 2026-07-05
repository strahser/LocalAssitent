# element_finder.py
from selenium.webdriver.common.by import By
from selenium.webdriver.remote.webelement import WebElement
from selenium.common.exceptions import NoSuchElementException
from typing import Optional, List

from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

class ElementFinder:
    """Класс для поиска элементов на странице DeepSeek."""

    def __init__(self, driver, logger):
        self.driver = driver
        self.logger = logger

    def find_assistant_messages(self) -> List[WebElement]:
        """Возвращает список сообщений ассистента."""
        try:
            return self.driver.find_elements(By.XPATH, "//div[contains(@class, 'message') and contains(@class, 'assistant')]")
        except Exception as e:
            self.logger.log(f"Ошибка при поиске сообщений: {e}", "ERROR")
            return []

    def find_input_box(self, timeout: int = 15) -> Optional[WebElement]:
        """Находит поле ввода текста."""

        try:
            input_box = WebDriverWait(self.driver, timeout).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "textarea[placeholder*='Ask'], textarea"))
            )
            self.driver.execute_script("arguments[0].scrollIntoView(true);", input_box)
            return input_box
        except Exception as e:
            self.logger.log(f"Ошибка поиска поля ввода: {e}", "ERROR")
            return None

    def find_send_button(self) -> Optional[WebElement]:
        """Находит кнопку отправки (ds-button--circle)."""
        try:
            buttons = self.driver.find_elements(By.CSS_SELECTOR, "div[role='button']")
            for btn in buttons:
                classes = btn.get_attribute("class") or ""
                if "ds-button--circle" in classes:
                    return btn
            return None
        except Exception as e:
            self.logger.log(f"Ошибка поиска кнопки отправки: {e}", "WARNING")
            return None

    def find_copy_button_in_message(self, message_element: WebElement) -> Optional[WebElement]:
        """
        Устойчивый поиск кнопки копирования внутри сообщения.
        Сначала ищет панель действий (вложенные div.ds-flex), затем первую кнопку.
        Если панель не найдена, ищет любую кнопку role='button' вне блоков кода.
        """
        try:
            # 1. Поиск панели действий
            flex_containers = message_element.find_elements(By.CSS_SELECTOR, "div.ds-flex")
            for container in flex_containers:
                child_flex = container.find_elements(By.XPATH, "./div[contains(@class, 'ds-flex')]")
                for child in child_flex:
                    buttons = child.find_elements(By.CSS_SELECTOR, "div[role='button']")
                    if buttons:
                        return buttons[0]  # первая кнопка – Копировать

            # 2. Запасной вариант: все кнопки, исключая те, что внутри блоков кода
            all_buttons = message_element.find_elements(By.CSS_SELECTOR, "div[role='button']")
            for btn in all_buttons:
                # Проверяем родительские классы на наличие 'code'
                parent = btn.find_element(By.XPATH, "..")
                parent_classes = parent.get_attribute("class") or ""
                if "code" not in parent_classes.lower():
                    return btn
        except Exception as e:
            self.logger.log(f"Ошибка при поиске кнопки копирования: {e}", "WARNING")
        return None

    def find_error_elements(self) -> List[WebElement]:
        """Ищет элементы с текстом ошибки."""
        try:
            return self.driver.find_elements(By.XPATH, "//div[contains(text(), 'error') or contains(text(), 'Error')]")
        except:
            return []