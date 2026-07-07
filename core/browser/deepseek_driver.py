# core/client.py
import time
from typing import Optional, Tuple
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
    ElementClickInterceptedException
)
from selenium.webdriver.remote.webelement import WebElement

from core.browser.response_waiter import ResponseReadyStrategyFactory
from core.browser.message_finder import MessageFinder
from core.browser.response_copier import ResponseCopier
from utils.clipboard_manager import ClipboardManager


class DeepSeekBrowserDriver:
    def __init__(self, logger, config):
        self.logger = logger
        self.config = config
        self.driver = None
        self.clipboard = ClipboardManager()
        self.message_finder = None
        self.response_copier = None
        self._connect()

    # ---------- Инициализация и подключение ----------
    def _connect(self) -> None:
        """Подключается к существующему экземпляру Edge или открывает новую вкладку DeepSeek."""
        self._attach_to_browser()
        self._ensure_deepseek_tab()
        self._wait_for_page_load()
        self._init_finders_and_copiers()
        self.logger.info(f"Подключено к браузеру. Текущий URL: {self.driver.current_url}")

    def _attach_to_browser(self) -> None:
        """Подключается к браузеру через debuggerAddress."""
        options = Options()
        options.add_experimental_option("debuggerAddress", f"127.0.0.1:{self.config.debug_port}")
        try:
            self.driver = webdriver.Edge(options=options)
        except Exception as e:
            self.logger.error(f"Не удалось подключиться к браузеру: {e}")
            raise

    def _ensure_deepseek_tab(self) -> None:
        """Находит вкладку DeepSeek или создаёт новую."""
        for handle in self.driver.window_handles:
            self.driver.switch_to.window(handle)
            if "chat.deepseek.com" in self.driver.current_url:
                self.logger.info(f"Найдена вкладка DeepSeek: {self.driver.current_url}")
                return

        self.logger.warning("Вкладка DeepSeek не найдена, открываем новую...")
        self.driver.execute_script("window.open('');")
        self.driver.switch_to.window(self.driver.window_handles[-1])
        self.driver.get(self.config.deepseek_url)
        self.logger.info(f"Открыта новая вкладка: {self.driver.current_url}")

        self.driver.execute_script("window.focus();")

    def _wait_for_page_load(self, timeout: int = 15) -> None:
        """Ожидает загрузки тела страницы."""
        try:
            WebDriverWait(self.driver, timeout).until(EC.presence_of_element_located((By.TAG_NAME, "body")))
        except TimeoutException:
            self.logger.error("Страница не загрузилась за %d секунд.", timeout)
            self.driver.quit()
            raise

    def _init_finders_and_copiers(self) -> None:
        """Инициализирует вспомогательные объекты для работы с сообщениями."""
        self.message_finder = MessageFinder(self.driver, self.config, logger=self.logger)
        self.response_copier = ResponseCopier(self.driver, self.config, logger=self.logger)

    # ---------- Работа с полем ввода ----------
    def _wait_for_input_box(self, timeout: int = 15) -> Optional[WebElement]:
        """Ожидает появления поля ввода и возвращает его."""
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

    def _clear_input_box(self, input_box: WebElement) -> None:
        """Очищает поле ввода."""
        input_box.click()
        input_box.clear()
        time.sleep(0.2)

    def _is_input_empty(self, input_box: WebElement) -> bool:
        """Проверяет, пусто ли поле ввода."""
        return self.driver.execute_script("return arguments[0].value;", input_box) == ""

    # ---------- Вставка текста ----------
    def _insert_text(self, input_box: WebElement, message: str) -> bool:
        """Вставляет текст в поле ввода (через буфер обмена или send_keys)."""
        if self._paste_via_clipboard(input_box, message):
            return True
        self.logger.warning("Вставка через Ctrl+V не сработала, пробуем send_keys.")
        return self._paste_via_send_keys(input_box, message)

    def _paste_via_clipboard(self, input_box: WebElement, message: str) -> bool:
        """Вставляет текст через буфер обмена (Ctrl+V)."""
        try:
            self.clipboard.set_text(message)
            self._clear_input_box(input_box)
            ActionChains(self.driver).key_down(Keys.CONTROL).send_keys('v').key_up(Keys.CONTROL).perform()
            time.sleep(0.5)
            inserted = self.driver.execute_script("return arguments[0].value;", input_box)
            if inserted and len(inserted) >= len(message) // 2:
                self.logger.debug(f"Текст вставлен через буфер (длина {len(inserted)} символов).")
                return True
            return False
        except Exception as e:
            self.logger.debug(f"Ошибка при вставке через буфер: {e}")
            return False

    def _paste_via_send_keys(self, input_box: WebElement, message: str) -> bool:
        """Вставляет текст через send_keys (медленнее, но надёжнее)."""
        try:
            self._clear_input_box(input_box)
            input_box.send_keys(message)
            inserted = self.driver.execute_script("return arguments[0].value;", input_box)
            if inserted:
                self.logger.debug(f"Текст вставлен через send_keys (длина {len(inserted)}).")
                return True
            self.logger.error("Не удалось вставить текст через send_keys.")
            return False
        except Exception as e:
            self.logger.error(f"Ошибка при вставке через send_keys: {e}")
            return False

    # ---------- Отправка сообщения ----------
    def _send_message(self, input_box: WebElement) -> bool:
        """Отправляет сообщение (Enter или клик по кнопке) с повторными попытками."""
        max_attempts = 3
        for attempt in range(max_attempts):
            try:
                if self._send_via_enter(input_box):
                    return True
                if self._send_via_button(input_box):
                    return True
            except StaleElementReferenceException:
                self.logger.warning(f"StaleElementReferenceException, попытка {attempt+1}/{max_attempts}...")
                input_box = self._wait_for_input_box()
                if not input_box:
                    return False
                continue
            except Exception as e:
                self.logger.warning(f"Ошибка при отправке: {e}")
                # продолжаем попытки
                continue
        self.logger.error("Не удалось отправить сообщение после нескольких попыток.")
        return False

    def _send_via_enter(self, input_box: WebElement) -> bool:
        """Отправляет нажатием Enter."""
        self.logger.debug("Отправка через Enter...")
        try:
            ActionChains(self.driver).send_keys(Keys.RETURN).perform()
            time.sleep(1)
            if self._is_input_empty(input_box):
                self.logger.debug("Поле очистилось после Enter.")
                return True
            self.logger.warning("Поле не очистилось после Enter.")
        except Exception as e:
            self.logger.warning(f"Ошибка при Enter: {e}")
        return False

    def _send_via_button(self, input_box: WebElement) -> bool:
        """Отправляет кликом по кнопке с классом ds-button--circle."""
        self.logger.debug("Попытка клика по кнопке ds-button--circle...")
        try:
            buttons = self.driver.find_elements(By.CSS_SELECTOR, "div[role='button']")
            for btn in buttons:
                classes = btn.get_attribute("class") or ""
                if "ds-button--circle" in classes:
                    btn.click()
                    self.logger.debug("Клик по кнопке выполнен.")
                    time.sleep(1)
                    if self._is_input_empty(input_box):
                        return True
                    # повторный клик, если не очистилось
                    btn.click()
                    time.sleep(1)
                    if self._is_input_empty(input_box):
                        return True
            self.logger.error("Не найден подходящий элемент с ds-button--circle.")
        except Exception as e:
            self.logger.error(f"Ошибка при поиске/клике кнопки: {e}")
        return False

    # ---------- Основной публичный метод ----------
    def send_message(self, message: str) -> Optional[str]:
        """Отправляет сообщение и возвращает ответ ассистента."""
        self.logger.info("Отправка запроса в DeepSeek...")
        input_box = self._wait_for_input_box()
        if not input_box:
            return None
        if not self._insert_text(input_box, message):
            return None
        if not self._send_message(input_box):
            return None

        self._wait_for_response_ready()
        return self._get_assistant_response()

    def _wait_for_response_ready(self) -> None:
        """Ожидает готовности ответа с использованием выбранной стратегии."""
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
            self.logger.warning(f"Стратегия не подтвердила готовность за {self.config.stable_timeout} сек. Причина: {reason}")

    def _get_assistant_response(self) -> Optional[str]:
        """Получает текст последнего ответа ассистента (через копирование или .text)."""
        last_msg = self.message_finder.get_last_assistant_message()
        if not last_msg:
            self.logger.error("Нет сообщений ассистента.")
            return None

        full_text = self.response_copier.copy_from_element(last_msg)
        if full_text:
            self.logger.info("Ответ скопирован через буфер обмена.")
            return full_text

        self.logger.warning("Не удалось скопировать через кнопку, используем .text")
        full_text = last_msg.text.strip()
        if full_text:
            self.logger.info("Ответ получен через .text.")
            return full_text

        self.logger.error("Не удалось получить текст ответа.")
        return None

    # ---------- Управление чатом ----------
    def new_chat(self) -> bool:
        """Создаёт новый чат через горячую клавишу Ctrl+J."""
        self.logger.info("Создание нового чата через Ctrl+J...")
        try:
            # Убедимся, что фокус на странице (клик по body)
            body = self.driver.find_element(By.TAG_NAME, "body")
            body.click()
            time.sleep(0.2)

            # Эмуляция Ctrl+J
            ActionChains(self.driver).key_down(Keys.CONTROL).send_keys('j').key_up(Keys.CONTROL).perform()
            time.sleep(1)
            self.logger.info("Горячая клавиша Ctrl+J отправлена.")
            return True
        except Exception as e:
            self.logger.error(f"Ошибка при отправке Ctrl+J: {e}")
            return False

    def attach_file(self, file_path: str) -> None:
        """Прикрепляет файл (заглушка)."""
        self.logger.warning("attach_file не реализован.")

    def close(self) -> None:
        """Закрывает браузер."""
        if self.driver:
            self.driver.quit()
            self.logger.info("Браузер закрыт.")