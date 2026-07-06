# selenium_client.py
import time
from typing import Optional, List

from selenium import webdriver
from selenium.webdriver.edge.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.action_chains import ActionChains
from selenium.common.exceptions import TimeoutException, StaleElementReferenceException, ElementClickInterceptedException
from selenium.webdriver.remote.webelement import WebElement

from response_ready_strategy import ResponseReadyStrategyFactory
from clipboard_manager import ClipboardManager
from message_finder import MessageFinder
from response_copier import ResponseCopier


class SeleniumDeepSeekClient:
    def __init__(self, logger, config):
        self.logger = logger
        self.config = config
        self.driver = None
        self.clipboard = ClipboardManager()
        self.message_finder = None
        self.response_copier = None
        self._connect()

    def _connect(self):
        options = Options()
        options.add_experimental_option("debuggerAddress", f"127.0.0.1:{self.config.debug_port}")
        try:
            self.driver = webdriver.Edge(options=options)
        except Exception as e:
            self.logger.log(f"Не удалось подключиться к браузеру: {e}", "ERROR")
            raise

        # Переключаемся на вкладку DeepSeek
        found = False
        for handle in self.driver.window_handles:
            self.driver.switch_to.window(handle)
            current_url = self.driver.current_url
            if "chat.deepseek.com" in current_url:
                found = True
                self.logger.log(f"✅ Найдена вкладка DeepSeek: {current_url}")
                break

        if not found:
            self.logger.log("⚠️ Вкладка DeepSeek не найдена, открываем новую...")
            self.driver.execute_script("window.open('');")
            self.driver.switch_to.window(self.driver.window_handles[-1])
            self.driver.get(self.config.deepseek_url)
            self.logger.log(f"✅ Открыта новая вкладка: {self.driver.current_url}")

        self.driver.execute_script("window.focus();")

        try:
            WebDriverWait(self.driver, 15).until(EC.presence_of_element_located((By.TAG_NAME, "body")))
        except TimeoutException:
            self.logger.log("Страница не загрузилась за 15 секунд.", "ERROR")
            self.driver.quit()
            raise

        self.logger.log(f"✅ Подключено к браузеру. Текущий URL: {self.driver.current_url}")

        # Инициализация вспомогательных классов
        self.message_finder = MessageFinder(self.driver, self.config, logger=self.logger)
        self.response_copier = ResponseCopier(self.driver, self.config, logger=self.logger)

    def _get_assistant_messages(self) -> List[WebElement]:
        return self.message_finder.get_assistant_messages()

    def _get_last_assistant_message(self) -> Optional[WebElement]:
        return self.message_finder.get_last_assistant_message()

    def _wait_for_input_box(self, timeout=15) -> Optional[WebElement]:
        self.logger.log(f"⏳ Ожидание поля ввода (селектор: {self.config.selectors['input_textarea']})...")
        try:
            input_box = WebDriverWait(self.driver, timeout).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, self.config.selectors["input_textarea"]))
            )
            self.driver.execute_script("arguments[0].scrollIntoView(true);", input_box)
            self.logger.log("✅ Поле ввода найдено.")
            return input_box
        except TimeoutException:
            self.logger.log("❌ Таймаут ожидания поля ввода.", "ERROR")
            return None

    def _set_clipboard(self, text):
        self.clipboard.set_text(text)

    def _insert_text(self, input_box: WebElement, message: str) -> bool:
        self.logger.log("📋 Вставка текста через буфер обмена...")
        try:
            self._set_clipboard(message)
            input_box.click()
            input_box.clear()
            time.sleep(0.2)
            ActionChains(self.driver).key_down(Keys.CONTROL).send_keys('v').key_up(Keys.CONTROL).perform()
            time.sleep(0.5)

            inserted = self.driver.execute_script("return arguments[0].value;", input_box)
            if inserted and len(inserted) >= len(message) // 2:
                self.logger.log(f"✅ Текст вставлен (длина {len(inserted)} символов).")
                return True
            else:
                self.logger.log("⚠️ Вставка через Ctrl+V не сработала, пробуем send_keys.", "WARNING")
                input_box.clear()
                input_box.send_keys(message)
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

    def _send_message(self, input_box: WebElement) -> bool:
        max_attempts = 3
        for attempt in range(max_attempts):
            try:
                self.logger.log("📤 Отправка через Enter...")
                ActionChains(self.driver).send_keys(Keys.RETURN).perform()
                time.sleep(1)
                new_text = self.driver.execute_script("return arguments[0].value;", input_box)
                if new_text == "":
                    self.logger.log("✅ Поле очистилось, запрос принят.")
                    return True
                else:
                    self.logger.log("⚠️ Поле не очистилось после Enter.", "WARNING")
            except StaleElementReferenceException:
                self.logger.log(f"⚠️ StaleElementReferenceException при отправке, попытка {attempt+1}/{max_attempts}...", "WARNING")
                input_box = self._wait_for_input_box()
                if not input_box:
                    return False
                continue
            except Exception as e:
                self.logger.log(f"⚠️ Ошибка при Enter: {e}", "WARNING")

            # Запасной вариант: клик по кнопке
            self.logger.log("📤 Попытка клика по кнопке с ds-button--circle...")
            try:
                buttons = self.driver.find_elements(By.CSS_SELECTOR, "div[role='button']")
                for btn in buttons:
                    classes = btn.get_attribute("class") or ""
                    if "ds-button--circle" in classes:
                        btn.click()
                        self.logger.log("✅ Клик по кнопке с ds-button--circle.")
                        time.sleep(1)
                        new_text = self.driver.execute_script("return arguments[0].value;", input_box)
                        if new_text == "":
                            return True
                        else:
                            self.logger.log("⚠️ Поле не очистилось после клика, повторная попытка...", "WARNING")
                            btn.click()
                            time.sleep(1)
                            new_text = self.driver.execute_script("return arguments[0].value;", input_box)
                            if new_text == "":
                                return True
                self.logger.log("❌ Не найден подходящий элемент с ds-button--circle.", "ERROR")
            except StaleElementReferenceException:
                self.logger.log(f"⚠️ StaleElementReferenceException при клике, попытка {attempt+1}/{max_attempts}...", "WARNING")
                input_box = self._wait_for_input_box()
                if not input_box:
                    return False
                continue
            except Exception as e:
                self.logger.log(f"❌ Ошибка при поиске кнопки: {e}", "ERROR")
                return False

        self.logger.log("❌ Не удалось отправить сообщение после нескольких попыток.", "ERROR")
        return False

    def _get_send_button_state(self) -> str:
        try:
            buttons = self.driver.find_elements(By.CSS_SELECTOR, "div[role='button']")
            for btn in buttons:
                classes = btn.get_attribute("class") or ""
                if "ds-button--circle" in classes:
                    disabled = "ds-button--disabled" in classes
                    return "disabled" if disabled else "enabled"
            return "not found"
        except Exception as e:
            return f"error: {e}"

    def _wait_for_response_ready(self, message_element: Optional[WebElement], timeout: int) -> bool:
        self.logger.log(f"⏳ Ожидание готовности ответа (стратегия: {self.config.response_strategy})...")
        strategy = ResponseReadyStrategyFactory.get_strategy(
            self.config.response_strategy,
            driver=self.driver,
            config=self.config,
            logger=self.logger,
            check_interval=self.config.check_interval,
            stable_duration=self.config.stable_duration,
            debug_interval=2.0
        )
        ready, reason = strategy.wait(self.driver, message_element, timeout)
        if ready:
            self.logger.log(f"✅ Ответ готов (триггер: {reason}).")
        else:
            self.logger.log(f"⚠️ Стратегия не подтвердила готовность ответа за {timeout} сек. Причина: {reason}",
                            "WARNING")
        return ready

    def _get_last_message_text(self, fallback_retries=2) -> Optional[str]:
        for attempt in range(fallback_retries):
            try:
                messages = self._get_assistant_messages()
                if not messages:
                    self.logger.log("❌ Нет сообщений ассистента.", "ERROR")
                    return None
                last = messages[-1]
                text = last.text.strip()
                if text:
                    self.logger.log(f"✅ Текст получен (длина {len(text)} символов).")
                    return text
                else:
                    self.logger.log("⚠️ Текст пустой, повторная попытка...", "WARNING")
                    time.sleep(0.5)
            except StaleElementReferenceException:
                self.logger.log("⚠️ Элемент устарел, повторная попытка...", "WARNING")
                time.sleep(0.5)
        self.logger.log("❌ Не удалось получить текст сообщения.", "ERROR")
        return None

    def send_message(self, message: str) -> Optional[str]:
        self.logger.log("📤 Отправка запроса в DeepSeek...")
        strategy = self.config.response_strategy

        # =============== Стратегия panel_count ===============
        if strategy == "panel_count":
            input_box = self._wait_for_input_box()
            if not input_box:
                return None
            if not self._insert_text(input_box, message):
                return None
            if not self._send_message(input_box):
                return None

            # Ждём готовности ответа (panel_count отслеживает увеличение панелей)
            ready = self._wait_for_response_ready(None, self.config.stable_timeout)
            if not ready:
                self.logger.log("⚠️ Ответ не готов по стратегии panel_count, но попытаемся скопировать.", "WARNING")

            # Небольшая пауза для появления сообщения в DOM (обычно достаточно 1-2 сек)
            time.sleep(2)

            # Берём последнее сообщение
            latest_message = self._get_last_assistant_message()
            if not latest_message:
                self.logger.log("❌ Нет сообщений ассистента.", "ERROR")
                return None

            # Копируем ответ через универсальный копировщик
            full_text = self.response_copier.copy_from_element(latest_message)
            if full_text:
                self.logger.log("✅ Ответ скопирован через буфер обмена.")
                return full_text

            # Fallback: .text
            self.logger.log("⚠️ Не удалось скопировать через кнопку, используем .text", "WARNING")
            full_text = self._get_last_message_text()
            if full_text:
                self.logger.log("✅ Ответ получен через .text.")
                return full_text
            else:
                self.logger.log("❌ Не удалось получить текст ответа.", "ERROR")
                return None

        # =============== Другие стратегии ===============
        else:
            messages_before = self._get_assistant_messages()
            count_before = len(messages_before)
            self.logger.log(f"До отправки: {count_before} сообщений ассистента.")

            input_box = self._wait_for_input_box()
            if not input_box:
                return None
            if not self._insert_text(input_box, message):
                return None
            if not self._send_message(input_box):
                return None

            # Ждём появление нового сообщения
            new_message = self._wait_for_new_message(count_before, self.config.selenium_timeout)
            if not new_message:
                return None

            # Ждём готовности (стратегия)
            ready = self._wait_for_response_ready(new_message, self.config.stable_timeout)
            if not ready:
                self.logger.log("⚠️ Ответ не подтверждён как готовый, но попытаемся скопировать.", "WARNING")

            # Обновляем ссылку на сообщение
            latest_message = self._get_last_assistant_message()
            if latest_message and latest_message.id != new_message.id:
                self.logger.log("🔄 Обновлена ссылка на последнее сообщение.")
                new_message = latest_message

            # Копирование через кнопку
            full_text = self.response_copier.copy_from_element(new_message)
            if full_text:
                self.logger.log("✅ Ответ скопирован через буфер обмена.")
                return full_text

            # Fallback: .text
            self.logger.log("⚠️ Не удалось скопировать через кнопку, используем .text", "WARNING")
            full_text = self._get_last_message_text()
            if full_text:
                self.logger.log("✅ Ответ получен через .text.")
                return full_text
            else:
                self.logger.log("❌ Не удалось получить текст ответа.", "ERROR")
                return None

    def _wait_for_new_message(self, old_count: int, timeout: int) -> Optional[WebElement]:
        """Ожидает появления нового сообщения ассистента (используется только для не-panel_count стратегий)."""
        self.logger.log(f"⏳ Ожидание появления нового сообщения (текущее кол-во: {old_count})...")
        start = time.time()
        last_log_time = start
        last_count = old_count
        send_button_disabled = False

        while time.time() - start < timeout:
            if time.time() - last_log_time >= 2:
                btn_state = self._get_send_button_state()
                if btn_state == "disabled" and not send_button_disabled:
                    send_button_disabled = True
                    self.logger.log("🔍 Генерация начата (кнопка отправки disabled)")
                elif btn_state == "enabled" and send_button_disabled:
                    send_button_disabled = False
                    self.logger.log("🔍 Генерация завершена (кнопка отправки enabled)")
                last_log_time = time.time()

            messages = self._get_assistant_messages()
            current_count = len(messages)
            if current_count > old_count:
                new_message = messages[-1]
                self.logger.log(f"✅ Новое сообщение обнаружено! Всего сообщений: {current_count}.")
                return new_message

            if current_count != last_count:
                self.logger.log(f"🔍 Сообщений ассистента сейчас: {current_count}")
                last_count = current_count

            try:
                error_elements = self.driver.find_elements(By.XPATH,
                                                           "//div[contains(text(), 'error') or contains(text(), 'Error')]")
                if error_elements:
                    self.logger.log(f"⚠️ Найдены элементы с ошибкой: {error_elements[0].text[:200]}", "WARNING")
            except:
                pass

            time.sleep(1.0)

        self.logger.log(f"❌ Таймаут: новое сообщение не появилось за {timeout} сек.", "ERROR")
        return None

    def new_chat(self):
        self.logger.log("🔄 Создание нового чата (заглушка) ...")
        return True

    def copy_last_response(self):
        self.logger.log("📋 Копирование последнего ответа...")
        try:
            messages = self._get_assistant_messages()
            if not messages:
                self.logger.log("❌ Нет сообщений ассистента.", "ERROR")
                return None
            last = messages[-1]
            return last.text.strip()
        except Exception as e:
            self.logger.log(f"❌ Не удалось получить последний ответ: {e}", "ERROR")
            return None

    def close(self):
        if self.driver:
            self.driver.quit()