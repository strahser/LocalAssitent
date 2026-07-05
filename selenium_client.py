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
from selenium.common.exceptions import (
    TimeoutException,
    StaleElementReferenceException,
    NoSuchElementException
)
from selenium.webdriver.remote.webelement import WebElement  # <-- добавлен импорт

from selectors import SELECTORS
from response_ready_strategy import ResponseReadyStrategyFactory


class SeleniumDeepSeekClient:
    """
    Клиент для управления браузером через Selenium и взаимодействия с DeepSeek.
    """

    def __init__(self, logger, config):
        self.logger = logger
        self.config = config
        self.driver = None
        self._connect()

        # Дополнительные селекторы для кнопки копирования (на случай, если основной не работает)
        self.copy_button_selectors = [
            self.config.selectors.get("copy_button", "span.ds-button__content span.code-info-button-text"),
            "button[aria-label*='Copy' i]",
            "span[class*='copy']",
            "button[class*='copy']",
            "div[class*='copy']",
        ]

    def _connect(self):
        """Подключается к уже запущенному браузеру с отладкой."""
        options = Options()
        options.add_experimental_option("debuggerAddress", f"127.0.0.1:{self.config.debug_port}")
        try:
            self.driver = webdriver.Edge(options=options)
        except Exception as e:
            self.logger.log(f"Не удалось подключиться к браузеру: {e}", "ERROR")
            raise

        if self.driver.window_handles:
            self.driver.switch_to.window(self.driver.window_handles[0])
        self.driver.execute_script("window.focus();")

        try:
            WebDriverWait(self.driver, 15).until(EC.presence_of_element_located((By.TAG_NAME, "body")))
        except TimeoutException:
            self.logger.log("Страница не загрузилась за 15 секунд.", "ERROR")
            self.driver.quit()
            raise

        self.logger.log(f"✅ Подключено к браузеру. Текущий URL: {self.driver.current_url}")

    def _set_clipboard(self, text):
        """Устанавливает текст в буфер обмена Windows через PowerShell."""
        escaped = text.replace('"', '\\"').replace('`', '``')
        ps_command = f'Set-Clipboard -Value "{escaped}"'
        subprocess.run(["powershell", "-Command", ps_command], check=True)

    def _get_assistant_messages(self) -> List[WebElement]:
        """Возвращает список элементов сообщений ассистента в текущей вкладке."""
        try:
            return self.driver.find_elements(By.XPATH, self.config.selectors["assistant_messages"])
        except Exception as e:
            self.logger.log(f"Ошибка при поиске сообщений: {e}", "ERROR")
            return []

    def _find_elements_by_selectors(self, selectors: List[str], by=By.CSS_SELECTOR) -> List[WebElement]:
        """
        Ищет элементы по списку селекторов (CSS или XPath).
        Возвращает первый найденный набор элементов (непустой).
        """
        for selector in selectors:
            try:
                elements = self.driver.find_elements(by, selector)
                if elements:
                    self.logger.log(f"🔍 Найдено {len(elements)} элементов по селектору: {selector}")
                    return elements
                else:
                    self.logger.log(f"🔍 Нет элементов по селектору: {selector}")
            except Exception as e:
                self.logger.log(f"Ошибка при поиске по селектору {selector}: {e}", "WARNING")
        return []

    def _wait_for_input_box(self, timeout=15) -> Optional[WebElement]:
        """Ожидает появления поля ввода и возвращает его."""
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
        """Вставляет текст в поле ввода через буфер обмена или send_keys."""
        self.logger.log("📋 Вставка текста через буфер обмена...")
        try:
            self._set_clipboard(message)
            input_box.click()
            input_box.clear()
            time.sleep(0.2)
            ActionChains(self.driver).key_down(Keys.CONTROL).send_keys('v').key_up(Keys.CONTROL).perform()
            time.sleep(0.5)

            # Проверяем, что текст вставлен
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

    def _send_message(self) -> bool:
        """Отправляет сообщение (клик по кнопке или Enter)."""
        send_selector = self.config.selectors.get("send_button", "button[type='submit']")
        self.logger.log(f"📤 Отправка сообщения (селектор: {send_selector})...")
        try:
            # Пробуем найти кнопку отправки
            send_button = self.driver.find_element(By.CSS_SELECTOR, send_selector)
            if send_button.is_enabled():
                send_button.click()
                self.logger.log("✅ Отправлено кликом по кнопке.")
                return True
            else:
                self.logger.log("⚠️ Кнопка отправки не активна, пробуем Enter.", "WARNING")
        except NoSuchElementException:
            self.logger.log("⚠️ Кнопка отправки не найдена, пробуем Enter.", "WARNING")
        except Exception as e:
            self.logger.log(f"⚠️ Ошибка при клике по кнопке: {e}, пробуем Enter.", "WARNING")

        # Запасной вариант – нажать Enter
        try:
            ActionChains(self.driver).send_keys(Keys.RETURN).perform()
            self.logger.log("✅ Отправлено через Enter.")
            return True
        except Exception as e:
            self.logger.log(f"❌ Не удалось отправить сообщение: {e}", "ERROR")
            return False

    def _wait_for_new_message(self, old_count: int, timeout: int) -> Optional[WebElement]:
        """
        Ожидает появления нового сообщения ассистента.
        Возвращает элемент нового сообщения или None при таймауте.
        """
        self.logger.log(f"⏳ Ожидание появления нового сообщения (текущее кол-во: {old_count})...")
        start = time.time()
        while time.time() - start < timeout:
            messages = self._get_assistant_messages()
            if len(messages) > old_count:
                new_message = messages[-1]
                self.logger.log(f"✅ Новое сообщение обнаружено! Всего сообщений: {len(messages)}.")
                return new_message
            time.sleep(0.5)
        self.logger.log(f"❌ Таймаут: новое сообщение не появилось за {timeout} сек.", "ERROR")
        return None

    def _wait_for_response_ready(self, message_element: WebElement, timeout: int) -> bool:
        """
        Применяет стратегию готовности к последнему сообщению.
        Возвращает True, если ответ готов, иначе False.
        """
        self.logger.log(f"⏳ Ожидание готовности ответа (стратегия: {self.config.response_strategy})...")
        strategy = ResponseReadyStrategyFactory.get_strategy(
            self.config.response_strategy,
            check_interval=self.config.check_interval,
            stable_duration=self.config.stable_duration
        )
        ready = strategy.wait(self.driver, message_element, timeout)
        if ready:
            self.logger.log("✅ Ответ готов.")
        else:
            self.logger.log(f"⚠️ Стратегия не подтвердила готовность ответа за {timeout} сек.", "WARNING")
        return ready

    def _get_last_message_text(self, fallback_retries=2) -> Optional[str]:
        """Получает текст последнего сообщения ассистента с повторными попытками."""
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
        """Логирует количество найденных кнопок копирования по всем селекторам."""
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
        """Отправляет сообщение и возвращает ответ."""
        self.logger.log("📤 Отправка запроса в DeepSeek...")
        # Логируем состояние до отправки
        messages_before = self._get_assistant_messages()
        count_before = len(messages_before)
        self.logger.log(f"До отправки: {count_before} сообщений ассистента.")
        self._log_copy_buttons_count("До отправки:")

        # Шаг 1: Ожидание поля ввода
        input_box = self._wait_for_input_box()
        if not input_box:
            return None

        # Шаг 2: Вставка текста
        if not self._insert_text(input_box, message):
            return None

        # Шаг 3: Отправка
        if not self._send_message():
            return None

        # Шаг 4: Ожидание нового сообщения
        new_message = self._wait_for_new_message(count_before, self.config.selenium_timeout)
        if not new_message:
            return None

        # Шаг 5: Ожидание готовности ответа
        ready = self._wait_for_response_ready(new_message, self.config.stable_timeout)
        if not ready:
            self.logger.log("⚠️ Ответ не подтверждён как готовый, но попытаемся получить текст.", "WARNING")

        # Шаг 6: Получение текста
        full_text = self._get_last_message_text()
        if full_text:
            self.logger.log("✅ Ответ получен.")
            return full_text
        else:
            self.logger.log("❌ Не удалось получить текст ответа.", "ERROR")
            return None

    def new_chat(self):
        """Создаёт новый чат в текущей вкладке."""
        self.logger.log("🔄 Создание нового чата...")
        try:
            new_chat_btn = WebDriverWait(self.driver, 10).until(
                EC.element_to_be_clickable((By.XPATH, self.config.selectors["new_chat_xpath"]))
            )
            new_chat_btn.click()
            WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, self.config.selectors["input_textarea"]))
            )
            self.logger.log("✅ Новый чат создан.")
            return True
        except Exception as e:
            self.logger.log(f"❌ Не удалось создать новый чат: {e}", "ERROR")
            return False

    def copy_last_response(self):
        """Возвращает последний ответ ассистента."""
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
        """Закрывает драйвер."""
        if self.driver:
            self.driver.quit()