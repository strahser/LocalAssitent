# response_copier.py
import time
from typing import Optional
from selenium.webdriver.remote.webelement import WebElement
from selenium.webdriver.common.action_chains import ActionChains
from selenium.common.exceptions import StaleElementReferenceException, ElementClickInterceptedException
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By

from action_panel_finder import ActionPanelFinder
from clipboard_manager import ClipboardManager

class ResponseCopier:
    def __init__(self, driver, config, logger=None):
        self.driver = driver
        self.config = config
        self.logger = logger
        self.panel_finder = ActionPanelFinder(driver, config, logger)
        self.clipboard = ClipboardManager()

    def copy_from_element(self, message_element: WebElement) -> Optional[str]:
        """
        Копирует ответ из переданного элемента сообщения.
        Возвращает текст или None при ошибке.
        """
        if message_element is None:
            return None

        self.logger.log("🔍 Поиск кнопки копирования...")

        # Наводим курсор для активации панели
        try:
            ActionChains(self.driver).move_to_element(message_element).perform()
            time.sleep(0.5)
        except StaleElementReferenceException:
            self.logger.log("⚠️ Элемент устарел при наведении.", "WARNING")
            return None
        except Exception as e:
            self.logger.log(f"Ошибка при наведении: {e}", "WARNING")

        copy_btn = self.panel_finder.find_copy_button(message_element)
        if not copy_btn:
            self.logger.log("❌ Кнопка копирования не найдена.", "ERROR")
            return None

        if not (copy_btn.is_displayed() and copy_btn.is_enabled()):
            self.logger.log("❌ Кнопка неактивна/невидима.", "ERROR")
            return None

        self.logger.log("✅ Кнопка Копировать найдена и активна.")

        # Надёжный клик
        if not self._click_element_safely(copy_btn):
            self.logger.log("❌ Не удалось кликнуть по кнопке.", "ERROR")
            return None

        time.sleep(0.5)  # ждём копирования
        clipboard_text = self.clipboard.get_text()
        if clipboard_text:
            return self._clean_copied_text(clipboard_text)

        self.logger.log("⚠️ Буфер обмена пуст после клика.", "WARNING")
        # Пробуем ещё раз через JS
        try:
            self.driver.execute_script("arguments[0].click();", copy_btn)
            time.sleep(0.5)
            clipboard_text = self.clipboard.get_text()
            if clipboard_text:
                return self._clean_copied_text(clipboard_text)
        except Exception as e:
            self.logger.log(f"❌ Повторный клик через JS не удался: {e}", "WARNING")

        return None

    def _click_element_safely(self, element, max_attempts=3) -> bool:
        """Кликает по элементу с обходом перехвата клика."""

        for attempt in range(max_attempts):
            try:
                self.driver.execute_script("arguments[0].scrollIntoView({block: 'center', inline: 'nearest'});", element)
                time.sleep(0.3)
                WebDriverWait(self.driver, 2).until(EC.element_to_be_clickable(element))
                element.click()
                return True
            except ElementClickInterceptedException:
                try:
                    self.driver.execute_script("arguments[0].click();", element)
                    return True
                except:
                    pass
                try:
                    ActionChains(self.driver).move_to_element(element).click().perform()
                    return True
                except:
                    pass
                try:
                    self.driver.find_element(By.TAG_NAME, "body").click()
                    time.sleep(0.3)
                except:
                    pass
                time.sleep(0.5)
            except StaleElementReferenceException:
                self.logger.log("⚠️ Элемент устарел, обновляем...", "WARNING")
                time.sleep(0.5)
        self.logger.log(f"❌ Не удалось кликнуть по элементу после {max_attempts} попыток.", "ERROR")
        return False

    def _clean_copied_text(self, text: str) -> str:
        """Удаляет служебные строки."""
        lines = text.splitlines()
        cleaned = []
        for line in lines:
            stripped = line.strip()
            if stripped in ("Копировать", "Скачать", "python", "bash", "cmd"):
                continue
            cleaned.append(line)
        return "\n".join(cleaned)