"""
ResponseReader - отвечает за ожидание и извлечение ответов.
"""
import time
from typing import List, Optional

from selenium.common.exceptions import StaleElementReferenceException
from selenium.webdriver.common.by import By
from selenium.webdriver.remote.webdriver import WebDriver
from selenium.webdriver.remote.webelement import WebElement

from agent.clipboard import ClipboardManager
from detection.element_finder import ElementFinder
from detection.response_ready import ResponseReadyStrategyFactory


class ResponseReader:
    def __init__(self, driver: WebDriver, logger, config, element_finder: ElementFinder,
                 clipboard: ClipboardManager):
        self.driver = driver
        self.logger = logger
        self.config = config
        self.finder = element_finder
        self.clipboard = clipboard

    def get_assistant_messages(self) -> List[WebElement]:
        return self.finder.find_assistant_messages()

    def wait_for_new_message(self, old_count: int, timeout: int) -> Optional[WebElement]:
        self.logger.log(f"⏳ Ожидание нового сообщения (текущее: {old_count})...")
        start = time.time()
        last_log_time = start

        while time.time() - start < timeout:
            if time.time() - last_log_time >= 5:
                self.logger.log(f"🔍 Сообщений: {len(self.get_assistant_messages())}")
                last_log_time = time.time()

            messages = self.get_assistant_messages()
            if len(messages) > old_count:
                self.logger.log(f"✅ Новое сообщение! Всего: {len(messages)}.")
                return messages[-1]

            try:
                errors = self.finder.find_error_elements()
                if errors:
                    self.logger.log(f"⚠️ Ошибка на странице: {errors[0].text[:200]}", "WARNING")
            except Exception:
                pass

            time.sleep(0.5)

        self.logger.log(f"❌ Таймаут ожидания нового сообщения ({timeout} сек).", "ERROR")
        return None

    def wait_ready(self, message_element: WebElement, timeout: int) -> bool:
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
            self.logger.log(f"⚠️ Стратегия не подтвердила готовность за {timeout} сек.", "WARNING")
        return ready

    def get_full_text(self, message_element: WebElement) -> Optional[str]:
        full_text = self._copy_response_via_button(message_element)
        if full_text:
            self.logger.log(f"✅ Текст ответа скопирован через буфер обмена.")
            return full_text

        self.logger.log("⚠️ Не удалось скопировать через кнопку, используем .text", "WARNING")
        return self._get_last_message_text()

    def get_code_from_message(self, message_element: WebElement) -> Optional[str]:
        return self._copy_last_code_block(message_element)

    def _get_last_message_text(self, fallback_retries: int = 2) -> Optional[str]:
        for attempt in range(fallback_retries):
            try:
                messages = self.get_assistant_messages()
                if not messages:
                    self.logger.log("❌ Нет сообщений ассистента.", "ERROR")
                    return None
                text = messages[-1].text.strip()
                if text:
                    self.logger.log(f"✅ Текст получен (длина {len(text)} символов).")
                    return text
                else:
                    self.logger.log("⚠️ Текст пустой, повтор...", "WARNING")
                    time.sleep(0.5)
            except StaleElementReferenceException:
                self.logger.log("⚠️ Элемент устарел, повтор...", "WARNING")
                time.sleep(0.5)
        self.logger.log("❌ Не удалось получить текст сообщения.", "ERROR")
        return None

    def _copy_response_via_button(self, message_element: WebElement) -> Optional[str]:
        self.logger.log("🔍 Поиск кнопки копирования сообщения...")
        try:
            from selenium.webdriver.common.action_chains import ActionChains
            ActionChains(self.driver).move_to_element(message_element).perform()
            time.sleep(0.3)
        except Exception as e:
            self.logger.log(f"Ошибка при наведении: {e}", "WARNING")

        copy_btn = self.finder.find_copy_button_in_message(message_element)
        if not copy_btn:
            self.logger.log("❌ Кнопка копирования сообщения не найдена.", "ERROR")
            return None

        if copy_btn.is_displayed() and copy_btn.is_enabled():
            self.logger.log("✅ Кнопка Копировать сообщения найдена и активна.")
            self.driver.execute_script("arguments[0].scrollIntoView(true);", copy_btn)
            time.sleep(0.2)
            copy_btn.click()
            time.sleep(0.5)

            clipboard_text = self.clipboard.get_text()
            if clipboard_text:
                return self._clean_copied_text(clipboard_text)
            else:
                self.logger.log("⚠️ Буфер пуст после клика, пробуем JS...", "WARNING")
                try:
                    self.driver.execute_script("arguments[0].click();", copy_btn)
                    time.sleep(0.5)
                    clipboard_text = self.clipboard.get_text()
                    if clipboard_text:
                        return self._clean_copied_text(clipboard_text)
                except Exception as e:
                    self.logger.log(f"❌ Повторный клик через JS не удался: {e}", "WARNING")
                return None
        else:
            self.logger.log("❌ Кнопка неактивна/невидима.", "ERROR")
            return None

    def _copy_last_code_block(self, message_element: WebElement) -> Optional[str]:
        code_blocks = self.finder.find_code_blocks(message_element)
        if not code_blocks:
            self.logger.log("⚠️ Блоки кода не найдены в сообщении.")
            return None

        last_block = code_blocks[-1]
        self.logger.log(f"🔍 Копирование последнего блока кода ({len(code_blocks)} всего)...")

        copy_btn = self.finder.find_code_copy_button(last_block)
        if copy_btn:
            self.logger.log("✅ Кнопка Copy в блоке кода найдена. Нажимаем...")
            try:
                from selenium.webdriver.common.action_chains import ActionChains
                ActionChains(self.driver).move_to_element(copy_btn).perform()
                time.sleep(0.2)
                self.driver.execute_script("arguments[0].scrollIntoView(true);", copy_btn)
                time.sleep(0.2)
                copy_btn.click()
                time.sleep(0.5)

                clipboard_text = self.clipboard.get_text()
                if clipboard_text:
                    self.logger.log(f"✅ Код скопирован через кнопку (длина {len(clipboard_text)}).")
                    return clipboard_text

                self.logger.log("⚠️ Буфер пуст после клика, пробуем JS-клик...", "WARNING")
                self.driver.execute_script("arguments[0].click();", copy_btn)
                time.sleep(0.5)
                clipboard_text = self.clipboard.get_text()
                if clipboard_text:
                    self.logger.log(f"✅ Код скопирован через JS-клик (длина {len(clipboard_text)}).")
                    return clipboard_text
            except Exception as e:
                self.logger.log(f"⚠️ Ошибка при клике по кнопке Copy: {e}", "WARNING")

        code_text = self.finder.get_code_text_from_pre(last_block)
        if code_text:
            self.logger.log(f"✅ Код прочитан из <pre> (длина {len(code_text)}).")
            return code_text

        self.logger.log("❌ Не удалось скопировать код ни одним способом.", "ERROR")
        return None

    def _clean_copied_text(self, text: str) -> str:
        lines = text.splitlines()
        cleaned = []
        for line in lines:
            stripped = line.strip()
            if stripped in ("Копировать", "Скачать", "Copy", "Download", "python", "bash", "cmd"):
                continue
            cleaned.append(line)
        return "\n".join(cleaned)
