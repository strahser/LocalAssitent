# selenium_client.py
import subprocess
import time
from selenium import webdriver
from selenium.common.exceptions import TimeoutException, StaleElementReferenceException
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.edge.options import Options
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

from response_ready_strategy import ResponseReadyStrategyFactory


class SeleniumDeepSeekClient:
    """
    Клиент для управления браузером через Selenium и взаимодействия с DeepSeek.
    """

    def __init__(self, logger, config):
        """
        :param logger: объект логгера (с методом log)
        :param config: объект с настройками (должен содержать атрибуты:
                       debug_port, edge_user_data_dir, deepseek_url,
                       selenium_timeout, stable_timeout, stable_duration,
                       check_interval, response_strategy,
                       selectors (словарь селекторов) )
        """
        self.logger = logger
        self.config = config
        self.driver = None
        self._connect()

    def _connect(self):
        """Подключается к уже запущенному браузеру с отладкой."""
        options = Options()
        options.add_experimental_option("debuggerAddress", f"127.0.0.1:{self.config.debug_port}")
        try:
            self.driver = webdriver.Edge(options=options)
        except Exception as e:
            self.logger.log(f"Не удалось подключиться к браузеру: {e}", "ERROR")
            raise

        # Переключаемся на первую вкладку и фокусируемся
        if self.driver.window_handles:
            self.driver.switch_to.window(self.driver.window_handles[0])
        self.driver.execute_script("window.focus();")

        # Ждём загрузки страницы
        try:
            WebDriverWait(self.driver, 15).until(EC.presence_of_element_located((By.TAG_NAME, "body")))
        except TimeoutException:
            self.logger.log("Страница не загрузилась за 15 секунд.", "ERROR")
            self.driver.quit()
            raise

    def _set_clipboard(self, text):
        """Устанавливает текст в буфер обмена Windows через PowerShell."""
        escaped = text.replace('"', '\\"').replace('`', '``')
        ps_command = f'Set-Clipboard -Value "{escaped}"'
        subprocess.run(["powershell", "-Command", ps_command], check=True)

    def _send_message_with_retries(self, message, max_retries=3):
        """Отправляет сообщение с повторными попытками при возникновении ошибок."""
        for attempt in range(max_retries):
            try:
                # Ждём поле ввода
                input_box = WebDriverWait(self.driver, 15).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, self.config.selectors["input_textarea"]))
                )
                self.driver.execute_script("arguments[0].scrollIntoView(true);", input_box)
                time.sleep(0.5)

                # Вставка через буфер обмена
                self._set_clipboard(message)
                input_box.click()
                input_box.clear()
                time.sleep(0.2)
                ActionChains(self.driver).key_down(Keys.CONTROL).send_keys('v').key_up(Keys.CONTROL).perform()
                time.sleep(0.5)

                # Проверка, что текст вставлен
                inserted = self.driver.execute_script("return arguments[0].value;", input_box)
                if not inserted or len(inserted) < len(message) // 2:
                    self.logger.log("WARNING: Вставка через Ctrl+V не сработала, пробуем send_keys.", "WARNING")
                    input_box.clear()
                    input_box.send_keys(message)

                # Запоминаем количество кнопок "Копировать" до отправки
                copy_buttons_before = self.driver.find_elements(By.CSS_SELECTOR, self.config.selectors["copy_button"])
                count_before = len(copy_buttons_before)

                # Отправляем
                send_selector = self.config.selectors.get("send_button", "button[type='submit']")
                try:
                    send_button = self.driver.find_element(By.CSS_SELECTOR, send_selector)
                    if send_button.is_enabled():
                        send_button.click()
                    else:
                        raise Exception("Send button not enabled")
                except:
                    ActionChains(self.driver).send_keys(Keys.RETURN).perform()

                # Ждём появления новой кнопки "Копировать" (индикатор, что ответ начал генерироваться)
                def copy_count_increased(driver):
                    current = driver.find_elements(By.CSS_SELECTOR, self.config.selectors["copy_button"])
                    return len(current) > count_before

                try:
                    WebDriverWait(self.driver, self.config.selenium_timeout).until(copy_count_increased)
                    self.logger.log("✅ Обнаружена кнопка 'Копировать' – ответ генерируется.")
                except TimeoutException:
                    self.logger.log("ERROR: Таймаут ожидания новой кнопки 'Копировать'.", "ERROR")
                    return None

                # Получаем последнее сообщение ассистента
                messages = self.driver.find_elements(By.XPATH, self.config.selectors["assistant_messages"])
                if not messages:
                    self.logger.log("ERROR: Не найдено сообщений ассистента.", "ERROR")
                    return None
                last_message = messages[-1]

                # Применяем стратегию ожидания готовности ответа
                strategy = ResponseReadyStrategyFactory.get_strategy(
                    self.config.response_strategy,
                    check_interval=self.config.check_interval,
                    stable_duration=self.config.stable_duration
                )
                if not strategy.wait(self.driver, last_message, self.config.stable_timeout):
                    self.logger.log("WARNING: Стратегия не подтвердила готовность ответа, но продолжаем.", "WARNING")

                # Получаем итоговый текст
                try:
                    full_text = last_message.text.strip()
                except StaleElementReferenceException:
                    # Обновляем ссылку на последнее сообщение
                    messages = self.driver.find_elements(By.XPATH, self.config.selectors["assistant_messages"])
                    if messages:
                        last_message = messages[-1]
                        full_text = last_message.text.strip()
                    else:
                        self.logger.log("ERROR: Не удалось получить текст ответа.", "ERROR")
                        return None

                if not full_text:
                    self.logger.log("ERROR: Текст ответа пуст.", "ERROR")
                    return None

                self.logger.log("✅ Ответ получен.")
                return full_text

            except StaleElementReferenceException as e:
                self.logger.log(f"⚠️ StaleElementReferenceException (попытка {attempt+1}/{max_retries}): {e}", "WARNING")
                time.sleep(1)
                continue
            except Exception as e:
                self.logger.log(f"⚠️ Ошибка (попытка {attempt+1}/{max_retries}): {e}", "ERROR")
                time.sleep(1)
                continue

        self.logger.log("ERROR: Не удалось получить ответ после нескольких попыток.", "ERROR")
        return None

    def send_message(self, message):
        """Отправляет сообщение и возвращает ответ."""
        self.logger.log("📤 Отправка запроса в DeepSeek...")
        result = self._send_message_with_retries(message, max_retries=3)
        return result

    def new_chat(self):
        """Создаёт новый чат."""
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
            self.logger.log(f"ERROR: Не удалось создать новый чат: {e}", "ERROR")
            return False

    def copy_last_response(self):
        """Возвращает последний ответ ассистента."""
        self.logger.log("📋 Копирование последнего ответа...")
        try:
            messages = self.driver.find_elements(By.XPATH, self.config.selectors["assistant_messages"])
            if not messages:
                self.logger.log("ERROR: Не найдено сообщений ассистента.", "ERROR")
                return None
            last = messages[-1]
            return last.text.strip()
        except Exception as e:
            self.logger.log(f"ERROR: Не удалось получить последний ответ: {e}", "ERROR")
            return None

    def close(self):
        """Закрывает драйвер."""
        if self.driver:
            self.driver.quit()