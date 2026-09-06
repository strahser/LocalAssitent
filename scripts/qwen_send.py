"""
Отправка текстового промпта в чат Qwen через attached Edge (CDP 127.0.0.1:9222).

Вставляет текст из файла в поле ввода (нативный setter + input event для React)
и эмулирует Enter. Проверяет, что сообщение ушло (поле очистилось, текст виден в чате).

  python scripts\\qwen_send.py --text-file d:\\Projects\\Demiurges\\QWEN_ORDER_battlefield.txt
  python scripts\\qwen_send.py --text-file prompt.txt --tab chat.qwen.ai --no-verify
"""
import argparse
import sys
import time

from selenium import webdriver
from selenium.common.exceptions import NoSuchElementException, WebDriverException
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys


def build_parser():
    p = argparse.ArgumentParser(description="Send text prompt to Qwen chat via attached Edge")
    p.add_argument("--text-file", required=True, help="Файл с текстом запроса")
    p.add_argument("--port", type=int, default=9222)
    p.add_argument("--tab", default="chat.qwen.ai", help="Подстрока URL вкладки чата")
    p.add_argument("--timeout", type=int, default=30, help="Секунды ожидания подтверждения")
    p.add_argument("--no-verify", action="store_true")
    return p


def find_qwen_tab(d, needle):
    for h in d.window_handles:
        d.switch_to.window(h)
        if needle in (d.current_url or ""):
            return True
    return False


def find_input(d):
    for css in ("textarea", "div[contenteditable=true]", "[role=textbox]"):
        try:
            for el in d.find_elements(By.CSS_SELECTOR, css):
                if el.is_displayed() and el.size.get("width", 0) > 100:
                    return el
        except WebDriverException:
            continue
    raise NoSuchElementException("поле ввода чата не найдено")


def paste(d, el, text):
    d.execute_script(
        """const el=arguments[0], text=arguments[1];
        el.focus();
        const proto = el.tagName==='TEXTAREA'
          ? window.HTMLTextAreaElement.prototype : window.HTMLInputElement.prototype;
        const setter = Object.getOwnPropertyDescriptor(proto, 'value').set;
        if (setter) setter.call(el, text); else el.value = text;
        el.dispatchEvent(new Event('input', {bubbles:true}));
        el.dispatchEvent(new Event('change', {bubbles:true}));""",
        el, text,
    )


def main():
    a = build_parser().parse_args()
    with open(a.text_file, encoding="utf-8") as f:
        text = f.read().strip()
    if not text:
        print("пустой запрос, нечего отправлять")
        return 2

    o = webdriver.EdgeOptions()
    o.add_experimental_option("debuggerAddress", f"127.0.0.1:{a.port}")
    d = webdriver.Edge(options=o)
    try:
        if not find_qwen_tab(d, a.tab):
            print(f"вкладка с {a.tab!r} не найдена")
            return 3
        el = find_input(d)
        paste(d, el, text)
        time.sleep(0.7)
        el.send_keys(Keys.ENTER)
        print("enter отправлен")
        if a.no_verify:
            return 0
        snippet = text[:40].replace("\n", " ")
        t0 = time.time()
        while time.time() - t0 < a.timeout:
            time.sleep(1.5)
            try:
                body = d.execute_script("return document.body.innerText || '';")
                cleared = d.execute_script(
                    "const t=document.querySelector('textarea');"
                    "return t ? t.value.length : -1;")
            except WebDriverException:
                continue
            if snippet[:20] in body and cleared == 0:
                print("OK: сообщение ушло в чат")
                return 0
        print("WARN: подтверждение не получено (проверь вкладку вручную)")
        return 4
    finally:
        d.quit()


if __name__ == "__main__":
    sys.exit(main())
