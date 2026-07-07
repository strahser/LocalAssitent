# test_chat_ui.py
import sys
import time
from selenium import webdriver
from selenium.webdriver.edge.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException

from config.config import DEBUG_PORT, SELENIUM_CONFIG
from logger.Logger import Logger
from core.client import DeepSeekClient
from core.message_finder import MessageFinder
from core.response_copier import ResponseCopier

class ChatUITester:
    def __init__(self):
        self.last_response = None
        self.logger = Logger(log_to_file=True, log_to_html=False, save_responses=False,
                             console_level='INFO', file_level='DEBUG')
        self.driver = None
        self.client = None
        self.message_finder = None
        self.response_copier = None

    def setup(self):
        """Подключение к браузеру и инициализация компонентов."""
        options = Options()
        options.add_experimental_option("debuggerAddress", f"127.0.0.1:{DEBUG_PORT}")
        try:
            self.driver = webdriver.Edge(options=options)
        except Exception as e:
            self.logger.error(f"Не удалось подключиться к браузеру: {e}")
            return False

        # Ищем вкладку DeepSeek
        found = False
        for handle in self.driver.window_handles:
            self.driver.switch_to.window(handle)
            if "chat.deepseek.com" in self.driver.current_url:
                found = True
                self.logger.info(f"Найдена вкладка DeepSeek: {self.driver.current_url}")
                break
        if not found:
            self.logger.error("Вкладка DeepSeek не найдена.")
            self.driver.quit()
            return False

        try:
            WebDriverWait(self.driver, 10).until(EC.presence_of_element_located((By.TAG_NAME, "body")))
        except TimeoutException:
            self.logger.error("Страница не загрузилась.")
            self.driver.quit()
            return False

        # Используем существующий DeepSeekClient для отправки сообщений
        self.client = DeepSeekClient(self.logger, SELENIUM_CONFIG)
        # Используем driver из клиента, чтобы избежать дублирования
        self.driver = self.client.driver
        self.message_finder = MessageFinder(self.driver, SELENIUM_CONFIG, logger=self.logger)
        self.response_copier = ResponseCopier(self.driver, SELENIUM_CONFIG, logger=self.logger)
        return True

    def test_input_box_presence(self):
        """Проверка наличия поля ввода."""
        self.logger.info("Шаг 1: Проверка поля ввода...")
        try:
            input_box = WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, SELENIUM_CONFIG.selectors["input_textarea"]))
            )
            self.logger.success("✅ Поле ввода найдено.")
            return True
        except TimeoutException:
            self.logger.error("❌ Поле ввода не найдено.")
            return False

    def test_send_message(self, message="Привет, как дела? Напиши краткий ответ."):
        """Отправка сообщения и получение ответа."""
        self.logger.info(f"Шаг 2: Отправка сообщения: '{message[:30]}...'")
        try:
            response = self.client.send_message(message)
            if response:
                self.logger.success(f"✅ Ответ получен (длина {len(response)} символов).")
                # Сохраним ответ для дальнейших проверок
                self.last_response = response
                return True
            else:
                self.logger.error("❌ Ответ не получен.")
                return False
        except Exception as e:
            self.logger.error(f"❌ Ошибка при отправке: {e}")
            return False

    def test_copy_response(self):
        """Проверка копирования ответа через кнопку."""
        self.logger.info("Шаг 3: Проверка копирования ответа...")
        last_msg = self.message_finder.get_last_assistant_message()
        if not last_msg:
            self.logger.error("❌ Нет сообщений ассистента для копирования.")
            return False
        text = self.response_copier.copy_from_element(last_msg)
        if text:
            self.logger.success(f"✅ Текст скопирован (длина {len(text)} символов).")
            # Сравниваем с сохранённым ответом (если есть)
            if hasattr(self, 'last_response') and self.last_response:
                if text.strip() == self.last_response.strip():
                    self.logger.success("✅ Скопированный текст совпадает с полученным.")
                else:
                    self.logger.warning("⚠️ Скопированный текст отличается от полученного (возможно, из-за форматирования).")
            return True
        else:
            self.logger.error("❌ Не удалось скопировать текст.")
            return False

    def test_new_chat(self):
        """Проверка создания нового чата."""
        self.logger.info("Шаг 4: Проверка создания нового чата...")
        try:
            result = self.client.new_chat()
            if result:
                self.logger.success("✅ Новый чат создан.")
                return True
            else:
                self.logger.error("❌ Не удалось создать новый чат.")
                return False
        except Exception as e:
            self.logger.error(f"❌ Ошибка при создании нового чата: {e}")
            return False

    def run_all_tests(self):
        """Запуск всех тестов."""
        if not self.setup():
            self.logger.error("Настройка не удалась, тесты прерваны.")
            return False

        results = []
        results.append(("Наличие поля ввода", self.test_input_box_presence()))
        if results[-1][1]:
            results.append(("Отправка сообщения", self.test_send_message()))
        else:
            self.logger.warning("Пропускаем отправку, т.к. поле ввода не найдено.")
            results.append(("Отправка сообщения", False))

        if results[-1][1]:
            results.append(("Копирование ответа", self.test_copy_response()))
        else:
            self.logger.warning("Пропускаем копирование, т.к. сообщение не отправлено.")
            results.append(("Копирование ответа", False))

        # New chat можно проверить независимо
        results.append(("Создание нового чата", self.test_new_chat()))

        # Вывод итогов
        self.logger.info("\n=== РЕЗУЛЬТАТЫ ТЕСТОВ ===")
        all_passed = True
        for name, passed in results:
            status = "✅ PASS" if passed else "❌ FAIL"
            self.logger.log(f"{name}: {status}", level="INFO")
            if not passed:
                all_passed = False

        self.cleanup()
        return all_passed

    def cleanup(self):
        if self.driver:
            self.driver.quit()
            self.logger.info("Браузер закрыт.")
        self.logger.close()

def main():
    tester = ChatUITester()
    success = tester.run_all_tests()
    sys.exit(0 if success else 1)

if __name__ == "__main__":
    main()