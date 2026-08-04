"""
Ожидание и чтение полного ответа из DeepSeek.
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
from Logger import Logger


def wait_and_read():
    logger = Logger(
        log_to_html=False,
        log_to_file=True,
        save_responses=True,
        log_file="wait_read.log",
        html_file="wait_read_log.html"
    )
    
    print("Подключение к Edge...")
    options = Options()
    options.add_experimental_option("debuggerAddress", f"127.0.0.1:{SELENIUM_CONFIG.debug_port}")
    options.page_load_strategy = "eager"
    driver = webdriver.Edge(options=options)
    print(f"URL: {driver.current_url}")
    
    finder = ElementFinder(driver, logger, SELENIUM_CONFIG.selectors)
    clipboard = ClipboardManager()
    
    print("\nОжидание завершения генерации ответа (до 5 минут)...")
    print("Нажмите Ctrl+C для прерывания\n")
    
    start = time.time()
    last_len = 0
    stable_count = 0
    
    while time.time() - start < 300:
        try:
            messages = finder.find_assistant_messages()
            if messages:
                current_text = messages[-1].text
                current_len = len(current_text)
                
                if current_len > last_len:
                    print(f"  [{int(time.time()-start)}s] Ответ растёт: {current_len} символов", end="\r")
                    last_len = current_len
                    stable_count = 0
                else:
                    stable_count += 1
                    if stable_count >= 10:
                        print(f"\n  Ответ стабилизировался на {current_len} символов")
                        break
            else:
                print(f"  [{int(time.time()-start)}s] Ожидание...", end="\r")
        except Exception as e:
            print(f"  Ошибка: {e}")
        
        time.sleep(1)
    
    print("\n" + "=" * 60)
    
    messages = finder.find_assistant_messages()
    if not messages:
        print("Сообщения не найдены")
        driver.quit()
        logger.close()
        return None
    
    final_text = messages[-1].text
    print(f"\nДлина финального ответа: {len(final_text)} символов")
    
    output_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "pipeline_output")
    os.makedirs(output_dir, exist_ok=True)
    
    md_path = os.path.join(output_dir, "deepseek_feedback.md")
    with open(md_path, "w", encoding="utf-8") as f:
        f.write("# Обратная связь от DeepSeek\n\n")
        f.write(f"**Дата:** {time.strftime('%Y-%m-%d %H:%M:%S')}\n\n")
        f.write(f"**Длина ответа:** {len(final_text)} символов\n\n")
        f.write("---\n\n")
        f.write(final_text)
    
    print(f"Сохранено: {md_path}")
    
    print("\n--- Ответ ---")
    print(final_text)
    print("--- конец ---")
    
    driver.quit()
    logger.close()
    return final_text


if __name__ == "__main__":
    wait_and_read()
