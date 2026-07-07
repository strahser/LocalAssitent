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
from core.message_finder import MessageFinder
from core.response_copier import ResponseCopier

def main():
    logger = Logger(log_to_file=True, log_to_html=False, save_responses=False,
                    console_level='INFO', file_level='DEBUG')

    options = Options()
    options.add_experimental_option("debuggerAddress", f"127.0.0.1:{DEBUG_PORT}")
    try:
        driver = webdriver.Edge(options=options)
    except Exception as e:
        logger.error(f"Не удалось подключиться: {e}")
        sys.exit(1)

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

    message_finder = MessageFinder(driver, SELENIUM_CONFIG, logger=logger)
    last_msg = message_finder.get_last_assistant_message()
    if not last_msg:
        logger.error("Не найдено ни одного сообщения.")
        driver.quit()
        sys.exit(1)

    logger.info("Выбрано последнее сообщение.")

    copier = ResponseCopier(driver, SELENIUM_CONFIG, logger=logger)
    text = copier.copy_from_element(last_msg)
    if text:
        logger.success(f"Текст скопирован (длина {len(text)} символов).")
        print("\n--- СКОПИРОВАННЫЙ ТЕКСТ ---\n")
        print(text)
        print("\n--- КОНЕЦ ТЕКСТА ---\n")
    else:
        logger.error("Не удалось скопировать текст.")

    driver.quit()
    logger.close()

if __name__ == "__main__":
    main()
