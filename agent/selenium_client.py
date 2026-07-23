import os
import subprocess
import time
from typing import Optional, List, Tuple

from selenium import webdriver
from selenium.common.exceptions import TimeoutException, StaleElementReferenceException, InvalidSessionIdException
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.remote.webelement import WebElement
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.edge.options import Options

from detection.action_panel_finder import ActionPanelFinder
from agent.auth import DeepSeekAuth
from agent.clipboard_manager import ClipboardManager
from detection.element_finder import ElementFinder
from detection.response_ready_strategy import ResponseReadyStrategyFactory


class SeleniumDeepSeekClient:
    def __init__(self, logger, config):
        self.logger = logger
        self.config = config
        self.driver = None
        self.clipboard = ClipboardManager()
        self.finder = None
        self.panel_finder = None
        self._email = ""
        self._password = ""
        self._connect()

    def set_auth_credentials(self, email: str, password: str):
        self._email = email
        self._password = password

    def _find_edge_exe(self):
        candidates = [
            "C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe",
            "C:\\Program Files\\Microsoft\\Edge\\Application\\msedge.exe",
        ]
        for p in candidates:
            if os.path.exists(p):
                return p
        return "msedge.exe"

    def _check_port(self, port):
        import socket
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.connect(("127.0.0.1", port))
                return True
            except:
                return False

    def _start_edge_debug_mode(self):
        port = self.config.debug_port

        if self._check_port(port):
            self.logger.log(f"Edge уже запущен на порту {port}.")
            return

        user_dir = self.config.edge_user_data_dir
        edge_exe = self._find_edge_exe()

        os.makedirs(user_dir, exist_ok=True)

        cmd = [
            edge_exe,
            f"--user-data-dir={user_dir}",
            f"--remote-debugging-port={port}",
            "--no-first-run",
            "--no-default-browser-check",
            "--disable-sync",
            "--disable-search-engine-choice-screen",
            self.config.deepseek_url,
        ]
        self.logger.log(f"🚀 Запуск Edge (порт {port})...")
        subprocess.Popen(cmd, shell=False)

        for i in range(20):
            time.sleep(1)
            if self._check_port(port):
                self.logger.log(f"Edge запущен на порту {port}.")
                return

        self.logger.log("❌ Edge не запустился за 20 секунд.", "ERROR")
        raise RuntimeError("Edge не запустился")

    def _connect(self):
        self._start_edge_debug_mode()

        try:
            options = Options()
            options.add_experimental_option("debuggerAddress", f"127.0.0.1:{self.config.debug_port}")
            options.page_load_strategy = "eager"
            self.driver = webdriver.Edge(options=options)
        except Exception as e:
            self.logger.log(f"Не удалось подключиться к Edge: {e}", "ERROR")
            raise

        self.logger.log("Edge подключён (debug mode).")

        try:
            WebDriverWait(self.driver, 15).until(EC.presence_of_element_located((By.TAG_NAME, "body")))
        except TimeoutException:
            self.logger.log("Страница не загрузилась за 15 секунд.", "ERROR")
            self.driver.quit()
            raise

        self.logger.log(f"Подключено к браузеру. Текущий URL: {self.driver.current_url}")

        auth = DeepSeekAuth(self.driver, self.logger)
        logged_in = auth.ensure_logged_in(
            email=self._email,
            password=self._password,
            timeout=120
        )

        if not logged_in:
            self.logger.log("Could not log in.", "ERROR")

        self.finder = ElementFinder(self.driver, self.logger, self.config.selectors)
        self.panel_finder = ActionPanelFinder(self.driver, self.config, logger=self.logger)

    # ──────────────────────────────
    #  Внутренние методы
    # ──────────────────────────────

    def _get_assistant_messages(self) -> List[WebElement]:
        return self.finder.find_assistant_messages()

    def _wait_for_input_box(self, timeout=15) -> Optional[WebElement]:
        return self.finder.find_input_box(timeout=timeout)

    def _get_input_value(self, element: WebElement) -> str:
        try:
            val = self.driver.execute_script(
                "return arguments[0].value || arguments[0].textContent || '';", element
            )
            return val or ""
        except:
            return ""

    def _insert_text(self, input_box: WebElement, message: str) -> bool:
        self.logger.log("📋 Вставка текста (React-compatible)...")
        try:
            tag = self.driver.execute_script("return arguments[0].tagName + '.' + (arguments[0].className || '');", input_box)
            self.logger.log(f"🔍 input_box: {tag}")

            input_box.click()
            time.sleep(0.3)
            input_box.clear()
            time.sleep(0.2)

            self.driver.execute_script("""
                const el = arguments[0];
                const text = arguments[1];
                const nativeSetter = Object.getOwnPropertyDescriptor(
                    window.HTMLTextAreaElement.prototype, 'value'
                ).set;
                nativeSetter.call(el, text);
                el.dispatchEvent(new Event('input', { bubbles: true }));
                el.dispatchEvent(new Event('change', { bubbles: true }));
            """, input_box, message)
            time.sleep(1)

            inserted = self._get_input_value(input_box)
            if inserted and len(inserted) >= len(message) // 2:
                self.logger.log(f"✅ Текст вставлен через nativeSetter (длина {len(inserted)}).")
                return True

            self.logger.log("⚠️ nativeSetter не сработал, пробуем send_keys.", "WARNING")
            input_box.send_keys(message)
            time.sleep(1)
            inserted = self._get_input_value(input_box)
            if inserted and len(inserted) >= len(message) // 2:
                self.logger.log(f"✅ Текст вставлен через send_keys (длина {len(inserted)}).")
                return True

            self.logger.log("❌ Не удалось вставить текст.", "ERROR")
            return False
        except Exception as e:
            self.logger.log(f"❌ Ошибка вставки текста: {e}", "ERROR")
            return False
    def _click_send_button(self) -> bool:
        selectors = [
            "div.ds-button--circle:not(.ds-button--disabled)",
            "button.ds-button--filled:not(.ds-button--disabled)",
            "div[role='button'].ds-button--primary:not(.ds-button--disabled)",
            "//div[contains(@class, 'ds-button--circle') and not(contains(@class, 'ds-button--disabled'))]",
        ]
        for sel in selectors:
            try:
                if sel.startswith("//"):
                    els = self.driver.find_elements(By.XPATH, sel)
                else:
                    els = self.driver.find_elements(By.CSS_SELECTOR, sel)
                for btn in els:
                    if btn.is_displayed():
                        btn.click()
                        self.logger.log(f"✅ Клик по кнопке: {sel}")
                        return True
            except:
                pass
        return False

    def _send_message(self, input_box: WebElement) -> bool:
        for attempt in range(3):
            try:
                self.logger.log("📤 Отправка через Enter...")
                input_box.send_keys(Keys.RETURN)
                time.sleep(1.5)
                new_text = self._get_input_value(input_box)
                if new_text == "":
                    self.logger.log("✅ Поле очистилось, запрос принят.")
                    return True
            except Exception as e:
                self.logger.log(f"⚠️ Enter error: {e}", "WARNING")

            self.logger.log("📤 Попытка клика по кнопке отправки...")
            try:
                if self._click_send_button():
                    time.sleep(1.5)
                    new_text = self._get_input_value(input_box)
                    if new_text == "":
                        return True
                    self.logger.log("⚠️ Поле не очистилось после клика.", "WARNING")
                else:
                    self.logger.log("❌ Кнопка отправки не найдена.", "ERROR")
            except Exception as e:
                self.logger.log(f"❌ Ошибка при клике: {e}", "ERROR")

        self.logger.log("❌ Не удалось отправить после нескольких попыток.", "ERROR")
        return False

    def _wait_for_new_message(self, old_count: int, timeout: int) -> Optional[WebElement]:
        self.logger.log(f"⏳ Ожидание нового сообщения (текущее: {old_count})...")
        start = time.time()
        last_log_time = start
        while time.time() - start < timeout:
            if time.time() - last_log_time >= 5:
                self.logger.log(f"🔍 Кнопка отправки: {self._get_send_button_state()}")
                self.logger.log(f"🔍 Сообщений: {len(self._get_assistant_messages())}")
                last_log_time = time.time()

            messages = self._get_assistant_messages()
            if len(messages) > old_count:
                self.logger.log(f"✅ Новое сообщение! Всего: {len(messages)}.")
                return messages[-1]

            try:
                errors = self.finder.find_error_elements()
                if errors:
                    self.logger.log(f"⚠️ Ошибка на странице: {errors[0].text[:200]}", "WARNING")
            except:
                pass

            time.sleep(0.5)

        self.logger.log(f"❌ Таймаут ожидания нового сообщения ({timeout} сек).", "ERROR")
        return None

    def _get_send_button_state(self) -> str:
        try:
            buttons = self.driver.find_elements(By.CSS_SELECTOR, "div[role='button']")
            for btn in buttons:
                classes = btn.get_attribute("class") or ""
                if "ds-button--circle" in classes:
                    return "disabled" if "ds-button--disabled" in classes else "enabled"
            return "not found"
        except Exception as e:
            return f"error: {e}"

    def _wait_for_response_ready(self, message_element: WebElement, timeout: int) -> bool:
        self.logger.log(f"⏳ Ожидание готовности ответа (стратегия: {self.config.response_strategy})...")
        strategy = ResponseReadyStrategyFactory.get_strategy(
            self.config.response_strategy,
            logger=self.logger,
            check_interval=self.config.check_interval,
            stable_duration=self.config.stable_duration,
            debug_interval=2.0
        )
        ready, reason = strategy.wait(self.driver, message_element, timeout)
        if ready:
            self.logger.log(f"✅ Ответ готов (триггер: {reason}).")
        else:
            self.logger.log(f"⚠️ Стратегия не подтвердила готовность за {timeout} сек. Причина: {reason}", "WARNING")
        return ready

    def _get_last_message_text(self, fallback_retries=2) -> Optional[str]:
        for attempt in range(fallback_retries):
            try:
                messages = self._get_assistant_messages()
                if not messages:
                    self.logger.log("❌ Нет сообщений ассистента.", "ERROR")
                    return None
                text = messages[-1].text.strip()
                if text:
                    self.logger.log(f"✅ Текст получен (длина {len(text)} символов).")
                    return text
                else:
                    self.logger.log("⚠️ Текст пустой, повтор...", "WARNING")
                    time.sleep(0.5)
            except StaleElementReferenceException:
                self.logger.log("⚠️ Элемент устарел, повтор...", "WARNING")
                time.sleep(0.5)
        self.logger.log("❌ Не удалось получить текст сообщения.", "ERROR")
        return None

    # ──────────────────────────────
    #  Копирование кода из блоков кода
    # ──────────────────────────────

    def _copy_last_code_block(self, message_element: WebElement) -> Optional[str]:
        """
        Находит последний блок кода внутри сообщения и копирует его.
        Сначала пытается через кнопку Copy, затем через <pre>.text.
        """
        code_blocks = self.finder.find_code_blocks(message_element)
        if not code_blocks:
            self.logger.log("⚠️ Блоки кода не найдены в сообщении.")
            return None

        last_block = code_blocks[-1]
        self.logger.log(f"🔍 Копирование последнего блока кода ({len(code_blocks)} всего)...")

        copy_btn = self.finder.find_code_copy_button(last_block)
        if copy_btn:
            self.logger.log("✅ Кнопка Copy в блоке кода найдена. Нажимаем...")
            try:
                ActionChains(self.driver).move_to_element(copy_btn).perform()
                time.sleep(0.2)
                self.driver.execute_script("arguments[0].scrollIntoView(true);", copy_btn)
                time.sleep(0.2)
                copy_btn.click()
                time.sleep(0.5)

                clipboard_text = self.clipboard.get_text()
                if clipboard_text:
                    self.logger.log(f"✅ Код скопирован через кнопку (длина {len(clipboard_text)}).")
                    return clipboard_text

                self.logger.log("⚠️ Буфер пуст после клика, пробуем JS-клик...", "WARNING")
                self.driver.execute_script("arguments[0].click();", copy_btn)
                time.sleep(0.5)
                clipboard_text = self.clipboard.get_text()
                if clipboard_text:
                    self.logger.log(f"✅ Код скопирован через JS-клик (длина {len(clipboard_text)}).")
                    return clipboard_text
            except Exception as e:
                self.logger.log(f"⚠️ Ошибка при клике по кнопке Copy: {e}", "WARNING")

        code_text = self.finder.get_code_text_from_pre(last_block)
        if code_text:
            self.logger.log(f"✅ Код прочитан из <pre> (длина {len(code_text)}).")
            return code_text

        self.logger.log("❌ Не удалось скопировать код ни одним способом.", "ERROR")
        return None

    def _copy_response_via_button(self, message_element: WebElement) -> Optional[str]:
        self.logger.log("🔍 Поиск кнопки копирования сообщения...")
        try:
            ActionChains(self.driver).move_to_element(message_element).perform()
            time.sleep(0.3)
        except Exception as e:
            self.logger.log(f"Ошибка при наведении: {e}", "WARNING")

        copy_btn = self.finder.find_copy_button_in_message(message_element)
        if not copy_btn:
            self.logger.log("❌ Кнопка копирования сообщения не найдена.", "ERROR")
            return None

        if copy_btn.is_displayed() and copy_btn.is_enabled():
            self.logger.log("✅ Кнопка Копировать сообщения найдена и активна.")
            self.driver.execute_script("arguments[0].scrollIntoView(true);", copy_btn)
            time.sleep(0.2)
            copy_btn.click()
            time.sleep(0.5)

            clipboard_text = self.clipboard.get_text()
            if clipboard_text:
                return self._clean_copied_text(clipboard_text)
            else:
                self.logger.log("⚠️ Буфер пуст после клика, пробуем JS...", "WARNING")
                try:
                    self.driver.execute_script("arguments[0].click();", copy_btn)
                    time.sleep(0.5)
                    clipboard_text = self.clipboard.get_text()
                    if clipboard_text:
                        return self._clean_copied_text(clipboard_text)
                except Exception as e:
                    self.logger.log(f"❌ Повторный клик через JS не удался: {e}", "WARNING")
                return None
        else:
            self.logger.log("❌ Кнопка неактивна/невидима.", "ERROR")
            return None

    def _clean_copied_text(self, text: str) -> str:
        lines = text.splitlines()
        cleaned = []
        for line in lines:
            stripped = line.strip()
            if stripped in ("Копировать", "Скачать", "Copy", "Download", "python", "bash", "cmd"):
                continue
            cleaned.append(line)
        return "\n".join(cleaned)

    # ──────────────────────────────
    #  Прикрепление файлов
    # ──────────────────────────────

    def _resolve_file_paths(self, file_paths: List[str]) -> List[str]:
        base = os.path.dirname(os.path.abspath(__file__))
        resolved = []
        for f in file_paths:
            abs_cwd = os.path.abspath(f)
            if os.path.exists(abs_cwd):
                resolved.append(abs_cwd)
                continue
            abs_base = os.path.join(base, f)
            if os.path.exists(abs_base):
                resolved.append(abs_base)
                continue
            self.logger.log(f"⚠️ Файл не найден: {f}", "WARNING")
        return resolved

    def attach_files(self, file_paths: List[str]) -> bool:
        if not file_paths:
            self.logger.log("⚠️ Список файлов пуст.")
            return True

        abs_paths = self._resolve_file_paths(file_paths)
        if not abs_paths:
            self.logger.log("❌ Ни один из указанных файлов не найден.", "ERROR")
            return False
        if len(abs_paths) < len(file_paths):
            self.logger.log(f"⚠️ {len(file_paths) - len(abs_paths)} файлов не найдено, пропущены.", "WARNING")

        self.logger.log(f"📎 Прикрепление {len(abs_paths)} файлов...")

        file_input = self.finder.find_file_input()
        if file_input:
            self.logger.log(f"✅ Найден input[type='file'], отправляем пути...")
            try:
                self.driver.execute_script(
                    "arguments[0].style.display = 'block'; arguments[0].style.visibility = 'visible';",
                    file_input
                )
                time.sleep(0.2)
                file_input.send_keys("\n".join(abs_paths))
                time.sleep(2)
                self.logger.log("✅ Файлы отправлены через input[type='file'].")
                return True
            except Exception as e:
                self.logger.log(f"⚠️ Ошибка отправки через input[type='file']: {e}", "WARNING")

        self.logger.log("🔄 Пробуем через клик по кнопке аттача...")
        attach_btn = self.finder.find_attach_button()
        if attach_btn:
            try:
                attach_btn.click()
                time.sleep(1)
                file_input = self.finder.find_file_input()
                if file_input:
                    self.driver.execute_script(
                        "arguments[0].style.display = 'block'; arguments[0].style.visibility = 'visible';",
                        file_input
                    )
                    file_input.send_keys("\n".join(abs_paths))
                    time.sleep(2)
                    self.logger.log("✅ Файлы прикреплены после клика по кнопке.")
                    return True
                else:
                    self.logger.log("⚠️ input[type='file'] не появился после клика.", "WARNING")
                    return False
            except Exception as e:
                self.logger.log(f"❌ Ошибка при клике по кнопке аттача: {e}", "ERROR")
                return False
        else:
            self.logger.log("❌ Кнопка аттача не найдена.", "ERROR")
            return False

    # ──────────────────────────────
    #  Основной метод отправки
    # ──────────────────────────────

    def send_message(self, message: str) -> Optional[Tuple[str, Optional[str]]]:
        """
        Отправляет сообщение и возвращает (full_text, code_text).
        full_text — полный текст ответа (через копирование сообщения).
        code_text — код из последнего блока кода (или None, если нет кода).
        """
        self.logger.log("📤 Отправка запроса в DeepSeek...")
        messages_before = self._get_assistant_messages()
        count_before = len(messages_before)
        self.logger.log(f"До отправки: {count_before} сообщений ассистента.")

        input_box = self._wait_for_input_box()
        if not input_box:
            return None

        if not self._insert_text(input_box, message):
            return None

        if not self._send_message(input_box):
            return None

        new_message = self._wait_for_new_message(count_before, self.config.selenium_timeout)
        if not new_message:
            return None

        ready = self._wait_for_response_ready(new_message, self.config.stable_timeout)
        if not ready:
            self.logger.log("⚠️ Ответ не подтверждён как готовый, но попытаемся скопировать.", "WARNING")

        full_text = None
        code_text = None

        full_text = self._copy_response_via_button(new_message)
        if full_text:
            self.logger.log("✅ Текст ответа скопирован через буфер обмена.")
        else:
            self.logger.log("⚠️ Не удалось скопировать через кнопку, используем .text", "WARNING")
            full_text = self._get_last_message_text()

        code_text = self._copy_last_code_block(new_message)

        if full_text:
            return (full_text, code_text)

        self.logger.log("❌ Не удалось получить текст ответа.", "ERROR")
        return None

    def send_prompt_legacy(self, message: str) -> Optional[str]:
        """Старый интерфейс для обратной совместимости — возвращает только текст."""
        result = self.send_message(message)
        if result is None:
            return None
        full_text, _ = result
        return full_text

    def new_chat(self):
        self.logger.log("🔄 Создание нового чата...")
        selectors = self.config.selectors.get("new_chat_xpath", [])
        if isinstance(selectors, str):
            selectors = [selectors]
        for xpath in selectors:
            try:
                elements = self.driver.find_elements(By.XPATH, xpath)
                if elements:
                    elements[0].click()
                    self.logger.log("✅ Новый чат создан.")
                    time.sleep(2)
                    return True
            except:
                pass
        self.logger.log("⚠️ Кнопка 'New chat' не найдена, просто переходим на страницу чата...")
        self.driver.get("https://chat.deepseek.com/a/chat")
        time.sleep(4)
        return True

    def close(self):
        if self.driver:
            self.driver.quit()
