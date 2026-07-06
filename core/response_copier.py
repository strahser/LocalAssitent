import time
from typing import Optional
from selenium.webdriver.remote.webelement import WebElement
from selenium.webdriver.common.action_chains import ActionChains
from selenium.common.exceptions import StaleElementReferenceException, ElementClickInterceptedException
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By

from core.action_panel_finder import ActionPanelFinder
from utils.clipboard_manager import ClipboardManager

class ResponseCopier:
    def __init__(self, driver, config, logger=None):
        self.driver = driver
        self.config = config
        self.logger = logger
        self.panel_finder = ActionPanelFinder(driver, config, logger)
        self.clipboard = ClipboardManager()

    def copy_from_element(self, message_element: WebElement) -> Optional[str]:
        if message_element is None:
            return None

        self.logger.debug("Поиск кнопки копирования...")
        try:
            ActionChains(self.driver).move_to_element(message_element).perform()
            time.sleep(0.5)
        except StaleElementReferenceException:
            self.logger.warning("Элемент устарел при наведении.")
            return None
        except Exception as e:
            self.logger.warning(f"Ошибка при наведении: {e}")

        copy_btn = self.panel_finder.find_copy_button(message_element)
        if not copy_btn:
            self.logger.warning("Кнопка копирования не найдена.")
            return None

        if not (copy_btn.is_displayed() and copy_btn.is_enabled()):
            self.logger.warning("Кнопка неактивна/невидима.")
            return None

        self.logger.debug("Кнопка Копировать найдена и активна.")

        if not self._click_element_safely(copy_btn):
            self.logger.warning("Не удалось кликнуть по кнопке.")
            return None

        time.sleep(0.5)
        clipboard_text = self.clipboard.get_text()
        if clipboard_text:
            return self._clean_copied_text(clipboard_text)

        self.logger.warning("Буфер обмена пуст после клика.")
        try:
            self.driver.execute_script("arguments[0].click();", copy_btn)
            time.sleep(0.5)
            clipboard_text = self.clipboard.get_text()
            if clipboard_text:
                return self._clean_copied_text(clipboard_text)
        except Exception as e:
            self.logger.warning(f"Повторный клик через JS не удался: {e}")

        return None

    def _click_element_safely(self, element, max_attempts=3) -> bool:
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
                self.logger.warning("Элемент устарел, обновляем...")
                time.sleep(0.5)
        self.logger.warning(f"Не удалось кликнуть по элементу после {max_attempts} попыток.")
        return False

    def _clean_copied_text(self, text: str) -> str:
        lines = text.splitlines()
        cleaned = []
        for line in lines:
            stripped = line.strip()
            if stripped in ("Копировать", "Скачать", "python", "bash", "cmd"):
                continue
            cleaned.append(line)
        return "\n".join(cleaned)
