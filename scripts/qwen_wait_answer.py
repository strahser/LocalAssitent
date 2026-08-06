"""
qwen_wait_answer.py — ожидание завершения генерации ответа Qwen в открытом чате.

Использование (Агент-3):
    python scripts/qwen_wait_answer.py [--timeout 600] [--stable 15] [--marker КОНЕЦ_ТЗ]

Опрашивает последний блок div.qwen-chat-message-assistant:
  - ждёт, пока длина текста стабилизируется (2 замера с интервалом --stable);
  - опционально ждёт маркер конца (--marker);
  - распознаёт «Сетевая ошибка» / «Oops! issue connecting» (-> код выхода 3, требует ретрая).

Выход: 0 — готов, 1 — таймаут/не готов, 2 — пустой чат, 3 — сетевая ошибка Qwen.
"""
import argparse
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.edge.options import Options

ASSISTANT_SELECTOR = "div.qwen-chat-message-assistant"
ERROR_MARKERS = ("Сетевая ошибка", "issue connecting", "Oops! There was an issue")


def connect(port=9222):
    opts = Options()
    opts.add_experimental_option("debuggerAddress", f"127.0.0.1:{port}")
    opts.page_load_strategy = "eager"
    return webdriver.Edge(options=opts)


def last_text(driver):
    msgs = driver.find_elements(By.CSS_SELECTOR, ASSISTANT_SELECTOR)
    if not msgs:
        return ""
    return (msgs[-1].text or "")


def is_error(text):
    return any(m in text for m in ERROR_MARKERS)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Ожидание ответа Qwen")
    ap.add_argument("--port", type=int, default=9222)
    ap.add_argument("--timeout", type=float, default=600, help="Макс. ожидание, сек")
    ap.add_argument("--stable", type=float, default=15, help="Интервал между замерами стабильности")
    ap.add_argument("--marker", default="", help="Маркер конца ответа (например КОНЕЦ_ТЗ)")
    args = ap.parse_args(argv)

    driver = connect(args.port)
    try:
        start = time.time()
        prev = ""
        while time.time() - start < args.timeout:
            text = last_text(driver)
            if is_error(text):
                print(f"ERROR: сетевая ошибка Qwen: {text[:120]!r}")
                return 3
            if text and text != prev:
                # текст меняется — генерация идёт, сбрасываем таймер стабильности
                print(f"  generating... len={len(text)}")
                prev = text
                stable_since = time.time()
                while time.time() - stable_since < args.stable:
                    time.sleep(2)
                    text2 = last_text(driver)
                    if is_error(text2):
                        print(f"ERROR: сетевая ошибка Qwen: {text2[:120]!r}")
                        return 3
                    if text2 != text:
                        text = text2
                        stable_since = time.time()
                        print(f"  generating... len={len(text)}")
                # стабильно args.stable сек
                if args.marker and args.marker not in text:
                    print(f"WARN: стабилен ({len(text)}), но маркер {args.marker!r} не найден")
                    return 1
                print(f"READY: {len(text)} символов, маркер={args.marker in text}")
                return 0
            time.sleep(2)
        print("TIMEOUT: ответ не готов")
        return 1
    finally:
        try:
            driver.quit()
        except Exception:
            pass


if __name__ == "__main__":
    sys.exit(main())
