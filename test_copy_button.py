# test_copy_button.py
import time
import sys
from selenium import webdriver
from selenium.webdriver.edge.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.common.action_chains import ActionChains

from Logger import Logger
from config import SELENIUM_CONFIG, DEBUG_PORT
from clipboard_manager import ClipboardManager
from action_panel_finder import ActionPanelFinder


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

    # Ищем сообщения ассистента
    selectors = SELENIUM_CONFIG.selectors.get("assistant_messages", [])
    if isinstance(selectors, str):
        selectors = [selectors]

    messages = []
    for xpath in selectors:
        try:
            elements = driver.find_elements(By.XPATH, xpath)
            if elements:
                logger.log(f"✅ Найдено {len(elements)} сообщений по XPath: {xpath}")
                messages.extend(elements)
        except Exception as e:
            logger.log(f"Ошибка при поиске по XPath {xpath}: {e}", "WARNING")

    if not messages:
        logger.log("❌ Не найдено ни одного сообщения.", "ERROR")
        driver.quit()
        sys.exit(1)

    # Берём последнее сообщение
    last_msg = messages[-1]
    logger.log(f"✅ Выбрано последнее сообщение (всего кандидатов: {len(messages)}).")

    # Наводим курсор
    try:
        ActionChains(driver).move_to_element(last_msg).perform()
        time.sleep(0.3)
    except Exception as e:
        logger.log(f"Ошибка при наведении: {e}", "WARNING")

    # Используем ActionPanelFinder
    panel_finder = ActionPanelFinder(driver, SELENIUM_CONFIG, logger=logger)
    copy_btn = panel_finder.find_copy_button(last_msg)
    if not copy_btn:
        logger.log("❌ Кнопка копирования не найдена.", "ERROR")
        driver.quit()
        sys.exit(1)

    if copy_btn.is_displayed() and copy_btn.is_enabled():
        logger.log("✅ Кнопка Копировать найдена и активна.")
        driver.execute_script("arguments[0].scrollIntoView(true);", copy_btn)
        time.sleep(0.2)
        copy_btn.click()
        time.sleep(0.5)
        text = ClipboardManager.get_text()
        if text:
            logger.log(f"✅ Текст скопирован (длина {len(text)} символов).")
            print("\n--- СКОПИРОВАННЫЙ ТЕКСТ ---\n")
            print(text)
            print("\n--- КОНЕЦ ТЕКСТА ---\n")
        else:
            logger.log("⚠️ Буфер обмена пуст после клика.", "WARNING")
    else:
        logger.log("❌ Кнопка неактивна/невидима.", "ERROR")

    driver.quit()
    logger.close()


if __name__ == "__main__":
    main()