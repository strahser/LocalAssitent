import sys
import io
import time
import subprocess
import argparse
from selenium import webdriver
from selenium.webdriver.edge.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.action_chains import ActionChains
from selenium.common.exceptions import StaleElementReferenceException, TimeoutException

try:
    import config
    from selectors import SELECTORS
except ImportError:
    SELECTORS = {
        "input_textarea": "textarea[placeholder*='Ask']",
        "send_button": "button[type='submit']",
        "copy_button": "span.code-info-button-text",
        "new_chat_xpath": "//span[text()='New chat']",
        "assistant_messages": ".//div[contains(@class, 'message') and contains(@class, 'assistant')]",
    }
    class config:
        STREAM_STABLE_TIMEOUT = 30
        STREAM_STABLE_DURATION = 2.0
        STREAM_CHECK_INTERVAL = 0.5

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')
sys.stdin = io.TextIOWrapper(sys.stdin.buffer, encoding='utf-8')

STABLE_TIMEOUT = getattr(config, 'STREAM_STABLE_TIMEOUT', 30)
STABLE_DURATION = getattr(config, 'STREAM_STABLE_DURATION', 2.0)
CHECK_INTERVAL = getattr(config, 'STREAM_CHECK_INTERVAL', 0.5)

def set_clipboard(text):
    escaped = text.replace('"', '\\"').replace('`', '``')
    ps_command = f'Set-Clipboard -Value "{escaped}"'
    subprocess.run(["powershell", "-Command", ps_command], check=True)

def wait_for_text_stabilization(driver, parent_element, timeout=STABLE_TIMEOUT,
                                stable_duration=STABLE_DURATION,
                                check_interval=CHECK_INTERVAL):
    start_time = time.time()
    stable_counter = 0.0
    last_text = None
    while time.time() - start_time < timeout:
        try:
            current_text = parent_element.text
        except StaleElementReferenceException:
            try:
                messages = driver.find_elements(By.XPATH, SELECTORS["assistant_messages"])
                if messages:
                    parent_element = messages[-1]
                    current_text = parent_element.text
                else:
                    return False
            except:
                return False
        if last_text is None:
            last_text = current_text
            time.sleep(check_interval)
            continue
        if current_text == last_text:
            stable_counter += check_interval
        else:
            stable_counter = 0.0
            last_text = current_text
        if stable_counter >= stable_duration:
            return True
        time.sleep(check_interval)
    return False

def send_message_with_retries(driver, message, max_retries=3):
    for attempt in range(max_retries):
        try:
            input_box = WebDriverWait(driver, 15).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, SELECTORS["input_textarea"]))
            )
            driver.execute_script("arguments[0].scrollIntoView(true);", input_box)
            time.sleep(0.5)

            set_clipboard(message)
            input_box.click()
            input_box.clear()
            time.sleep(0.2)
            ActionChains(driver).key_down(Keys.CONTROL).send_keys('v').key_up(Keys.CONTROL).perform()
            time.sleep(0.5)

            inserted = driver.execute_script("return arguments[0].value;", input_box)
            if not inserted or len(inserted) < len(message) // 2:
                sys.stderr.write("WARNING: Вставка через Ctrl+V не сработала, пробуем send_keys.\n")
                input_box.clear()
                input_box.send_keys(message)

            copy_buttons = driver.find_elements(By.CSS_SELECTOR, SELECTORS["copy_button"])
            count_before = len(copy_buttons)

            send_selector = SELECTORS.get("send_button", "button[type='submit']")
            try:
                send_button = driver.find_element(By.CSS_SELECTOR, send_selector)
                if send_button.is_enabled():
                    send_button.click()
                else:
                    raise Exception("Send button not enabled")
            except:
                ActionChains(driver).send_keys(Keys.RETURN).perform()

            def copy_count_increased(driver):
                current = driver.find_elements(By.CSS_SELECTOR, SELECTORS["copy_button"])
                return len(current) > count_before

            try:
                WebDriverWait(driver, 120).until(copy_count_increased)
            except TimeoutException:
                sys.stderr.write("ERROR: Таймаут ожидания новой кнопки 'Копировать'.\n")
                return None

            messages = driver.find_elements(By.XPATH, SELECTORS["assistant_messages"])
            if not messages:
                sys.stderr.write("ERROR: Не найдено сообщений ассистента.\n")
                return None
            parent = messages[-1]

            if not wait_for_text_stabilization(driver, parent):
                sys.stderr.write("WARNING: Текст не стабилизировался за отведённое время.\n")

            try:
                full_text = parent.text.strip()
            except StaleElementReferenceException:
                messages = driver.find_elements(By.XPATH, SELECTORS["assistant_messages"])
                if messages:
                    parent = messages[-1]
                    full_text = parent.text.strip()
                else:
                    sys.stderr.write("ERROR: Не удалось получить текст ответа.\n")
                    return None

            if not full_text:
                sys.stderr.write("ERROR: Текст ответа пуст.\n")
                return None

            return full_text

        except StaleElementReferenceException as e:
            sys.stderr.write(f"⚠️ StaleElementReferenceException (попытка {attempt+1}/{max_retries}): {e}\n")
            time.sleep(1)
            continue
        except Exception as e:
            sys.stderr.write(f"⚠️ Ошибка (попытка {attempt+1}/{max_retries}): {e}\n")
            time.sleep(1)
            continue

    sys.stderr.write("ERROR: Не удалось получить ответ после нескольких попыток.\n")
    return None

def click_new_chat(driver):
    try:
        new_chat_btn = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.XPATH, SELECTORS["new_chat_xpath"]))
        )
        new_chat_btn.click()
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, SELECTORS["input_textarea"]))
        )
        return True
    except Exception as e:
        sys.stderr.write(f"ERROR: Не удалось создать новый чат: {e}\n")
        return False

def get_last_assistant_response(driver):
    try:
        messages = driver.find_elements(By.XPATH, SELECTORS["assistant_messages"])
        if not messages:
            return None
        last = messages[-1]
        return last.text.strip()
    except Exception as e:
        sys.stderr.write(f"ERROR: Не удалось получить последний ответ: {e}\n")
        return None

# Основные функции для вызова из других модулей
def send_message(message, max_retries=3):
    options = Options()
    options.add_experimental_option("debuggerAddress", "127.0.0.1:9222")
    try:
        driver = webdriver.Edge(options=options)
    except Exception as e:
        sys.stderr.write(f"ERROR: Не удалось подключиться к браузеру: {e}\n")
        return None

    if driver.window_handles:
        driver.switch_to.window(driver.window_handles[0])
    driver.execute_script("window.focus();")

    try:
        WebDriverWait(driver, 15).until(EC.presence_of_element_located((By.TAG_NAME, "body")))
    except TimeoutException:
        sys.stderr.write("ERROR: Страница не загрузилась за 15 секунд.\n")
        driver.quit()
        return None

    result = send_message_with_retries(driver, message, max_retries)
    driver.quit()
    return result

def new_chat():
    options = Options()
    options.add_experimental_option("debuggerAddress", "127.0.0.1:9222")
    try:
        driver = webdriver.Edge(options=options)
    except Exception as e:
        sys.stderr.write(f"ERROR: Не удалось подключиться к браузеру: {e}\n")
        return False

    if driver.window_handles:
        driver.switch_to.window(driver.window_handles[0])
    driver.execute_script("window.focus();")

    try:
        WebDriverWait(driver, 15).until(EC.presence_of_element_located((By.TAG_NAME, "body")))
    except TimeoutException:
        sys.stderr.write("ERROR: Страница не загрузилась за 15 секунд.\n")
        driver.quit()
        return False

    success = click_new_chat(driver)
    driver.quit()
    return success

def copy_last_response():
    options = Options()
    options.add_experimental_option("debuggerAddress", "127.0.0.1:9222")
    try:
        driver = webdriver.Edge(options=options)
    except Exception as e:
        sys.stderr.write(f"ERROR: Не удалось подключиться к браузеру: {e}\n")
        return None

    if driver.window_handles:
        driver.switch_to.window(driver.window_handles[0])
    driver.execute_script("window.focus();")

    try:
        WebDriverWait(driver, 15).until(EC.presence_of_element_located((By.TAG_NAME, "body")))
    except TimeoutException:
        sys.stderr.write("ERROR: Страница не загрузилась за 15 секунд.\n")
        driver.quit()
        return None

    result = get_last_assistant_response(driver)
    driver.quit()
    return result

# Если скрипт запущен напрямую — обрабатываем аргументы командной строки
def main():
    # Для обратной совместимости сохраняем поддержку --new-chat и --copy
    if len(sys.argv) > 1 and sys.argv[1] == "--new-chat":
        success = new_chat()
        sys.exit(0 if success else 1)
    elif len(sys.argv) > 1 and sys.argv[1] == "--copy":
        result = copy_last_response()
        if result is not None:
            print(result)
            sys.exit(0)
        else:
            sys.exit(1)
    else:
        # Если аргументов нет или передан --send (по умолчанию), читаем stdin
        message = sys.stdin.read().strip()
        if not message:
            message = "Привет! Расскажи, как дела?"
        result = send_message(message)
        if result is not None:
            print(result)
            sys.exit(0)
        else:
            sys.exit(1)

if __name__ == "__main__":
    main()