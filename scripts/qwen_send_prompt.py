"""
qwen_send_prompt.py — отправка промпта в текущую вкладку chat.qwen.ai (Edge debug-порт 9222).

Использование (Агент-3, конвейер HeatLossRevit2):
    python scripts/qwen_send_prompt.py --file "Tasks\\Конвейер\\Браузер\\_история\\prompt_*.md"

Формат файла задания (конвейер):
    строка 1   — путь сохранения ответа (не отправляется);
    строка 2-3 — служебные/пустые (не отправляются);
    строки 4+  — текст промпта для Qwen.

Что делает:
  1. Убирает блокирующий оверлей `.page-loading` (z-index 49, pointer-events: auto),
     который перехватывает клики и ломает React-ввод (найдено 2026-08-06).
  2. Находит настоящий textarea.message-input-textarea (НЕ скрытые .ime-text-area).
  3. Вставляет промпт через JS nativeSetter + input/change события (проверенный путь).
  4. Отправляет: кнопка button.send-button (не disabled) или Enter.
  5. Проверяет очистку поля; при неудаче — ретрай Enter (до 2 раз).
  НЕ закрывает браузер (только webdriver-сессию).
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
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.edge.options import Options

from agent.clipboard import ClipboardManager


def parse_prompt_file(path):
    """Возвращает (dest_path, prompt_text) из файла задания конвейера."""
    lines = open(path, encoding="utf-8").read().splitlines()
    dest = lines[0].strip() if lines else ""
    prompt = "\n".join(lines[3:]).strip()
    return dest, prompt


def connect(port=9222):
    opts = Options()
    opts.add_experimental_option("debuggerAddress", f"127.0.0.1:{port}")
    opts.page_load_strategy = "eager"
    return webdriver.Edge(options=opts)


def remove_blocking_overlay(driver):
    """Убирает .page-loading оверлей, перехватывающий клики (z=49)."""
    driver.execute_script(
        """
        document.querySelectorAll('.page-loading').forEach(el => {
            el.style.pointerEvents = 'none';
            el.style.display = 'none';
        });
        """
    )
    time.sleep(0.4)


def find_textarea(driver):
    for el in driver.find_elements(By.CSS_SELECTOR, "textarea.message-input-textarea"):
        try:
            if el.is_displayed() and not el.get_attribute("readonly"):
                return el
        except Exception:
            continue
    return None


def insert_prompt(driver, ta, prompt):
    driver.execute_script(
        "arguments[0].focus(); arguments[0].scrollIntoView({block:'center'});", ta
    )
    time.sleep(0.3)
    driver.execute_script(
        """
        const el = arguments[0];
        const text = arguments[1];
        const proto = window.HTMLTextAreaElement.prototype;
        const nativeSetter = Object.getOwnPropertyDescriptor(proto, 'value').set;
        nativeSetter.call(el, text);
        el.dispatchEvent(new Event('input', { bubbles: true }));
        el.dispatchEvent(new Event('change', { bubbles: true }));
        """,
        ta,
        prompt,
    )
    time.sleep(0.6)


def field_value(driver, ta):
    return driver.execute_script("return arguments[0].value || '';", ta) or ""


def send(driver, ta):
    sent = False
    for sel in [
        "button.send-button:not([disabled])",
        "button[aria-label='Отправить']:not([disabled])",
        "button.send-button",
    ]:
        for btn in driver.find_elements(By.CSS_SELECTOR, sel):
            try:
                if btn.is_displayed():
                    driver.execute_script("arguments[0].click();", btn)
                    sent = True
                    break
            except Exception:
                continue
        if sent:
            break
    if not sent:
        ta.send_keys(Keys.RETURN)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Отправка промпта в chat.qwen.ai")
    ap.add_argument("--file", required=True, help="Файл задания конвейера (строка 1 = путь ответа)")
    ap.add_argument("--port", type=int, default=9222, help="Edge debug-порт (по умолчанию 9222)")
    ap.add_argument("--output-path", default="",
                    help="Если задан — печатает путь ответа (из строки 1) и завершает")
    args = ap.parse_args(argv)

    dest, prompt = parse_prompt_file(args.file)
    if args.output_path:
        print(dest)
        return 0
    if not prompt:
        print("ERROR: пустой промпт в", args.file)
        return 1

    driver = connect(args.port)
    try:
        print("URL:", driver.current_url)
        remove_blocking_overlay(driver)
        ta = find_textarea(driver)
        if ta is None:
            print("ERROR: textarea.message-input-textarea не найдена")
            return 1

        insert_prompt(driver, ta, prompt)
        val = field_value(driver, ta)
        print(f"inserted len: {len(val)} expected: {len(prompt)}")

        send(driver, ta)
        time.sleep(2.5)
        after = field_value(driver, ta)
        print("field after send empty:", after == "")
        if after != "":
            print("RETRY send (поле не очистилось)...")
            ta.send_keys(Keys.RETURN)
            time.sleep(2.5)
            after2 = field_value(driver, ta)
            print("after retry empty:", after2 == "")
            if after2 != "":
                print("ERROR: поле не очистилось, сообщение могло не уйти")
                return 2
        print("OK: промпт отправлен. Путь ответа:", dest or "(не указан)")
        return 0
    finally:
        try:
            driver.quit()
        except Exception:
            pass


if __name__ == "__main__":
    sys.exit(main())
