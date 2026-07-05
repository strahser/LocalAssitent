from selenium.webdriver.remote.webelement import WebElement
from selenium.common.exceptions import NoSuchElementException
from selenium.webdriver.common.by import By
from typing import Optional


class ActionPanelFinder:
    def __init__(self, driver, config, logger=None):
        self.driver = driver
        self.config = config
        self.logger = logger

    def find_copy_button(self, message_element: WebElement) -> Optional[WebElement]:
        if self.logger:
            self.logger.log("🔍 Поиск панели действий (по 5 кнопкам в ds-flex)...")

        # Рекурсивный обход родителей для поиска контейнера ds-flex с 5 кнопками
        current = message_element
        level = 0
        while current:
            if self.logger:
                tag = current.tag_name
                classes = current.get_attribute("class") or ""
                self.logger.log(f"  Поиск на уровне {level} (текущий элемент: {tag}, class={classes[:50]})")

            try:
                containers = current.find_elements(By.XPATH, self.config.selectors["action_panel_container"])
                if self.logger:
                    self.logger.log(f"  Найдено {len(containers)} контейнеров ds-flex на этом уровне.")

                for idx, container in enumerate(containers):
                    buttons = container.find_elements(By.CSS_SELECTOR, "div[role='button']")
                    if self.logger:
                        self.logger.log(f"    Контейнер {idx}: содержит {len(buttons)} кнопок.")
                    if len(buttons) == 5:
                        if self.logger:
                            self.logger.log("✅ Найдена панель с ровно 5 кнопками.")
                        return buttons[0]
            except Exception as e:
                if self.logger:
                    self.logger.log(f"Ошибка при поиске контейнеров: {e}", "WARNING")

            # Поднимаемся на уровень выше (родитель)
            try:
                current = current.find_element(By.XPATH, "..")
                level += 1
            except:
                break

        if self.logger:
            self.logger.log("❌ Панель с 5 кнопками не найдена.", "ERROR")
        return None