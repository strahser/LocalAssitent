"""
Чтение ответа из уже открытого браузера.
Ответ уже сгенерирован, нужно просто прочитать.
"""
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.edge.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

from agent.clipboard import ClipboardManager
from detection.element_finder import ElementFinder
from config import SELENIUM_CONFIG
from logger import Logger


def read_response():
    logger = Logger(
        log_to_html=False,
        log_to_file=True,
        save_responses=True,
        log_file="read_response.log",
        html_file="read_response_log.html"
    )
    
    print("Подключение к Edge...")
    options = Options()
    options.add_experimental_option("debuggerAddress", f"127.0.0.1:{SELENIUM_CONFIG.debug_port}")
    options.page_load_strategy = "eager"
    driver = webdriver.Edge(options=options)
    print(f"URL: {driver.current_url}")
    
    time.sleep(2)
    
    finder = ElementFinder(driver, logger, SELENIUM_CONFIG.selectors)
    clipboard = ClipboardManager()
    
    print("Поиск сообщений ассистента...")
    messages = finder.find_assistant_messages()
    print(f"Найдено сообщений: {len(messages)}")
    
    if not messages:
        print("Сообщения не найдены")
        return
    
    last_msg = messages[-1]
    text = last_msg.text
    print(f"Длина текста: {len(text)} символов")
    
    output_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "pipeline_output")
    os.makedirs(output_dir, exist_ok=True)
    
    md_path = os.path.join(output_dir, "deepseek_feedback.md")
    with open(md_path, "w", encoding="utf-8") as f:
        f.write("# Обратная связь от DeepSeek\n\n")
        f.write(f"**Дата:** {time.strftime('%Y-%m-%d %H:%M:%S')}\n\n")
        f.write("---\n\n")
        f.write(text)
    
    print(f"Сохранено: {md_path}")
    
    print("\n--- Превью (первые 1000 символов) ---")
    print(text[:1000])
    print("--- конец превью ---")
    
    driver.quit()
    logger.close()
    return text


if __name__ == "__main__":
    read_response()
