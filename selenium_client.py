# selenium_client.py
import subprocess
import time
from typing import List, Optional

from selenium import webdriver
from selenium.webdriver.edge.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.action_chains import ActionChains
from selenium.common.exceptions import TimeoutException, StaleElementReferenceException, NoSuchElementException
from selenium.webdriver.remote.webelement import WebElement

from selectors import SELECTORS
from response_ready_strategy import ResponseReadyStrategyFactory


class SeleniumDeepSeekClient:
    def __init__(self, logger, config):
        self.logger = logger
        self.config = config
        self.driver = None
        self._connect()

        self.copy_button_selectors = [
            self.config.selectors.get("copy_button", "span.ds-button__content span.code-info-button-text")
        ]

    def _connect(self):
        options = Options()
        options.add_experimental_option("debuggerAddress", f"127.0.0.1:{self.config.debug_port}")
        try:
            self.driver = webdriver.Edge(options=options)
        except Exception as e:
            self.logger.log(f"Не удалось подключиться к браузеру: {e}", "ERROR")
            raise

        # Ищем вкладку с DeepSeek
        target_url = self.config.deepseek_url
        found = False
        for handle in self.driver.window_handles:
            self.driver.switch_to.window(handle)
            current_url = self.driver.current_url
            if "chat.deepseek.com" in current_url:
                found = True
                self.logger.log(f"✅ Найдена вкладка DeepSeek: {current_url}")
                break

        if not found:
            # Открываем новую вкладку с нужным URL
            self.logger.log("⚠️ Вкладка DeepSeek не найдена, открываем новую...")
            self.driver.execute_script("window.open('');")
            self.driver.switch_to.window(self.driver.window_handles[-1])
            self.driver.get(self.config.deepseek_url)
            self.logger.log(f"✅ Открыта новая вкладка: {self.driver.current_url}")

        # Фокусируемся на окне
        self.driver.execute_script("window.focus();")

        # Ждём загрузки страницы
        try:
            WebDriverWait(self.driver, 15).until(EC.presence_of_element_located((By.TAG_NAME, "body")))
        except TimeoutException:
            self.logger.log("Страница не загрузилась за 15 секунд.", "ERROR")
            self.driver.quit()
            raise

        self.logger.log(f"✅ Подключено к браузеру. Текущий URL: {self.driver.current_url}")

    def _set_clipboard(self, text):
        escaped = text.replace('"', '\\"').replace('`', '``')
        ps_command = f'Set-Clipboard -Value "{escaped}"'
        subprocess.run(["powershell", "-Command", ps_command], check=True)

    def _get_assistant_messages(self) -> List[WebElement]:
        try:
            return self.driver.find_elements(By.XPATH, self.config.selectors["assistant_messages"])
        except Exception as e:
            self.logger.log(f"Ошибка при поиске сообщений: {e}", "ERROR")
            return []

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
        """
        Отправляет сообщение. При ошибке StaleElementReferenceException обновляет input_box и повторяет.
        """
        max_attempts = 3
        for attempt in range(max_attempts):
            try:
                # Пытаемся отправить через Enter
                current_text = self.driver.execute_script("return arguments[0].value;", input_box)
                self.logger.log("📤 Отправка через Enter...")
                ActionChains(self.driver).send_keys(Keys.RETURN).perform()
                time.sleep(1)
                # Проверяем очистку
                new_text = self.driver.execute_script("return arguments[0].value;", input_box)
                if new_text == "":
                    self.logger.log("✅ Поле очистилось, запрос принят.")
                    return True
                else:
                    self.logger.log("⚠️ Поле не очистилось после Enter.", "WARNING")
            except StaleElementReferenceException:
                self.logger.log(f"⚠️ StaleElementReferenceException при отправке, попытка {attempt+1}/{max_attempts}...", "WARNING")
                # Обновляем input_box
                input_box = self._wait_for_input_box()
                if not input_box:
                    return False
                continue
            except Exception as e:
                self.logger.log(f"⚠️ Ошибка при Enter: {e}", "WARNING")
                # пробуем кликнуть по кнопке

            # Запасной вариант: клик по кнопке с ds-button--circle
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
                            # пробуем ещё раз кликнуть
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

    def _wait_for_new_message(self, old_count: int, timeout: int) -> Optional[WebElement]:
        self.logger.log(f"⏳ Ожидание появления нового сообщения (текущее кол-во: {old_count})...")
        start = time.time()
        last_log_time = start
        while time.time() - start < timeout:
            # Логируем состояние кнопки отправки и количество сообщений каждые 5 секунд
            if time.time() - last_log_time >= 5:
                btn_state = self._get_send_button_state()
                self.logger.log(f"🔍 Состояние кнопки отправки: {btn_state}")
                messages = self._get_assistant_messages()
                self.logger.log(f"🔍 Сообщений ассистента сейчас: {len(messages)}")
                last_log_time = time.time()

            messages = self._get_assistant_messages()
            if len(messages) > old_count:
                new_message = messages[-1]
                self.logger.log(f"✅ Новое сообщение обнаружено! Всего сообщений: {len(messages)}.")
                return new_message

            # Проверяем, не появились ли ошибки (например, "Something went wrong")
            try:
                error_elements = self.driver.find_elements(By.XPATH,
                                                           "//div[contains(text(), 'error') or contains(text(), 'Error')]")
                if error_elements:
                    self.logger.log(f"⚠️ Найдены элементы с ошибкой: {error_elements[0].text[:200]}", "WARNING")
            except:
                pass

            time.sleep(0.5)

        self.logger.log(f"❌ Таймаут: новое сообщение не появилось за {timeout} сек.", "ERROR")
        return None

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

    def _log_copy_buttons_count(self, prefix: str = ""):
        for selector in self.copy_button_selectors:
            try:
                elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                if elements:
                    self.logger.log(f"{prefix} Найдено {len(elements)} кнопок 'Копировать' по селектору: {selector}")
                else:
                    self.logger.log(f"{prefix} Нет кнопок 'Копировать' по селектору: {selector}")
            except Exception:
                pass

    def send_message(self, message: str) -> Optional[str]:
        self.logger.log("📤 Отправка запроса в DeepSeek...")
        messages_before = self._get_assistant_messages()
        count_before = len(messages_before)
        self.logger.log(f"До отправки: {count_before} сообщений ассистента.")
        self._log_copy_buttons_count("До отправки:")

        input_box = self._wait_for_input_box()
        if not input_box:
            return None

        if not self._insert_text(input_box, message):
            return None

        if not self._send_message(input_box):
            return None

        # Ждём новое сообщение
        new_message = self._wait_for_new_message(count_before, self.config.selenium_timeout)
        if not new_message:
            return None

        # Ждём готовности
        ready = self._wait_for_response_ready(new_message, self.config.stable_timeout)
        if not ready:
            self.logger.log("⚠️ Ответ не подтверждён как готовый, но попытаемся получить текст.", "WARNING")

        full_text = self._get_last_message_text()
        if full_text:
            self.logger.log("✅ Ответ получен.")
            return full_text
        else:
            self.logger.log("❌ Не удалось получить текст ответа.", "ERROR")
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