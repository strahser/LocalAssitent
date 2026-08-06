"""
list_messages.py — показать ВСЕ сообщения ассистента в активной сессии Qwen
(Edge, debug-порт 9222): индекс, длина, первые 300 символов.
"""
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.edge.options import Options
from config import SELENIUM_CONFIG


def main():
    options = Options()
    options.add_experimental_option("debuggerAddress", f"127.0.0.1:{SELENIUM_CONFIG.debug_port}")
    options.page_load_strategy = "eager"
    driver = webdriver.Edge(options=options)
    time.sleep(2)
    print(f"URL: {driver.current_url}")

    # Пробуем несколько XPath/CSS для сообщений ассистента
    attempts = [
        ".//div[contains(@class, 'message') and contains(@class, 'assistant')]",
        ".//div[contains(@class, 'assistant')]",
        ".//div[@data-role='assistant']",
        ".//article",
        ".//div[contains(@class, 'markdown')]",
    ]
    for xpath in attempts:
        try:
            els = driver.find_elements(By.XPATH, xpath)
        except Exception:
            continue
        visible = [e for e in els if e.is_displayed()]
        print(f"XPath '{xpath}': всего={len(els)}, видимых={len(visible)}")
        for i, el in enumerate(visible[-6:], start=max(1, len(visible) - 5)):
            try:
                text = el.text or ""
            except Exception:
                text = ""
            print(f"  [{i}] длина={len(text)} | {text[:300]!r}")
        if visible:
            print()

    driver.quit()


if __name__ == "__main__":
    main()
