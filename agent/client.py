"""
SeleniumChatClient - фасад, использующий специализированные обработчики.
Базовый класс общий для DeepSeek и Qwen; подклассы выбирают auth + селекторы.
"""
import os
import time
from typing import Optional, Tuple

from selenium.webdriver.common.by import By

from agent.auth import DeepSeekAuth
from agent.qwen_auth import QwenAuth
from agent.browser.manager import BrowserManager
from agent.clipboard import ClipboardManager
from agent.handlers.file_attacher import FileAttacher
from agent.handlers.message_sender import MessageSender
from agent.handlers.response_reader import ResponseReader
from detection.action_panel import ActionPanelFinder
from detection.element_finder import ElementFinder


class SeleniumChatClient:
    """Базовый фасад облачного чата (DeepSeek / Qwen)."""

    provider_name = "chat"

    def __init__(self, logger, config, auth_cls=None, chat_fallback_url=None):
        self.logger = logger
        self.config = config

        self.browser = BrowserManager(logger, config)
        self.driver = self.browser.start()

        self.clipboard = ClipboardManager()
        self.finder = ElementFinder(self.driver, logger, config.selectors)
        self.panel_finder = ActionPanelFinder(self.driver, config, logger=self.logger)

        self.sender = MessageSender(self.driver, logger, self.finder)
        self.reader = ResponseReader(self.driver, logger, config, self.finder, self.clipboard)
        self.attacher = FileAttacher(self.driver, logger, self.finder, self.clipboard)

        self._email = ""
        self._password = ""
        self._chat_fallback_url = chat_fallback_url or "https://chat.deepseek.com/a/chat"

        auth_cls = auth_cls or DeepSeekAuth
        auth = auth_cls(self.driver, self.logger)
        logged_in = auth.ensure_logged_in(
            email=self._email,
            password=self._password,
            timeout=120
        )
        if not logged_in:
            self.logger.log("Could not log in.", "ERROR")

    def set_auth_credentials(self, email: str, password: str):
        self._email = email
        self._password = password

    def send_message(self, message: str) -> Optional[Tuple[str, Optional[str]]]:
        self.logger.log(f"📤 Отправка запроса в {self.provider_name}...")

        old_messages = self.reader.get_assistant_messages()
        count_before = len(old_messages)
        self.logger.log(f"До отправки: {count_before} сообщений ассистента.")

        if not self.sender.send(message):
            return None

        new_message = self.reader.wait_for_new_message(count_before, self.config.selenium_timeout)
        if not new_message:
            return None

        ready = self.reader.wait_ready(new_message, self.config.stable_timeout)
        if not ready:
            self.logger.log("⚠️ Ответ не подтверждён как готовый, но попытаемся скопировать.", "WARNING")

        full_text = self.reader.get_full_text(new_message)
        code_text = self.reader.get_code_from_message(new_message)

        if full_text:
            return (full_text, code_text)

        self.logger.log("❌ Не удалось получить текст ответа.", "ERROR")
        return None

    def send_message_with_attached_file(self, message: str) -> Optional[Tuple[str, Optional[str]]]:
        """Отправка сообщения ПОСЛЕ прикрепления файла.

        Qwen показывает оверлей/перестраивает композитор после drag-and-drop файла:
        textarea и send-button становятся недоступны для Selenium (is_displayed=False),
        поэтому обычный sender.send() не срабатывает. Здесь:
          1) текст вводится напрямую через JS nativeSetter в textarea;
          2) кнопка отправки нажимается через JS click;
          3) ответ читается штатным ResponseReader'ом.
        """
        self.logger.log(f"📤 Отправка запроса (с прикреплённым файлом) в {self.provider_name}...")

        old_messages = self.reader.get_assistant_messages()
        count_before = len(old_messages)
        self.logger.log(f"До отправки: {count_before} сообщений ассистента.")

        if not self._type_into_textarea_js(message):
            return None

        if not self._click_send_button_js():
            self.logger.log("❌ Кнопка отправки не найдена (JS).", "ERROR")
            return None

        new_message = self.reader.wait_for_new_message(count_before, self.config.selenium_timeout)
        if not new_message:
            self.logger.log("❌ Новое сообщение не появилось после отправки.", "ERROR")
            return None

        ready = self.reader.wait_ready(new_message, self.config.stable_timeout)
        if not ready:
            self.logger.log("⚠️ Ответ не подтверждён как готовый, но попытаемся скопировать.", "WARNING")

        full_text = self.reader.get_full_text(new_message)
        code_text = self.reader.get_code_from_message(new_message)

        if full_text:
            return (full_text, code_text)

        self.logger.log("❌ Не удалось получить текст ответа.", "ERROR")
        return None

    def _type_into_textarea_js(self, message: str) -> bool:
        """Вводит текст в textarea.message-input-textarea через JS nativeSetter (без проверки видимости)."""
        try:
            escaped = message.replace("\\", "\\\\").replace("'", "\\'").replace("\n", "\\n")
            expr = f"""
            (() => {{
              const el = document.querySelector('textarea.message-input-textarea');
              if (!el) return 'no-textarea';
              const s = Object.getOwnPropertyDescriptor(
                window.HTMLTextAreaElement.prototype, 'value'
              ).set;
              s.call(el, '{escaped}');
              el.dispatchEvent(new Event('input', {{ bubbles: true }}));
              el.dispatchEvent(new Event('change', {{ bubbles: true }}));
              return 'typed:' + el.value.length;
            }})()
            """
            res = self.driver.execute_cdp_cmd("Runtime.evaluate", {
                "expression": expr,
                "returnByValue": True,
            })
            val = (res.get("result", {}) or {}).get("value", "")
            self.logger.log(f"📋 JS-ввод текста: {val}")
            return isinstance(val, str) and val.startswith("typed:")
        except Exception as e:
            self.logger.log(f"❌ Ошибка JS-ввода текста: {e}", "ERROR")
            return False

    def _click_send_button_js(self) -> bool:
        """Нажимает кнопку отправки через JS click (без проверки видимости).

        Qwen имеет два состояния композитора:
          - thread-режим (есть активный чат): кнопка button.send-button;
          - prompt-режим (главная страница / новый чат): chat-prompt-send-button.
        """
        selectors = [
            "button.send-button:not([disabled])",
            "button.send-button",
            "div.chat-prompt-send-button",
            "button[class*='prompt-send']",
            "div[class*='send-button']",
        ]
        for sel in selectors:
            try:
                btns = self.driver.find_elements(By.CSS_SELECTOR, sel)
                for b in btns:
                    try:
                        self.driver.execute_script("arguments[0].click();", b)
                        self.logger.log(f"✅ JS-клик по кнопке отправки: {sel}")
                        return True
                    except Exception:
                        continue
            except Exception:
                continue
        return False

    def select_model(self, name: str) -> bool:
        """
        Открывает селектор модели (dropdown) и выбирает модель по имени.
        Использует селекторы config.selectors: model_selector / model_options /
        model_option_by_text_xpath. Работает с UI Qwen (Ant Design dropdown).
        """
        self.logger.log(f"🤖 Выбор модели: {name}")
        selectors = self.config.selectors

        trigger_list = selectors.get("model_selector", [])
        if isinstance(trigger_list, str):
            trigger_list = [trigger_list]

        # Два полных цикла: dropdown мог быть открыт/закрыт от предыдущего вызова
        for cycle in range(2):
            clicked = False
            for sel in trigger_list:
                try:
                    if sel.startswith("//"):
                        els = self.driver.find_elements(By.XPATH, sel)
                    else:
                        els = self.driver.find_elements(By.CSS_SELECTOR, sel)
                    for el in els:
                        if el.is_displayed():
                            el.click()
                            clicked = True
                            break
                    if clicked:
                        break
                except Exception:
                    continue
            if not clicked:
                self.logger.log("⚠️ Селектор модели не найден", "WARNING")
                return False
            time.sleep(2)

            # 1) XPath по тексту модели (стабильный fallback)
            xpath_tpl = selectors.get("model_option_by_text_xpath", "")
            if xpath_tpl and "{model}" in xpath_tpl:
                try:
                    els = self.driver.find_elements(By.XPATH, xpath_tpl.format(model=name))
                    for el in els:
                        if el.is_displayed():
                            el.click()
                            self.logger.log(f"✅ Модель выбрана: {name}")
                            time.sleep(1)
                            return True
                except Exception:
                    pass

            # 2) Перебор пунктов меню по тексту
            options = selectors.get("model_options", [])
            if isinstance(options, str):
                options = [options]
            for sel in options:
                try:
                    if sel.startswith("//"):
                        els = self.driver.find_elements(By.XPATH, sel)
                    else:
                        els = self.driver.find_elements(By.CSS_SELECTOR, sel)
                    for el in els:
                        if el.is_displayed() and name in (el.text or ""):
                            el.click()
                            self.logger.log(f"✅ Модель выбрана: {name}")
                            time.sleep(1)
                            return True
                except Exception:
                    continue

            # dropdown не открылся — закроем (клик по триггеру) и повторим цикл
            for sel in trigger_list:
                try:
                    if sel.startswith("//"):
                        els = self.driver.find_elements(By.XPATH, sel)
                    else:
                        els = self.driver.find_elements(By.CSS_SELECTOR, sel)
                    for el in els:
                        if el.is_displayed():
                            el.click()
                            time.sleep(1)
                            break
                except Exception:
                    continue

        self.logger.log(f"⚠️ Модель '{name}' не найдена в списке", "WARNING")
        return False

    def send_prompt_legacy(self, message: str) -> Optional[str]:
        result = self.send_message(message)
        if result is None:
            return None
        full_text, _ = result
        return full_text

    def attach_files(self, file_paths: list) -> bool:
        return self.attacher.attach(file_paths)

    def attach_files_drop(self, file_paths: list) -> bool:
        """Drag-and-drop файлов через DataTransfer (CDP Runtime.evaluate).

        Qwen: обычный send_keys в input[type='file'] не регистрируется
        (файл не прикрепляется). Надёжный способ — сэмулировать настоящий
        drag-and-drop: строим File + DataTransfer и диспатчим dragenter/
        dragover/drop (и dragleave/dragend) на композитор.
        """
        import base64
        try:
            path = file_paths[0]
            if not os.path.exists(path):
                self.logger.log(f"⚠️ Файл не найден для drop: {path}", "WARNING")
                return False
            with open(path, "rb") as f:
                b64 = base64.b64encode(f.read()).decode()
            fname = os.path.basename(path)
            js = r"""
            () => {
              const b64 = '%B64%';
              const bin = atob(b64);
              const bytes = new Uint8Array(bin.length);
              for (let i = 0; i < bin.length; i++) bytes[i] = bin.charCodeAt(i);
              const file = new File([bytes], '%FNAME%', {type: 'text/plain'});
              const dt = new DataTransfer();
              dt.items.add(file);
              const targets = [
                document.querySelector('.message-input-container-area'),
                document.querySelector('.message-input-wrapper'),
                document.querySelector('textarea.message-input-textarea')
              ].filter(Boolean);
              for (const t of targets) {
                try {
                  t.dispatchEvent(new DragEvent('dragenter', {bubbles:true, cancelable:true, dataTransfer:dt}));
                  t.dispatchEvent(new DragEvent('dragover', {bubbles:true, cancelable:true, dataTransfer:dt}));
                  t.dispatchEvent(new DragEvent('drop', {bubbles:true, cancelable:true, dataTransfer:dt}));
                } catch (e) {}
              }
              for (const t of targets) {
                try {
                  t.dispatchEvent(new DragEvent('dragleave', {bubbles:true, cancelable:true, dataTransfer:dt}));
                  t.dispatchEvent(new DragEvent('dragend', {bubbles:true, cancelable:true, dataTransfer:dt}));
                } catch (e) {}
              }
              return document.querySelectorAll('.file-card-list, .message-input-column-file').length;
            }
            """.replace('%B64%', b64).replace('%FNAME%', fname)
            res = self.driver.execute_cdp_cmd("Runtime.evaluate", {
                "expression": "(" + js + ")()",
                "returnByValue": True,
            })
            count = (res.get("result", {}) or {}).get("value", 0)
            self.logger.log(f"📎 Drag-and-drop файла: {fname} (элементов файла: {count})")
            time.sleep(4)
            # проверим реально видимые чипы
            chips = self.driver.find_elements(
                By.CSS_SELECTOR, ".message-input-column-file, .file-card-list"
            )
            visible = sum(1 for c in chips if c.is_displayed())
            self.logger.log(f"   Чипов файла видимо: {visible}")
            return visible > 0
        except Exception as e:
            self.logger.log(f"❌ Ошибка drag-and-drop файла: {e}", "ERROR")
            return False

    def paste_files_from_clipboard(self) -> bool:
        return self.attacher.paste_from_clipboard()

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
            except Exception:
                pass
        self.logger.log("⚠️ Кнопка 'New chat' не найдена, просто переходим на страницу чата...")
        self.driver.get(self._chat_fallback_url)
        time.sleep(4)
        return True

    def close(self):
        self.browser.close()


class SeleniumDeepSeekClient(SeleniumChatClient):
    """Фасад DeepSeek Chat (поведение не изменилось)."""

    provider_name = "DeepSeek"

    def __init__(self, logger, config):
        super().__init__(
            logger, config,
            auth_cls=DeepSeekAuth,
            chat_fallback_url="https://chat.deepseek.com/a/chat",
        )


class SeleniumQwenClient(SeleniumChatClient):
    """Фасад Qwen Chat (chat.qwen.ai) с селекторами QWEN_SELECTORS."""

    provider_name = "Qwen"

    def __init__(self, logger, config):
        super().__init__(
            logger, config,
            auth_cls=QwenAuth,
            chat_fallback_url="https://chat.qwen.ai/",
        )
