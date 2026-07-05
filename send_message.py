# send_message.py – отправка сообщения в DeepSeek через Selenium, возврат полного ответа
# Использует буфер обмена для надёжной вставки многострочного текста.

import sys
import io
import time
import subprocess
import tempfile
from selenium import webdriver
from selenium.webdriver.edge.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.action_chains import ActionChains
from selenium.common.exceptions import StaleElementReferenceException, TimeoutException, NoSuchElementException

# Кодировка
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')
sys.stdin = io.TextIOWrapper(sys.stdin.buffer, encoding='utf-8')

try:
    import config
    STABLE_TIMEOUT = getattr(config, 'STREAM_STABLE_TIMEOUT', 30)
    STABLE_DURATION = getattr(config, 'STREAM_STABLE_DURATION', 2.0)
    CHECK_INTERVAL = getattr(config, 'STREAM_CHECK_INTERVAL', 0.5)
except ImportError:
    STABLE_TIMEOUT = 30
    STABLE_DURATION = 2.0
    CHECK_INTERVAL = 0.5

def set_clipboard(text):
    """Устанавливает текст в буфер обмена Windows с использованием PowerShell."""
    # Экранируем кавычки и специальные символы
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
                messages = driver.find_elements(By.XPATH, ".//div[contains(@class, 'message') and contains(@class, 'assistant')]")
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
            # Найти поле ввода
            input_box = WebDriverWait(driver, 15).until(
                EC.presence_of_element_located((By.CSS_SELECTOR,
                    "textarea[placeholder*='Ask'], textarea._27c9245, textarea"))
            )
            driver.execute_script("arguments[0].scrollIntoView(true);", input_box)
            time.sleep(0.5)

            # Устанавливаем текст в буфер обмена
            set_clipboard(message)

            # Кликаем в поле и отправляем Ctrl+V (вставка)
            input_box.click()
            # Очищаем поле (на случай, если там что-то есть)
            input_box.clear()
            time.sleep(0.2)
            # Вставка через Ctrl+V
            ActionChains(driver).key_down(Keys.CONTROL).send_keys('v').key_up(Keys.CONTROL).perform()
            time.sleep(0.5)

            # Проверяем, что текст действительно вставился
            inserted = driver.execute_script("return arguments[0].value;", input_box)
            if not inserted or len(inserted) < len(message) // 2:  # если текст не вставился полностью
                sys.stderr.write("WARNING: Вставка через Ctrl+V не сработала, пробуем send_keys.\n")
                input_box.clear()
                input_box.send_keys(message)

            # Запоминаем количество кнопок "Копировать"
            copy_buttons = driver.find_elements(By.CSS_SELECTOR, "span.ds-button__content span.code-info-button-text")
            count_before = len(copy_buttons)

            # Отправка: ищем кнопку отправки
            send_button = None
            selectors_button = [
                "button[type='submit']",
                "button[aria-label*='Send' i]",
                "button[aria-label*='Отправить' i]",
                "button.send",
                "button[class*='send']",
                "button[class*='submit']"
            ]
            for selector in selectors_button:
                try:
                    send_button = driver.find_element(By.CSS_SELECTOR, selector)
                    if send_button.is_enabled():
                        break
                except:
                    continue
            if send_button and send_button.is_enabled():
                send_button.click()
            else:
                # Имитация Enter через ActionChains (без разбивки)
                ActionChains(driver).send_keys(Keys.RETURN).perform()

            # Ожидание увеличения кнопок "Копировать"
            def copy_count_increased(driver):
                current = driver.find_elements(By.CSS_SELECTOR, "span.ds-button__content span.code-info-button-text")
                return len(current) > count_before

            try:
                WebDriverWait(driver, 120).until(copy_count_increased)
            except TimeoutException:
                sys.stderr.write("ERROR: Таймаут ожидания новой кнопки 'Копировать'.\n")
                return None

            # Найти последнее сообщение ассистента
            messages = driver.find_elements(By.XPATH, ".//div[contains(@class, 'message') and contains(@class, 'assistant')]")
            if not messages:
                sys.stderr.write("ERROR: Не найдено сообщений ассистента.\n")
                return None
            parent = messages[-1]

            if not wait_for_text_stabilization(driver, parent):
                sys.stderr.write("WARNING: Текст не стабилизировался за отведённое время.\n")

            try:
                full_text = parent.text.strip()
            except StaleElementReferenceException:
                messages = driver.find_elements(By.XPATH, ".//div[contains(@class, 'message') and contains(@class, 'assistant')]")
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

def main():
    if len(sys.argv) > 1:
        message = " ".join(sys.argv[1:])
    else:
        message = sys.stdin.read().strip()
        if not message:
            message = "Привет! Расскажи, как дела?"

    options = Options()
    options.add_experimental_option("debuggerAddress", "127.0.0.1:9222")

    try:
        driver = webdriver.Edge(options=options)
    except Exception as e:
        sys.stderr.write(f"ERROR: Не удалось подключиться к браузеру: {e}\n")
        sys.exit(1)

    if driver.window_handles:
        driver.switch_to.window(driver.window_handles[0])
    driver.execute_script("window.focus();")

    try:
        WebDriverWait(driver, 15).until(EC.presence_of_element_located((By.TAG_NAME, "body")))
    except TimeoutException:
        sys.stderr.write("ERROR: Страница не загрузилась за 15 секунд.\n")
        driver.quit()
        sys.exit(1)

    result = send_message_with_retries(driver, message)
    driver.quit()

    if result is not None:
        print(result)
    else:
        sys.exit(1)

if __name__ == "__main__":
    main()