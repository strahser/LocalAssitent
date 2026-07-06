# test_copy_button.py
import time
import sys
from selenium import webdriver
from selenium.webdriver.edge.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException

from Logger import Logger
from config import SELENIUM_CONFIG, DEBUG_PORT
from message_finder import MessageFinder
from response_copier import ResponseCopier

def main():
    logger = Logger(log_to_file=True, log_to_html=False, save_responses=False)

    options = Options()
    options.add_experimental_option("debuggerAddress", f"127.0.0.1:{DEBUG_PORT}")
    try:
        driver = webdriver.Edge(options=options)
    except Exception as e:
        logger.log(f"Не удалось подключиться: {e}", "ERROR")
        sys.exit(1)

    # Переключаемся на вкладку DeepSeek
    found = False
    for handle in driver.window_handles:
        driver.switch_to.window(handle)
        if "chat.deepseek.com" in driver.current_url:
            found = True
            logger.log(f"✅ Найдена вкладка DeepSeek: {driver.current_url}")
            break
    if not found:
        logger.log("❌ Вкладка DeepSeek не найдена.", "ERROR")
        driver.quit()
        sys.exit(1)

    try:
        WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.TAG_NAME, "body")))
    except TimeoutException:
        logger.log("❌ Страница не загрузилась.", "ERROR")
        driver.quit()
        sys.exit(1)

    # Используем MessageFinder для поиска последнего сообщения
    message_finder = MessageFinder(driver, SELENIUM_CONFIG, logger=logger)
    last_msg = message_finder.get_last_assistant_message()
    if not last_msg:
        logger.log("❌ Не найдено ни одного сообщения.", "ERROR")
        driver.quit()
        sys.exit(1)

    logger.log(f"✅ Выбрано последнее сообщение.")

    # Копируем через ResponseCopier
    copier = ResponseCopier(driver, SELENIUM_CONFIG, logger=logger)
    text = copier.copy_from_element(last_msg)
    if text:
        logger.log(f"✅ Текст скопирован (длина {len(text)} символов).")
        print("\n--- СКОПИРОВАННЫЙ ТЕКСТ ---\n")
        print(text)
        print("\n--- КОНЕЦ ТЕКСТА ---\n")
    else:
        logger.log("❌ Не удалось скопировать текст.", "ERROR")

    driver.quit()
    logger.close()

if __name__ == "__main__":
    main()