"""
MessageSender - отвечает за вставку текста и отправку сообщений.
"""
import time
from typing import Optional

from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.remote.webdriver import WebDriver
from selenium.webdriver.remote.webelement import WebElement

from detection.element_finder import ElementFinder


class MessageSender:
    def __init__(self, driver: WebDriver, logger, element_finder: ElementFinder):
        self.driver = driver
        self.logger = logger
        self.finder = element_finder

    def send(self, message: str) -> bool:
        input_box = self._wait_for_input_box()
        if not input_box:
            return False
        if not self._insert_text(input_box, message):
            return False
        return self._click_send(input_box)

    def _wait_for_input_box(self, timeout: int = 15) -> Optional[WebElement]:
        return self.finder.find_input_box(timeout=timeout)

    def _insert_text(self, input_box: WebElement, message: str) -> bool:
        self.logger.log("📋 Вставка текста (React-compatible)...")
        try:
            input_box.click()
            time.sleep(0.3)
            input_box.clear()
            time.sleep(0.2)

            self.driver.execute_script("""
                const el = arguments[0];
                const text = arguments[1];
                const nativeSetter = Object.getOwnPropertyDescriptor(
                    window.HTMLTextAreaElement.prototype, 'value'
                ).set;
                nativeSetter.call(el, text);
                el.dispatchEvent(new Event('input', { bubbles: true }));
                el.dispatchEvent(new Event('change', { bubbles: true }));
            """, input_box, message)
            time.sleep(1)

            inserted = self._get_input_value(input_box)
            if inserted and len(inserted) >= len(message) // 2:
                self.logger.log(f"✅ Текст вставлен через nativeSetter (длина {len(inserted)}).")
                return True

            self.logger.log("⚠️ nativeSetter не сработал, пробуем send_keys.", "WARNING")
            input_box.send_keys(message)
            time.sleep(1)
            inserted = self._get_input_value(input_box)
            if inserted and len(inserted) >= len(message) // 2:
                self.logger.log(f"✅ Текст вставлен через send_keys (длина {len(inserted)}).")
                return True

            self.logger.log("❌ Не удалось вставить текст.", "ERROR")
            return False
        except Exception as e:
            self.logger.log(f"❌ Ошибка вставки текста: {e}", "ERROR")
            return False

    def _get_input_value(self, element: WebElement) -> str:
        try:
            val = self.driver.execute_script(
                "return arguments[0].value || arguments[0].textContent || '';", element
            )
            return val or ""
        except Exception:
            return ""

    def _click_send(self, input_box: WebElement) -> bool:
        for attempt in range(3):
            try:
                self.logger.log("📤 Отправка через Enter...")
                input_box.send_keys(Keys.RETURN)
                time.sleep(1.5)
                new_text = self._get_input_value(input_box)
                if new_text == "":
                    self.logger.log("✅ Поле очистилось, запрос принят.")
                    return True
            except Exception as e:
                self.logger.log(f"⚠️ Enter error: {e}", "WARNING")

            self.logger.log("📤 Попытка клика по кнопке отправки...")
            try:
                if self._click_send_button():
                    time.sleep(1.5)
                    new_text = self._get_input_value(input_box)
                    if new_text == "":
                        return True
                    self.logger.log("⚠️ Поле не очистилось после клика.", "WARNING")
                else:
                    self.logger.log("❌ Кнопка отправки не найдена.", "ERROR")
            except Exception as e:
                self.logger.log(f"❌ Ошибка при клике: {e}", "ERROR")

        self.logger.log("❌ Не удалось отправить после нескольких попыток.", "ERROR")
        return False

    def _click_send_button(self) -> bool:
        selectors = [
            "div.ds-button--circle:not(.ds-button--disabled)",
            "button.ds-button--filled:not(.ds-button--disabled)",
            "div[role='button'].ds-button--primary:not(.ds-button--disabled)",
            "//div[contains(@class, 'ds-button--circle') and not(contains(@class, 'ds-button--disabled'))]",
        ]
        for sel in selectors:
            try:
                if sel.startswith("//"):
                    els = self.driver.find_elements(By.XPATH, sel)
                else:
                    els = self.driver.find_elements(By.CSS_SELECTOR, sel)
                for btn in els:
                    if btn.is_displayed():
                        btn.click()
                        self.logger.log(f"✅ Клик по кнопке: {sel}")
                        return True
            except Exception:
                pass
        return False

    def is_send_button_disabled(self) -> bool:
        try:
            buttons = self.driver.find_elements(By.CSS_SELECTOR, "div[role='button']")
            for btn in buttons:
                classes = btn.get_attribute("class") or ""
                if "ds-button--circle" in classes:
                    return "ds-button--disabled" in classes
            return False
        except Exception:
            return False
