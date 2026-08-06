"""
client.py — QwenClient: полный поток задачи в chat.qwen.ai.

Поток: открыть чат → загрузить файл drag-and-drop → зафиксировать получение
файла → отправить промпт → зафиксировать начало «думания» → дождаться
готовности ответа → скопировать ответ → сохранить в markdown.

Selenium импортируется лениво (внутри connect), agent.clipboard — внутри
extract_answer, чтобы модуль импортировался офлайн и в тестах без selenium.
"""
import os
import time

from qwen.dnd_uploader import DragAndDropUploader
from qwen.html_monitor import HtmlChangeMonitor, HtmlSnapshot
from qwen.selectors import QWEN_SELECTORS


class QwenClient:
    """Автоматизация chat.qwen.ai: файл → промпт → ответ."""

    def __init__(self, logger, driver=None, selectors: dict = None,
                 url: str = "https://chat.qwen.ai"):
        self.logger = logger
        self.driver = driver
        self.selectors = selectors if selectors is not None else QWEN_SELECTORS
        self.url = url
        self.monitor = None
        self._uploader = None
        self._owns_driver = False
        self._last_file_name = ""

    # === Подключение ===

    @staticmethod
    def _find_edge_exe() -> str:
        candidates = [
            "C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe",
            "C:\\Program Files\\Microsoft\\Edge\\Application\\msedge.exe",
        ]
        for p in candidates:
            if os.path.exists(p):
                return p
        return "msedge.exe"

    @staticmethod
    def _check_port(port: int) -> bool:
        import socket
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.connect(("127.0.0.1", port))
                return True
            except Exception:
                return False

    def _ensure_components(self):
        if self.monitor is None:
            self.monitor = HtmlChangeMonitor(
                self.driver, logger=self.logger, selectors=self.selectors
            )
        if self._uploader is None:
            self._uploader = DragAndDropUploader(
                self.driver, logger=self.logger, selectors=self.selectors
            )

    def connect(self, debug_port: int = 9222, user_data_dir: str = None) -> None:
        """Подключается к Edge (debug mode) или использует переданный driver."""
        if self.driver is not None:
            self._ensure_components()
            return

        import subprocess
        from selenium import webdriver
        from selenium.webdriver.edge.options import Options

        user_data_dir = user_data_dir or os.path.expandvars(
            r"%LOCALAPPDATA%\QwenDebugProfile"
        )

        if not self._check_port(debug_port):
            edge_exe = self._find_edge_exe()
            os.makedirs(user_data_dir, exist_ok=True)
            cmd = [
                edge_exe,
                f"--user-data-dir={user_data_dir}",
                f"--remote-debugging-port={debug_port}",
                "--no-first-run",
                "--no-default-browser-check",
                "--disable-sync",
                "--disable-search-engine-choice-screen",
                self.url,
            ]
            if self.logger:
                self.logger.log(f"🚀 Запуск Edge (порт {debug_port})...")
            subprocess.Popen(cmd, shell=False)
            for _ in range(20):
                time.sleep(1)
                if self._check_port(debug_port):
                    break
            else:
                raise RuntimeError(f"Edge не запустился за 20 секунд (порт {debug_port})")

        options = Options()
        options.add_experimental_option("debuggerAddress", f"127.0.0.1:{debug_port}")
        options.page_load_strategy = "eager"
        self.driver = webdriver.Edge(options=options)
        self._owns_driver = True
        if self.logger:
            self.logger.log(f"Edge подключён (debug mode, порт {debug_port}).")
        self._ensure_components()

    def close(self) -> None:
        """Закрывает браузер, только если он запущен этим клиентом."""
        if self._owns_driver and self.driver is not None:
            try:
                self.driver.quit()
            except Exception:
                pass

    # === Шаги потока ===

    def open_chat(self) -> None:
        """Открывает URL чата и ждёт появления body."""
        self.driver.get(self.url)
        if self.logger:
            self.logger.log(f"🌐 Открыт {self.url}")
        deadline = time.time() + 15
        while time.time() < deadline:
            try:
                if self.driver.execute_script(
                    "return document.body ? true : false;"
                ):
                    return
            except Exception:
                pass
            time.sleep(0.5)
        if self.logger:
            self.logger.log("⚠️ Не дождались body за 15 секунд", "WARNING")

    def send_task_file(self, file_path: str) -> bool:
        """Загружает файл-задание drag-and-drop'ом. True — если загружен."""
        self._last_file_name = os.path.basename(file_path)
        return self._uploader.upload(file_path)

    def wait_file_received(self, timeout: float = 30,
                           file_name: str = "") -> HtmlSnapshot:
        """Ждёт появления чипа файла (и имени файла в тексте страницы)."""
        baseline = self.monitor.snapshot()
        snap = self.monitor.wait_for_change(
            baseline, timeout, desc="file received",
            marker_queries={"file_chip": self.selectors["file_chip"]},
        )
        if file_name:
            deadline = time.time() + timeout
            while time.time() < deadline:
                text = self.monitor.get_page_text()
                if file_name in text:
                    snap = self.monitor.snapshot()
                    break
                time.sleep(0.5)
        return snap

    def _find_textarea(self):
        from selenium.webdriver.common.by import By
        for sel in self.selectors["input_textarea"]:
            try:
                els = self.driver.find_elements(By.CSS_SELECTOR, sel)
            except Exception:
                continue
            for el in els:
                try:
                    if el.is_displayed():
                        return el
                except Exception:
                    return el
        return None

    def _get_input_value(self, element) -> str:
        try:
            val = self.driver.execute_script(
                "return arguments[0].value || arguments[0].textContent || '';",
                element,
            )
            if val:
                return val
        except Exception:
            pass
        try:
            return element.get_attribute("value") or ""
        except Exception:
            return ""

    def _click_send_or_enter(self, textarea) -> bool:
        from selenium.webdriver.common.by import By
        from selenium.webdriver.common.keys import Keys
        for sel in self.selectors["send_button"]:
            try:
                els = self.driver.find_elements(By.CSS_SELECTOR, sel)
            except Exception:
                continue
            for btn in els:
                try:
                    if btn.is_displayed():
                        btn.click()
                        if self.logger:
                            self.logger.log(f"✅ клик по кнопке отправки: {sel}")
                        return True
                except Exception:
                    pass
        try:
            textarea.send_keys(Keys.RETURN)
            if self.logger:
                self.logger.log("✅ отправка через Enter")
            return True
        except Exception as e:
            if self.logger:
                self.logger.log(f"❌ отправка не удалась: {e}", "ERROR")
            return False

    def send_prompt(self, prompt: str) -> bool:
        """Вставляет промпт (nativeSetter) и отправляет. True — если отправлен."""
        textarea = self._find_textarea()
        if textarea is None:
            if self.logger:
                self.logger.log("❌ textarea не найдена", "ERROR")
            return False

        try:
            textarea.click()
            time.sleep(0.3)
            self.driver.execute_script(
                """
                const el = arguments[0];
                const text = arguments[1];
                const proto = el.tagName === 'TEXTAREA'
                    ? window.HTMLTextAreaElement.prototype
                    : window.HTMLDivElement.prototype;
                const nativeSetter = Object.getOwnPropertyDescriptor(proto, 'value').set;
                nativeSetter.call(el, text);
                el.dispatchEvent(new Event('input', { bubbles: true }));
                el.dispatchEvent(new Event('change', { bubbles: true }));
                """,
                textarea,
                prompt,
            )
            time.sleep(0.5)
        except Exception as e:
            if self.logger:
                self.logger.log(f"⚠️ nativeSetter failed, send_keys: {e}", "WARNING")
            try:
                textarea.clear()
                textarea.send_keys(prompt)
            except Exception as e2:
                if self.logger:
                    self.logger.log(f"❌ вставка текста не удалась: {e2}", "ERROR")
                return False

        value = self._get_input_value(textarea)
        if not value or len(value) < len(prompt) // 2:
            if self.logger:
                self.logger.log("❌ текст не вставлен", "ERROR")
            return False

        if not self._click_send_or_enter(textarea):
            return False

        time.sleep(1.0)
        after = self._get_input_value(textarea)
        if after == "":
            if self.logger:
                self.logger.log("✅ промпт отправлен, поле очищено")
        else:
            if self.logger:
                self.logger.log("⚠️ поле не очистилось после отправки", "WARNING")
        return True

    def wait_thinking_started(self, timeout: float = 120) -> HtmlSnapshot:
        """Ждёт начала генерации (индикатор thinking или рост текста)."""
        baseline = self.monitor.snapshot()
        return self.monitor.wait_for_change(
            baseline, timeout, desc="thinking started",
            marker_queries={"thinking": self.selectors["thinking_indicator"]},
        )

    def wait_answer_ready(self, timeout: float = 600,
                          stable_duration: float = 3.0) -> HtmlSnapshot:
        """Ждёт стабилизации ответа и появления кнопки копирования."""
        return self.monitor.wait_for_stable(
            timeout, stable_duration=stable_duration, desc="answer ready",
            marker_queries={"copy": self.selectors["copy_answer_button"]},
        )

    def _reveal_response_footer(self) -> None:
        """Раскрывает скрытый футер сообщения (response-message-footer-none).

        В новом UI Qwen кнопка «Копировать» видна только после наведения мыши на
        сообщение; CSS-класс .response-message-footer-none прячет футер.
        """
        try:
            from selenium.webdriver.common.action_chains import ActionChains
            from selenium.webdriver.common.by import By
        except Exception:
            return

        for sel in self.selectors["assistant_message"]:
            try:
                els = self.driver.find_elements(By.CSS_SELECTOR, sel)
            except Exception:
                continue
            if not els:
                continue
            try:
                target = els[-1]
                self.driver.execute_script(
                    "arguments[0].scrollIntoView({block:'center'});", target
                )
                time.sleep(0.3)
                ActionChains(self.driver).move_to_element(target).perform()
                time.sleep(0.5)
                # Снять класс скрытия у всех футеров страницы (надёжнее hover)
                self.driver.execute_script(
                    "document.querySelectorAll('div.response-message-footer')"
                    ".forEach(el => el.classList.remove('response-message-footer-none'));"
                )
                if self.logger:
                    self.logger.log("✅ Футер ответа раскрыт (hover + снят класс скрытия).")
                return
            except Exception:
                continue

    @staticmethod
    def normalize_answer_text(text: str) -> str:
        """Нормализует скопированный текст: CRLF→LF, без одиночных \r и дублей пустых строк."""
        if not text:
            return ""
        text = text.replace("\r\n", "\n").replace("\r", "\n")
        lines = [ln.rstrip() for ln in text.split("\n")]
        out = []
        prev_blank = False
        for ln in lines:
            blank = not ln.strip()
            if blank and prev_blank:
                continue
            out.append(ln)
            prev_blank = blank
        return "\n".join(out).strip()

    def _copy_message_via_button(self) -> str:
        """Ищет и нажимает кнопку «Копировать» у последнего сообщения. '' — не удалось."""
        try:
            from agent.clipboard import ClipboardManager
            from selenium.webdriver.common.by import By
        except Exception:
            ClipboardManager = None
            By = None
        if By is None or ClipboardManager is None:
            return ""

        for sel in self.selectors["copy_answer_button"]:
            try:
                els = self.driver.find_elements(By.CSS_SELECTOR, sel)
            except Exception:
                continue
            for el in els:
                try:
                    if el.is_displayed():
                        self.driver.execute_script(
                            "arguments[0].scrollIntoView({block:'center'});", el
                        )
                        time.sleep(0.3)
                        el.click()
                        time.sleep(0.5)
                        text = ClipboardManager.get_text() or ""
                        if text:
                            if self.logger:
                                self.logger.log(
                                    f"✅ ответ скопирован в буфер (длина {len(text)})"
                                )
                            return self.normalize_answer_text(text)
                except Exception:
                    continue
        return ""

    def extract_answer(self) -> str:
        """Копирует ответ через кнопку copy; фолбэк — текст последнего сообщения."""
        try:
            from selenium.webdriver.common.by import By
        except Exception:
            By = None

        self._reveal_response_footer()
        text = self._copy_message_via_button()
        if text:
            return text

        # Фолбэк: текст последнего сообщения ассистента
        if By is not None:
            for sel in self.selectors["assistant_message"]:
                try:
                    els = self.driver.find_elements(By.CSS_SELECTOR, sel)
                except Exception:
                    continue
                if els:
                    try:
                        text = els[-1].text or ""
                    except Exception:
                        text = ""
                    if text:
                        if self.logger:
                            self.logger.log(
                                f"✅ ответ извлечён из сообщения (длина {len(text)})"
                            )
                        return self.normalize_answer_text(text)
        return ""

    def extract_all_answers(self) -> list:
        """Копирует ВСЕ ответы ассистента через кнопки «Копировать».

        Возвращает список dict: {'index': int, 'text': str, 'error': str|None}.
        Наведение выполняется на каждый блок ответа, класс скрытия снимается,
        буфер обмена читается после каждого клика.
        """
        try:
            from agent.clipboard import ClipboardManager
            from selenium.webdriver.common.action_chains import ActionChains
            from selenium.webdriver.common.by import By
        except Exception:
            ClipboardManager = None
            ActionChains = None
            By = None

        results = []
        if By is None or ClipboardManager is None:
            return results

        messages = []
        for sel in self.selectors["assistant_message"]:
            try:
                messages = self.driver.find_elements(By.CSS_SELECTOR, sel)
            except Exception:
                continue
            if messages:
                break

        for i, message in enumerate(messages, start=1):
            entry = {"index": i, "text": "", "error": None}
            try:
                self.driver.execute_script(
                    "arguments[0].scrollIntoView({block:'center'});", message
                )
                time.sleep(0.3)
                if ActionChains is not None:
                    ActionChains(self.driver).move_to_element(message).perform()
                    time.sleep(0.4)
                self.driver.execute_script(
                    "const el = arguments[0];"
                    "el.querySelectorAll('div.response-message-footer')"
                    ".forEach(f => f.classList.remove('response-message-footer-none'));",
                    message,
                )

                copied = ""
                for sel in self.selectors["copy_answer_button"]:
                    try:
                        els = message.find_elements(By.CSS_SELECTOR, sel)
                    except Exception:
                        continue
                    for el in els:
                        try:
                            if el.is_displayed():
                                el.click()
                                time.sleep(0.6)
                                copied = ClipboardManager.get_text() or ""
                                if copied:
                                    break
                        except Exception:
                            continue
                    if copied:
                        break

                if copied:
                    entry["text"] = self.normalize_answer_text(copied)
                else:
                    entry["text"] = self.normalize_answer_text(message.text or "")
                    entry["error"] = "copy button not found/clicked, fallback .text"
                if self.logger:
                    self.logger.log(
                        f"✅ Ответ {i}: {len(entry['text'])} симв."
                        + (f" ({entry['error']})" if entry["error"] else "")
                    )
            except Exception as e:
                entry["error"] = str(e)
            results.append(entry)
            time.sleep(0.8)

        return results

    def save_all_answers(self, answers: list, output_file: str,
                         chat_id: str = "") -> str:
        """Сохраняет все ответы в один markdown. Возвращает путь."""
        from datetime import datetime

        parent = os.path.dirname(os.path.abspath(output_file))
        if parent:
            os.makedirs(parent, exist_ok=True)

        with open(output_file, "w", encoding="utf-8", newline="\n") as f:
            f.write("# Ответы Qwen (chat.qwen.ai)\n\n")
            f.write(f"**Чат:** {chat_id}\n\n")
            f.write(f"**Дата:** {datetime.now().isoformat(timespec='seconds')}\n\n")
            for a in answers:
                f.write("---\n\n")
                f.write(f"## Ответ {a['index']}\n\n")
                if a.get("error"):
                    f.write(f"_{a['error']}_\n\n")
                f.write((a.get("text") or "").strip() + "\n\n")
            f.write("---\n")
        if self.logger:
            self.logger.log(f"💾 Все ответы сохранены: {output_file} ({len(answers)} шт.)")
        return output_file

    def save_answer(self, answer: str, output_file: str) -> str:
        """Сохраняет ответ в markdown (шапка: дата + имя файла). Возвращает путь."""
        from datetime import datetime

        parent = os.path.dirname(os.path.abspath(output_file))
        if parent:
            os.makedirs(parent, exist_ok=True)

        with open(output_file, "w", encoding="utf-8") as f:
            f.write("# Ответ Qwen\n\n")
            f.write(f"**Дата:** {datetime.now().isoformat(timespec='seconds')}\n")
            f.write(f"**Источник:** {self._last_file_name or os.path.basename(output_file)}\n\n")
            f.write("---\n\n")
            f.write(answer)
            f.write("\n")
        if self.logger:
            self.logger.log(f"💾 Ответ сохранён: {output_file}")
        return output_file

    # === Оркестрация ===

    def run_task(self, file_path: str, prompt: str,
                 output_file: str = "qwen_answer.md",
                 timeout_file: float = 30, timeout_thinking: float = 120,
                 timeout_answer: float = 600) -> dict:
        """Полный поток: файл → промпт → ответ → сохранение."""
        stages = {"file_received": 0.0, "thinking_started": 0.0, "answer_ready": 0.0}
        error = ""
        answer = ""
        try:
            self.connect()
            self.open_chat()

            t0 = time.time()
            if not self.send_task_file(file_path):
                error = "file drop failed"
            else:
                snap = self.wait_file_received(
                    timeout_file, os.path.basename(file_path)
                )
                elapsed = time.time() - t0
                stages["file_received"] = elapsed
                if self.monitor:
                    self.monitor.log_stage("file_received", snap, elapsed)

            if not error:
                t0 = time.time()
                if not self.send_prompt(prompt):
                    error = "prompt send failed"
                else:
                    snap = self.wait_thinking_started(timeout_thinking)
                    elapsed = time.time() - t0
                    stages["thinking_started"] = elapsed
                    if self.monitor:
                        self.monitor.log_stage("thinking_started", snap, elapsed)

            if not error:
                t0 = time.time()
                snap = self.wait_answer_ready(timeout_answer)
                elapsed = time.time() - t0
                stages["answer_ready"] = elapsed
                if self.monitor:
                    self.monitor.log_stage("answer_ready", snap, elapsed)

                answer = self.extract_answer()
                if not answer:
                    error = "answer extraction failed"
                else:
                    output_file = self.save_answer(answer, output_file)
        except Exception as e:
            error = str(e)
            if self.logger:
                self.logger.log(f"❌ QwenClient error: {e}", "ERROR")
        finally:
            self.close()

        return {
            "ok": not error,
            "stages": stages,
            "answer": answer,
            "output_file": output_file,
            "error": error,
        }
