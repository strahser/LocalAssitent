# core/client.py
import time
from typing import Optional
from selenium import webdriver
from selenium.webdriver.edge.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.action_chains import ActionChains
from selenium.common.exceptions import TimeoutException, StaleElementReferenceException, ElementClickInterceptedException
from selenium.webdriver.remote.webelement import WebElement

from core.response_ready_strategy import ResponseReadyStrategyFactory
from core.message_finder import MessageFinder
from core.response_copier import ResponseCopier
from utils.clipboard_manager import ClipboardManager

class DeepSeekClient:
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
            self.logger.error(f"Не удалось подключиться к браузеру: {e}")
            raise

        found = False
        for handle in self.driver.window_handles:
            self.driver.switch_to.window(handle)
            if "chat.deepseek.com" in self.driver.current_url:
                found = True
                self.logger.info(f"Найдена вкладка DeepSeek: {self.driver.current_url}")
                break

        if not found:
            self.logger.warning("Вкладка DeepSeek не найдена, открываем новую...")
            self.driver.execute_script("window.open('');")
            self.driver.switch_to.window(self.driver.window_handles[-1])
            self.driver.get(self.config.deepseek_url)
            self.logger.info(f"Открыта новая вкладка: {self.driver.current_url}")

        self.driver.execute_script("window.focus();")

        try:
            WebDriverWait(self.driver, 15).until(EC.presence_of_element_located((By.TAG_NAME, "body")))
        except TimeoutException:
            self.logger.error("Страница не загрузилась за 15 секунд.")
            self.driver.quit()
            raise

        self.logger.info(f"Подключено к браузеру. Текущий URL: {self.driver.current_url}")

        self.message_finder = MessageFinder(self.driver, self.config, logger=self.logger)
        self.response_copier = ResponseCopier(self.driver, self.config, logger=self.logger)

    def _wait_for_input_box(self, timeout=15) -> Optional[WebElement]:
        self.logger.debug(f"Ожидание поля ввода (селектор: {self.config.selectors['input_textarea']})...")
        try:
            input_box = WebDriverWait(self.driver, timeout).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, self.config.selectors["input_textarea"]))
            )
            self.driver.execute_script("arguments[0].scrollIntoView(true);", input_box)
            self.logger.debug("Поле ввода найдено.")
            return input_box
        except TimeoutException:
            self.logger.error("Таймаут ожидания поля ввода.")
            return None

    def _insert_text(self, input_box: WebElement, message: str) -> bool:
        self.logger.debug("Вставка текста через буфер обмена...")
        try:
            self.clipboard.set_text(message)
            input_box.click()
            input_box.clear()
            time.sleep(0.2)
            ActionChains(self.driver).key_down(Keys.CONTROL).send_keys('v').key_up(Keys.CONTROL).perform()
            time.sleep(0.5)
            inserted = self.driver.execute_script("return arguments[0].value;", input_box)
            if inserted and len(inserted) >= len(message) // 2:
                self.logger.debug(f"Текст вставлен (длина {len(inserted)} символов).")
                return True
            else:
                self.logger.warning("Вставка через Ctrl+V не сработала, пробуем send_keys.")
                input_box.clear()
                input_box.send_keys(message)
                inserted = self.driver.execute_script("return arguments[0].value;", input_box)
                if inserted:
                    self.logger.debug(f"Текст вставлен через send_keys (длина {len(inserted)}).")
                    return True
                else:
                    self.logger.error("Не удалось вставить текст.")
                    return False
        except Exception as e:
            self.logger.error(f"Ошибка вставки текста: {e}")
            return False

    def _send_message(self, input_box: WebElement) -> bool:
        max_attempts = 3
        for attempt in range(max_attempts):
            try:
                self.logger.debug("Отправка через Enter...")
                ActionChains(self.driver).send_keys(Keys.RETURN).perform()
                time.sleep(1)
                new_text = self.driver.execute_script("return arguments[0].value;", input_box)
                if new_text == "":
                    self.logger.debug("Поле очистилось, запрос принят.")
                    return True
                else:
                    self.logger.warning("Поле не очистилось после Enter.")
            except StaleElementReferenceException:
                self.logger.warning(f"StaleElementReferenceException при отправке, попытка {attempt+1}/{max_attempts}...")
                input_box = self._wait_for_input_box()
                if not input_box:
                    return False
                continue
            except Exception as e:
                self.logger.warning(f"Ошибка при Enter: {e}")

            self.logger.debug("Попытка клика по кнопке с ds-button--circle...")
            try:
                buttons = self.driver.find_elements(By.CSS_SELECTOR, "div[role='button']")
                for btn in buttons:
                    classes = btn.get_attribute("class") or ""
                    if "ds-button--circle" in classes:
                        btn.click()
                        self.logger.debug("Клик по кнопке с ds-button--circle.")
                        time.sleep(1)
                        new_text = self.driver.execute_script("return arguments[0].value;", input_box)
                        if new_text == "":
                            return True
                        else:
                            self.logger.warning("Поле не очистилось после клика, повторная попытка...")
                            btn.click()
                            time.sleep(1)
                            new_text = self.driver.execute_script("return arguments[0].value;", input_box)
                            if new_text == "":
                                return True
                self.logger.error("Не найден подходящий элемент с ds-button--circle.")
            except StaleElementReferenceException:
                self.logger.warning(f"StaleElementReferenceException при клике, попытка {attempt+1}/{max_attempts}...")
                input_box = self._wait_for_input_box()
                if not input_box:
                    return False
                continue
            except Exception as e:
                self.logger.error(f"Ошибка при поиске кнопки: {e}")
                return False

        self.logger.error("Не удалось отправить сообщение после нескольких попыток.")
        return False

    def send_message(self, message: str) -> Optional[str]:
        self.logger.info("Отправка запроса в DeepSeek...")
        input_box = self._wait_for_input_box()
        if not input_box:
            return None
        if not self._insert_text(input_box, message):
            return None
        if not self._send_message(input_box):
            return None

        strategy = ResponseReadyStrategyFactory.get_strategy(
            self.config.response_strategy,
            driver=self.driver,
            config=self.config,
            logger=self.logger,
            check_interval=self.config.check_interval,
            stable_duration=self.config.stable_duration,
            debug_interval=2.0
        )
        self.logger.debug(f"Ожидание готовности ответа (стратегия: {self.config.response_strategy})...")
        ready, reason = strategy.wait(self.driver, self.config.stable_timeout)
        if ready:
            self.logger.debug(f"Ответ готов (триггер: {reason}).")
        else:
            self.logger.warning(f"Стратегия не подтвердила готовность ответа за {self.config.stable_timeout} сек. Причина: {reason}")

        last_msg = self.message_finder.get_last_assistant_message()
        if not last_msg:
            self.logger.error("Нет сообщений ассистента.")
            return None

        full_text = self.response_copier.copy_from_element(last_msg)
        if full_text:
            self.logger.info("Ответ скопирован через буфер обмена.")
            return full_text
        else:
            self.logger.warning("Не удалось скопировать через кнопку, используем .text")
            full_text = last_msg.text.strip()
            if full_text:
                self.logger.info("Ответ получен через .text.")
                return full_text
            else:
                self.logger.error("Не удалось получить текст ответа.")
                return None

    def new_chat(self) -> bool:
        self.logger.info("Создание нового чата...")
        selectors = ["//span[text()='New chat']", "//span[text()='Новый чат']", "//button[contains(@aria-label, 'New chat')]"]
        for xpath in selectors:
            try:
                new_chat_btn = WebDriverWait(self.driver, 5).until(
                    EC.element_to_be_clickable((By.XPATH, xpath))
                )
                new_chat_btn.click()
                self.logger.info("Кнопка 'New chat' нажата.")
                time.sleep(1)
                return True
            except TimeoutException:
                continue
        self.logger.warning("Не удалось найти кнопку 'New chat'.")
        return False

    def close(self):
        if self.driver:
            self.driver.quit()
            self.logger.info("Браузер закрыт.")
