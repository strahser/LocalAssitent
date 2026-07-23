import time
from typing import Optional, List
from selenium.webdriver.common.by import By
from selenium.webdriver.remote.webelement import WebElement
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException


class ElementFinder:
    def __init__(self, driver, logger, selectors=None):
        self.driver = driver
        self.logger = logger
        self.selectors = selectors or {}

    # ──────────────────────────────
    #  Сообщения ассистента
    # ──────────────────────────────

    def find_assistant_messages(self) -> List[WebElement]:
        xpaths = self.selectors.get("assistant_messages", [])
        if isinstance(xpaths, str):
            xpaths = [xpaths]
        for xpath in xpaths:
            try:
                elements = self.driver.find_elements(By.XPATH, xpath)
                if elements:
                    self.logger.log(f"✅ Найдено {len(elements)} сообщений по XPath: {xpath}")
                    return elements
            except Exception as e:
                self.logger.log(f"Ошибка по XPath {xpath}: {e}", "WARNING")
        try:
            articles = self.driver.find_elements(By.CSS_SELECTOR, "article")
            if articles:
                self.logger.log(f"✅ Найдено {len(articles)} элементов <article>")
                return articles
        except:
            pass
        self.logger.log("❌ Сообщения не найдены ни по одному селектору.", "ERROR")
        return []

    # ──────────────────────────────
    #  Поле ввода
    # ──────────────────────────────

    def find_input_box(self, timeout: int = 15) -> Optional[WebElement]:
        selectors = self.selectors.get("input_textarea", [])
        if isinstance(selectors, str):
            selectors = [selectors]
        for selector in selectors:
            try:
                input_box = WebDriverWait(self.driver, timeout).until(
                    EC.visibility_of_element_located((By.CSS_SELECTOR, selector))
                )
                self.driver.execute_script("arguments[0].scrollIntoView(true);", input_box)
                time.sleep(0.3)
                return input_box
            except TimeoutException:
                continue
            except Exception as e:
                self.logger.log(f"Ошибка поиска поля ввода ({selector}): {e}", "WARNING")
        self.logger.log("❌ Поле ввода не найдено.", "ERROR")
        return None

    # ──────────────────────────────
    #  Кнопка отправки
    # ──────────────────────────────

    def find_send_button(self) -> Optional[WebElement]:
        try:
            buttons = self.driver.find_elements(By.CSS_SELECTOR, "div[role='button']")
            for btn in buttons:
                classes = btn.get_attribute("class") or ""
                if "ds-button--circle" in classes:
                    return btn
        except Exception as e:
            self.logger.log(f"Ошибка поиска кнопки отправки: {e}", "WARNING")
        return None

    # ──────────────────────────────
    #  Блоки кода внутри сообщения
    # ──────────────────────────────

    def find_code_blocks(self, message_element: WebElement) -> List[WebElement]:
        """Ищет блоки div.md-code-block внутри сообщения."""
        selectors = self.selectors.get("code_block", ["div.md-code-block"])
        if isinstance(selectors, str):
            selectors = [selectors]
        for sel in selectors:
            try:
                blocks = message_element.find_elements(By.CSS_SELECTOR, sel)
                if blocks:
                    self.logger.log(f"✅ Найдено {len(blocks)} блоков кода по '{sel}'")
                    return blocks
            except Exception as e:
                self.logger.log(f"Ошибка поиска блоков кода ({sel}): {e}", "WARNING")
        return []

    def find_code_copy_button(self, code_block: WebElement) -> Optional[WebElement]:
        """Ищет кнопку 'Copy' внутри блока кода."""
        selectors = self.selectors.get("code_block_copy_button", [])
        if isinstance(selectors, str):
            selectors = [selectors]
        for sel in selectors:
            try:
                buttons = code_block.find_elements(By.CSS_SELECTOR, sel)
                for btn in buttons:
                    if btn.is_displayed() or True:
                        return btn
            except:
                continue
        return None

    def get_code_text_from_pre(self, code_block: WebElement) -> Optional[str]:
        """Читает код напрямую из <pre> внутри блока кода."""
        try:
            pre = code_block.find_element(By.CSS_SELECTOR, "pre")
            return pre.text.strip()
        except:
            return None

    # ──────────────────────────────
    #  Кнопка копирования сообщения
    # ──────────────────────────────

    def find_copy_button_in_message(self, message_element: WebElement) -> Optional[WebElement]:
        try:
            flex_containers = message_element.find_elements(By.CSS_SELECTOR, "div.ds-flex")
            for container in flex_containers:
                child_flex = container.find_elements(By.XPATH, "./div[contains(@class, 'ds-flex')]")
                for child in child_flex:
                    buttons = child.find_elements(By.CSS_SELECTOR, "div[role='button']")
                    if buttons:
                        return buttons[0]
            all_buttons = message_element.find_elements(By.CSS_SELECTOR, "div[role='button']")
            for btn in all_buttons:
                parent = btn.find_element(By.XPATH, "..")
                parent_classes = parent.get_attribute("class") or ""
                if "code" not in parent_classes.lower():
                    return btn
        except Exception as e:
            self.logger.log(f"Ошибка при поиске кнопки копирования: {e}", "WARNING")
        return None

    # ──────────────────────────────
    #  Прикрепление файлов
    # ──────────────────────────────

    def find_attach_button(self) -> Optional[WebElement]:
        """Ищет кнопку прикрепления файлов."""
        selectors = self.selectors.get("attach_button", [])
        if isinstance(selectors, str):
            selectors = [selectors]
        for sel in selectors:
            try:
                if "|" in sel:
                    parts = sel.split("|")
                    parent = self.driver.find_element(By.XPATH, parts[1])
                    return parent
                if sel.startswith("//") or sel.startswith(".//"):
                    elements = self.driver.find_elements(By.XPATH, sel)
                else:
                    elements = self.driver.find_elements(By.CSS_SELECTOR, sel)
                if elements:
                    self.logger.log(f"✅ Кнопка аттача найдена по '{sel}'")
                    return elements[0]
            except:
                continue

        fallback_selectors = [
            "div[role='button'] svg path[d*='M5.5498 9.75']/ancestor::div[role='button']"
        ]
        for xp in fallback_selectors:
            try:
                elements = self.driver.find_elements(By.XPATH, xp)
                if elements:
                    return elements[0]
            except:
                continue
        return None

    def find_file_input(self) -> Optional[WebElement]:
        """Ищет скрытый input[type='file']."""
        try:
            return self.driver.find_element(By.CSS_SELECTOR, "input[type='file']")
        except:
            return None

    # ──────────────────────────────
    #  Ошибки
    # ──────────────────────────────

    def find_error_elements(self) -> List[WebElement]:
        selectors = self.selectors.get("error_elements", [])
        if isinstance(selectors, str):
            selectors = [selectors]
        for xpath in selectors:
            try:
                errors = self.driver.find_elements(By.XPATH, xpath)
                if errors:
                    return errors
            except:
                continue
        return []
