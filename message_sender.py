# message_sender.py
import time
from typing import Optional
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.action_chains import ActionChains
from selenium.common.exceptions import StaleElementReferenceException, TimeoutException
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.remote.webelement import WebElement

from response_ready_strategy import ResponseReadyStrategyFactory
from clipboard_utils import set_clipboard_text, get_clipboard_text

class MessageSender:
    """Отвечает за отправку сообщений и ожидание ответа."""

    def __init__(self, driver, logger, config):
        self.driver = driver
        self.logger = logger
        self.config = config

    def send_message(self, prompt: str) -> Optional[str]:
        """
        Отправляет сообщение, ожидает ответ и возвращает скопированный текст.
        Возвращает None при ошибке.
        """
        self.logger.log("📤 Отправка запроса в DeepSeek...")
        messages_before = self._find_assistant_messages()
        count_before = len(messages_before)
        self.logger.log(f"До отправки: {count_before} сообщений ассистента.")

        input_box = self._find_input_box()
        if not input_box:
            return None

        if not self._insert_text(input_box, prompt):
            return None

        if not self._send_message_via_enter_or_button(input_box):
            return None

        # Ждём новое сообщение
        new_message = self._wait_for_new_message(count_before, self.config.selenium_timeout)
        if not new_message:
            return None

        # Ждём готовности ответа
        ready = self._wait_for_response_ready(new_message, self.config.stable_timeout)
        if not ready:
            self.logger.log("⚠️ Ответ не подтверждён как готовый, но попытаемся скопировать.", "WARNING")

        # 1. Копирование через кнопку
        full_text = self._copy_response_via_button(new_message)
        if full_text:
            self.logger.log("✅ Ответ скопирован через буфер обмена.")
            return full_text

        # 2. Fallback: чтение через .text
        self.logger.log("⚠️ Не удалось скопировать через кнопку, используем .text", "WARNING")
        full_text = self._get_last_message_text()
        if full_text:
            self.logger.log("✅ Ответ получен через .text.")
            return full_text

        self.logger.log("❌ Не удалось получить текст ответа.", "ERROR")
        return None

    def _find_assistant_messages(self):
        try:
            return self.driver.find_elements(By.XPATH, "//div[contains(@class, 'message') and contains(@class, 'assistant')]")
        except Exception as e:
            self.logger.log(f"Ошибка поиска сообщений: {e}", "ERROR")
            return []

    def _find_input_box(self):
        from element_finder import ElementFinder
        finder = ElementFinder(self.driver, self.logger)
        return finder.find_input_box()

    def _insert_text(self, input_box: WebElement, text: str) -> bool:
        """Вставляет текст через буфер обмена."""
        self.logger.log("📋 Вставка текста через буфер обмена...")
        try:
            if not set_clipboard_text(text):
                self.logger.log("❌ Не удалось записать в буфер обмена.", "ERROR")
                return False

            input_box.click()
            input_box.clear()
            time.sleep(0.2)
            ActionChains(self.driver).key_down(Keys.CONTROL).send_keys('v').key_up(Keys.CONTROL).perform()
            time.sleep(0.5)

            inserted = self.driver.execute_script("return arguments[0].value;", input_box)
            if inserted and len(inserted) >= len(text) // 2:
                self.logger.log(f"✅ Текст вставлен (длина {len(inserted)} символов).")
                return True
            else:
                # fallback: send_keys
                self.logger.log("⚠️ Ctrl+V не сработал, пробуем send_keys.", "WARNING")
                input_box.clear()
                input_box.send_keys(text)
                inserted = self.driver.execute_script("return arguments[0].value;", input_box)
                if inserted:
                    self.logger.log(f"✅ Текст вставлен через send_keys (длина {len(inserted)}).")
                    return True
                else:
                    self.logger.log("❌ Не удалось вставить текст.", "ERROR")
                    return False
        except Exception as e:
            self.logger.log(f"❌ Ошибка вставки текста: {e}", "ERROR")
            return False

    def _send_message_via_enter_or_button(self, input_box: WebElement) -> bool:
        """Отправляет сообщение через Enter или кнопку."""
        max_attempts = 3
        for attempt in range(max_attempts):
            try:
                ActionChains(self.driver).send_keys(Keys.RETURN).perform()
                time.sleep(1)
                new_text = self.driver.execute_script("return arguments[0].value;", input_box)
                if new_text == "":
                    self.logger.log("✅ Поле очистилось, запрос принят.")
                    return True
                else:
                    self.logger.log("⚠️ Поле не очистилось после Enter.", "WARNING")
            except StaleElementReferenceException:
                self.logger.log(f"⚠️ StaleElementReferenceException, попытка {attempt+1}/{max_attempts}", "WARNING")
                input_box = self._find_input_box()
                if not input_box:
                    return False
                continue
            except Exception as e:
                self.logger.log(f"⚠️ Ошибка при Enter: {e}", "WARNING")

            # Запасной вариант: клик по кнопке
            self.logger.log("📤 Попытка клика по кнопке с ds-button--circle...")
            try:
                from element_finder import ElementFinder
                finder = ElementFinder(self.driver, self.logger)
                send_btn = finder.find_send_button()
                if send_btn:
                    send_btn.click()
                    time.sleep(1)
                    new_text = self.driver.execute_script("return arguments[0].value;", input_box)
                    if new_text == "":
                        self.logger.log("✅ Отправлено через кнопку.")
                        return True
                    else:
                        self.logger.log("⚠️ Поле не очистилось после клика.", "WARNING")
                else:
                    self.logger.log("❌ Не найдена кнопка отправки.", "ERROR")
            except Exception as e:
                self.logger.log(f"❌ Ошибка при клике: {e}", "ERROR")
        return False

    def _wait_for_new_message(self, old_count: int, timeout: int):
        self.logger.log(f"⏳ Ожидание появления нового сообщения (текущее кол-во: {old_count})...")
        start = time.time()
        last_log = start
        while time.time() - start < timeout:
            if time.time() - last_log >= 5:
                self.logger.log(f"🔍 Сообщений сейчас: {len(self._find_assistant_messages())}")
                last_log = time.time()

            messages = self._find_assistant_messages()
            if len(messages) > old_count:
                new_msg = messages[-1]
                self.logger.log(f"✅ Новое сообщение обнаружено! Всего: {len(messages)}.")
                return new_msg

            # Проверка ошибок
            try:
                errors = self.driver.find_elements(By.XPATH, "//div[contains(text(), 'error') or contains(text(), 'Error')]")
                if errors:
                    self.logger.log(f"⚠️ Найдены ошибки: {errors[0].text[:200]}", "WARNING")
            except:
                pass

            time.sleep(0.5)

        self.logger.log(f"❌ Таймаут ожидания нового сообщения ({timeout} сек).", "ERROR")
        return None

    def _wait_for_response_ready(self, message_element: WebElement, timeout: int) -> bool:
        self.logger.log(f"⏳ Ожидание готовности ответа (стратегия: {self.config.response_strategy})...")
        strategy = ResponseReadyStrategyFactory.get_strategy(
            self.config.response_strategy,
            logger=self.logger,
            check_interval=self.config.check_interval,
            stable_duration=self.config.stable_duration,
            debug_interval=2.0
        )
        ready, reason = strategy.wait(self.driver, message_element, timeout)
        if ready:
            self.logger.log(f"✅ Ответ готов (триггер: {reason}).")
        else:
            self.logger.log(f"⚠️ Стратегия не подтвердила готовность за {timeout} сек. Причина: {reason}", "WARNING")
        return ready

    def _copy_response_via_button(self, message_element: WebElement) -> Optional[str]:
        """Копирует ответ через кнопку Копировать."""
        from element_finder import ElementFinder
        finder = ElementFinder(self.driver, self.logger)

        # Наводим курсор, чтобы активировать панель
        try:
            ActionChains(self.driver).move_to_element(message_element).perform()
            time.sleep(0.3)
        except Exception as e:
            self.logger.log(f"Ошибка наведения: {e}", "WARNING")

        copy_btn = finder.find_copy_button_in_message(message_element)
        if not copy_btn:
            self.logger.log("❌ Кнопка копирования не найдена.", "ERROR")
            return None

        if copy_btn.is_displayed() and copy_btn.is_enabled():
            self.logger.log("✅ Найдена кнопка Копировать.")
            self.driver.execute_script("arguments[0].scrollIntoView(true);", copy_btn)
            time.sleep(0.2)
            copy_btn.click()
            time.sleep(0.5)

            text = get_clipboard_text()
            if text:
                # Убираем лишние слова
                return self._clean_copied_text(text)
            else:
                self.logger.log("⚠️ Буфер обмена пуст после клика.", "WARNING")
                # пробуем кликнуть через JS
                try:
                    self.driver.execute_script("arguments[0].click();", copy_btn)
                    time.sleep(0.5)
                    text = get_clipboard_text()
                    if text:
                        return self._clean_copied_text(text)
                except Exception as e:
                    self.logger.log(f"❌ Повторный клик через JS не удался: {e}", "WARNING")
                return None
        else:
            self.logger.log("❌ Кнопка неактивна/невидима.", "ERROR")
            return None

    def _get_last_message_text(self) -> Optional[str]:
        messages = self._find_assistant_messages()
        if not messages:
            return None
        last = messages[-1]
        return last.text.strip()

    def _clean_copied_text(self, text: str) -> str:
        """Удаляет строки с 'Копировать', 'Скачать' и т.п."""
        lines = text.splitlines()
        cleaned = []
        for line in lines:
            stripped = line.strip()
            if stripped in ("Копировать", "Скачать", "python", "bash", "cmd"):
                continue
            cleaned.append(line)
        return "\n".join(cleaned)