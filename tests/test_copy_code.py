# test_copy_code_block.py
import time
import sys
from selenium import webdriver
from selenium.webdriver.edge.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException

from config.config import DEBUG_PORT, SELENIUM_CONFIG
from logger.Logger import Logger
from core.client import DeepSeekClient
from core.message_finder import MessageFinder
from utils.clipboard_manager import ClipboardManager


def find_copy_button_in_assistant_message(driver, message_finder, logger):
    """
    Находит кнопку копирования в последнем сообщении ассистента.
    """
    # Получаем все сообщения ассистента
    assistant_messages = message_finder.get_assistant_messages()
    if not assistant_messages:
        logger.error("Нет сообщений ассистента.")
        return None, None

    # Берём последнее сообщение ассистента
    last_msg = assistant_messages[-1]
    logger.info(f"Найдено последнее сообщение ассистента (длина текста: {len(last_msg.text)} символов).")

    # Проверяем, есть ли в нём код
    if "```" not in last_msg.text:
        logger.warning("В сообщении нет блоков кода.")
        return None, None

    # Ищем кнопку копирования ТОЛЬКО внутри этого сообщения
    try:
        # Вариант 1: по тексту (русский/английский)
        copy_spans = last_msg.find_elements(By.XPATH,
            ".//span[contains(@class, 'code-info-button-text') and (text()='Копировать' or text()='Copy')]")
        for span in copy_spans:
            button = span.find_element(By.XPATH, "./ancestor::div[@role='button']")
            if button and button.is_displayed() and button.is_enabled():
                logger.info("Найдена кнопка 'Копировать'/'Copy'.")
                return last_msg, button
    except Exception as e:
        logger.debug(f"Ошибка при поиске по тексту: {e}")

    # Вариант 2: по классу кнопки
    try:
        buttons = last_msg.find_elements(By.XPATH,
            ".//div[@role='button' and contains(@class, 'ds-button') and contains(@class, 'ds-button--borderlessNeutral')]")
        for button in buttons:
            spans = button.find_elements(By.XPATH, ".//span[contains(@class, 'code-info-button-text')]")
            if spans and button.is_displayed() and button.is_enabled():
                logger.info("Найдена кнопка по классу ds-button.")
                return last_msg, button
    except Exception as e:
        logger.debug(f"Ошибка при поиске по классу: {e}")

    logger.error("Кнопка копирования не найдена в последнем сообщении ассистента.")
    return None, None


def main():
    logger = Logger(log_to_file=True, log_to_html=False, save_responses=False,
                    console_level='INFO', file_level='DEBUG')

    # Подключение к браузеру
    options = Options()
    options.add_experimental_option("debuggerAddress", f"127.0.0.1:{DEBUG_PORT}")
    try:
        driver = webdriver.Edge(options=options)
    except Exception as e:
        logger.error(f"Не удалось подключиться: {e}")
        sys.exit(1)

    # Поиск вкладки DeepSeek
    found = False
    for handle in driver.window_handles:
        driver.switch_to.window(handle)
        if "chat.deepseek.com" in driver.current_url:
            found = True
            logger.info(f"Найдена вкладка DeepSeek: {driver.current_url}")
            break
    if not found:
        logger.error("Вкладка DeepSeek не найдена.")
        driver.quit()
        sys.exit(1)

    try:
        WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.TAG_NAME, "body")))
    except TimeoutException:
        logger.error("Страница не загрузилась.")
        driver.quit()
        sys.exit(1)

    # Создаём клиент для отправки сообщений
    client = DeepSeekClient(logger, SELENIUM_CONFIG)
    driver = client.driver
    message_finder = MessageFinder(driver, SELENIUM_CONFIG, logger=logger)

    # Проверяем последнее сообщение ассистента
    last_msg, copy_button = find_copy_button_in_assistant_message(driver, message_finder, logger)

    # Если нет кнопки или нет кода, отправляем запрос
    if last_msg is None or copy_button is None:
        logger.info("Отправляем запрос на генерацию кода...")
        prompt = "Напиши простой Python скрипт, который выводит 'Hello, World!'. Ответь только кодом в блоке ```python ... ```. Не добавляй пояснений."
        response = client.send_message(prompt)
        if response is None:
            logger.error("Не удалось получить ответ.")
            driver.quit()
            sys.exit(1)

        # Ждём появления нового сообщения
        time.sleep(2)
        last_msg, copy_button = find_copy_button_in_assistant_message(driver, message_finder, logger)
        if last_msg is None or copy_button is None:
            logger.error("Не удалось найти сообщение с кодом после отправки.")
            driver.quit()
            sys.exit(1)

    logger.info("Найдено сообщение ассистента с кодом, копируем...")

    clipboard = ClipboardManager()

    try:
        # Прокручиваем к кнопке
        driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", copy_button)
        time.sleep(0.5)

        # Кликаем через JavaScript (надёжнее)
        driver.execute_script("arguments[0].click();", copy_button)
        time.sleep(0.5)

        copied_text = clipboard.get_text()
        if copied_text and len(copied_text) > 10:
            logger.success(f"Код скопирован (длина {len(copied_text)} символов).")

            # Проверяем, что скопирован именно код (а не текст теста)
            if "```" not in copied_text and "import" in copied_text:
                logger.success("✅ Скопирован именно код (содержит import).")
            else:
                logger.warning("⚠️ Возможно, скопирован не код.")

            print("\n--- СКОПИРОВАННЫЙ КОД ---\n")
            print(copied_text)
            print("\n--- КОНЕЦ КОДА ---\n")
        else:
            logger.error("Буфер обмена пуст или слишком короткий.")
            driver.quit()
            sys.exit(1)

    except Exception as e:
        logger.error(f"Ошибка при копировании: {e}")
        driver.quit()
        sys.exit(1)

    driver.quit()
    logger.close()
    sys.exit(0)


if __name__ == "__main__":
    main()