# response_ready.py
import time
from abc import ABC, abstractmethod
from selenium.webdriver.remote.webelement import WebElement
from selenium.webdriver.common.by import By
from selenium.common.exceptions import StaleElementReferenceException
from detection.selectors import SELECTORS


def _coerce_list(value):
    """Приводит селектор (строка или список) к списку."""
    if value is None:
        return []
    if isinstance(value, str):
        return [value]
    return list(value)


class ResponseReadyStrategy(ABC):
    @abstractmethod
    def wait(self, driver, last_message_element: WebElement, timeout: float) -> tuple[bool, str]:
        pass


class TextStabilizationStrategy(ResponseReadyStrategy):
    """Стабилизация текста и innerHTML последнего сообщения.

    Ответ считается готовым, когда и текст, и длина innerHTML перестали расти
    в течение stable_duration. HTML-стабильность ловит случаи, когда видимый
    текст не меняется, но контент ещё рендерится (код-блоки, таблицы).
    """

    def __init__(self, check_interval: float = 0.5, stable_duration: float = 1.0,
                 selectors: dict = None):
        self.check_interval = check_interval
        self.stable_duration = stable_duration
        self.selectors = selectors or SELECTORS

    def _current(self, driver, element) -> tuple[str, int]:
        """Возвращает (text, len(innerHTML)) элемента, обрабатывая stale."""
        try:
            text = element.text or ""
            try:
                html = driver.execute_script(
                    "return arguments[0].innerHTML.length;", element
                ) or 0
            except Exception:
                html = len(element.get_attribute("innerHTML") or "")
            return text, int(html or 0)
        except StaleElementReferenceException:
            try:
                messages = driver.find_elements(
                    By.XPATH, _coerce_list(self.selectors["assistant_messages"])[0]
                )
                if messages:
                    el = messages[-1]
                    text = el.text or ""
                    try:
                        html = driver.execute_script(
                            "return arguments[0].innerHTML.length;", el
                        ) or 0
                    except Exception:
                        html = len(el.get_attribute("innerHTML") or "")
                    return text, int(html or 0)
            except Exception:
                pass
            return "", 0

    def wait(self, driver, last_message_element: WebElement, timeout: float) -> tuple[bool, str]:
        start_time = time.time()
        stable_counter = 0.0
        last = None
        while time.time() - start_time < timeout:
            current = self._current(driver, last_message_element)
            if last is None:
                last = current
                time.sleep(self.check_interval)
                continue

            if current == last:
                stable_counter += self.check_interval
            else:
                stable_counter = 0.0
                last = current

            if stable_counter >= self.stable_duration:
                return True, "стабилизация текста и HTML"
            time.sleep(self.check_interval)
        return False, "таймаут стабилизации"


class CopyButtonAppearanceStrategy(ResponseReadyStrategy):
    """Ожидает появления кнопки копирования для блоков кода (старое)."""

    def __init__(self, check_interval: float = 0.5, selectors: dict = None):
        self.check_interval = check_interval
        self.selectors = selectors or SELECTORS

    def wait(self, driver, last_message_element: WebElement, timeout: float) -> tuple[bool, str]:
        start_time = time.time()
        while time.time() - start_time < timeout:
            try:
                copy_buttons = last_message_element.find_elements(
                    By.CSS_SELECTOR, ", ".join(_coerce_list(self.selectors["copy_button"]))
                )
                if copy_buttons and copy_buttons[0].is_displayed():
                    return True, "появление кнопки 'Копировать' (блок кода)"
            except StaleElementReferenceException:
                try:
                    messages = driver.find_elements(
                        By.XPATH, _coerce_list(self.selectors["assistant_messages"])[0]
                    )
                    if messages:
                        last_message_element = messages[-1]
                        continue
                except Exception:
                    pass
            time.sleep(self.check_interval)
        return False, "таймаут ожидания кнопки (блок кода)"


class CopyButtonCountStrategy(ResponseReadyStrategy):
    """Готовность по количеству кнопок копирования.

    Пока счётчик растёт — ответ генерируется; когда счётчик > 0 и стабилен
    (не меняется) в течение stable_duration — ответ готов.
    Для DeepSeek: div.ds-button__background / span.code-info-button-text.
    Для Qwen: button[aria-label*='copy' i] и др. (из config.selectors).
    """

    def __init__(self, check_interval: float = 0.5, stable_duration: float = 1.0,
                 selectors: dict = None):
        self.check_interval = check_interval
        self.stable_duration = stable_duration
        self.selectors = selectors or SELECTORS

    def _count_buttons(self, element) -> int:
        total = 0
        for sel in _coerce_list(self.selectors.get("copy_button")):
            try:
                total += len(element.find_elements(By.CSS_SELECTOR, sel))
            except Exception:
                continue
        return total

    def wait(self, driver, last_message_element: WebElement, timeout: float) -> tuple[bool, str]:
        start_time = time.time()
        stable_counter = 0.0
        last_count = None
        while time.time() - start_time < timeout:
            try:
                count = self._count_buttons(last_message_element)
            except StaleElementReferenceException:
                try:
                    messages = driver.find_elements(
                        By.XPATH, _coerce_list(self.selectors["assistant_messages"])[0]
                    )
                    if messages:
                        last_message_element = messages[-1]
                        count = self._count_buttons(last_message_element)
                    else:
                        count = 0
                except Exception:
                    count = 0

            if count > 0:
                if last_count is None:
                    last_count = count
                    time.sleep(self.check_interval)
                    continue
                if count == last_count:
                    stable_counter += self.check_interval
                else:
                    last_count = count
                    stable_counter = 0.0
                if stable_counter >= self.stable_duration:
                    return True, f"количество кнопок копирования стабильно ({count})"
            else:
                last_count = None
                stable_counter = 0.0

            time.sleep(self.check_interval)
        return False, "таймаут ожидания стабильности кнопок копирования"


class CopyMessageButtonStrategy(ResponseReadyStrategy):
    """Ожидает появления кнопки копирования всего сообщения."""

    def __init__(self, check_interval: float = 0.5, selectors: dict = None):
        self.check_interval = check_interval
        self.selectors = selectors or SELECTORS

    def wait(self, driver, last_message_element: WebElement, timeout: float) -> tuple[bool, str]:
        start_time = time.time()
        while time.time() - start_time < timeout:
            for sel in _coerce_list(self.selectors.get("copy_message_button")):
                try:
                    copy_btns = last_message_element.find_elements(By.CSS_SELECTOR, sel)
                    for cb in copy_btns:
                        try:
                            if cb.is_displayed():
                                return True, "появление кнопки копирования сообщения"
                        except Exception:
                            continue
                except Exception:
                    continue
            time.sleep(self.check_interval)
        return False, "таймаут ожидания кнопки копирования сообщения"


class SendButtonStateStrategy(ResponseReadyStrategy):
    """Стратегия, отслеживающая состояние кнопки отправки (DeepSeek).

    - Ждём, пока кнопка станет disabled (начало генерации).
    - Затем ждём, пока кнопка перестанет быть disabled (конец генерации).
    """

    def __init__(self, check_interval: float = 0.5, selectors: dict = None):
        self.check_interval = check_interval
        self.selectors = selectors or SELECTORS

    def _get_send_button(self, driver):
        try:
            buttons = driver.find_elements(By.CSS_SELECTOR, "div[role='button']")
            for btn in buttons:
                classes = btn.get_attribute("class") or ""
                if "ds-button--circle" in classes:
                    return btn
        except Exception:
            pass
        return None

    def wait(self, driver, last_message_element: WebElement, timeout: float) -> tuple[bool, str]:
        start_time = time.time()
        disabled_detected = False

        while time.time() - start_time < timeout:
            btn = self._get_send_button(driver)
            if btn is None:
                time.sleep(self.check_interval)
                continue

            classes = btn.get_attribute("class") or ""
            is_disabled = "ds-button--disabled" in classes

            if not disabled_detected:
                if is_disabled:
                    disabled_detected = True
                    continue
            else:
                if not is_disabled:
                    return True, "кнопка отправки стала активной"

            time.sleep(self.check_interval)

        return False, "таймаут ожидания состояния кнопки"


class CombinedStrategy(ResponseReadyStrategy):
    """Комбинированная стратегия: несколько условий, быстрый возврат.

    Порядок:
    1. Стабильное количество кнопок копирования (CopyButtonCountStrategy,
       короткое окно ~5с) — самый быстрый надёжный сигнал.
    2. Появление кнопки копирования сообщения + непустой контент.
    3. Состояние кнопки отправки (disabled -> enabled) + непустой контент.
    4. Стабилизация текста и innerHTML (с порогом min_content_length).
    5. Запасной вариант — полная стабилизация (5с).
    """

    MIN_CONTENT_LENGTH = 10

    def __init__(self,
                 text_strategy: TextStabilizationStrategy,
                 button_strategy: CopyButtonAppearanceStrategy,
                 send_button_strategy: SendButtonStateStrategy,
                 copy_message_strategy: CopyMessageButtonStrategy,
                 copy_count_strategy: CopyButtonCountStrategy = None,
                 logger=None,
                 debug_interval: float = 2.0,
                 selectors: dict = None,
                 min_content_length: int = None):
        self.text_strategy = text_strategy
        self.button_strategy = button_strategy
        self.send_button_strategy = send_button_strategy
        self.copy_message_strategy = copy_message_strategy
        self.copy_count_strategy = copy_count_strategy or CopyButtonCountStrategy(
            check_interval=0.5, stable_duration=1.0, selectors=selectors
        )
        self.logger = logger
        self.debug_interval = debug_interval
        self.selectors = selectors or SELECTORS
        self.min_content_length = (
            min_content_length if min_content_length is not None
            else self.MIN_CONTENT_LENGTH
        )

    def _log_element_state(self, driver):
        if not self.logger:
            return
        try:
            input_box = driver.find_element(By.CSS_SELECTOR, _coerce_list(
                self.selectors["input_textarea"])[0])
            value = driver.execute_script("return arguments[0].value;", input_box)
            placeholder = input_box.get_attribute("placeholder")
            self.logger.log(f"🔍 textarea: value='{value[:50]}...' (len {len(value)}), placeholder='{placeholder}'")
        except Exception as e:
            self.logger.log(f"🔍 textarea: не найдено ({e})")

        try:
            buttons = driver.find_elements(By.CSS_SELECTOR, "div[role='button']")
            found = False
            for btn in buttons:
                classes = btn.get_attribute("class") or ""
                if "ds-button--circle" in classes:
                    disabled = "ds-button--disabled" in classes
                    self.logger.log(f"🔍 send_button: disabled={disabled}")
                    found = True
                    break
            if not found:
                self.logger.log("🔍 send_button: не найден")
        except Exception as e:
            self.logger.log(f"🔍 send_button: ошибка ({e})")

    def _get_content_len(self, driver, last_message_element) -> int:
        try:
            return len((last_message_element.text or "").strip())
        except Exception:
            return 0

    def _check_content_ok(self, driver, last_message_element) -> bool:
        """Непустой контент: текст > 0 ИЛИ есть кнопки копирования кода."""
        try:
            text = (last_message_element.text or "").strip()
            if len(text) > 0:
                return True
            code_blocks = last_message_element.find_elements(
                By.CSS_SELECTOR, ", ".join(_coerce_list(self.selectors["copy_button"]))
            )
            if code_blocks:
                return True
            return False
        except Exception:
            return False

    def wait(self, driver, last_message_element: WebElement, timeout: float) -> tuple[bool, str]:
        start_time = time.time()
        last_debug_time = start_time

        def _remaining() -> float:
            return max(0.0, timeout - (time.time() - start_time))

        # 1. Быстрое подтверждение: стабильное количество кнопок копирования
        remaining = _remaining()
        if remaining > 0:
            ok, reason = self.copy_count_strategy.wait(
                driver, last_message_element, min(remaining, 5.0)
            )
            if ok:
                return True, f"кнопки копирования стабильны ({reason})"

        # 2. Кнопка копирования сообщения + непустой контент
        remaining = _remaining()
        if remaining > 0:
            ok, reason = self.copy_message_strategy.wait(driver, last_message_element, remaining)
            if ok and self._check_content_ok(driver, last_message_element):
                return True, reason
            if ok:
                self.logger and self.logger.log(
                    f"copy_message готов, но контент пуст ({self._get_content_len(driver, last_message_element)}). Ждём дальше."
                )

        # 3. Кнопка отправки disabled -> enabled + непустой контент
        remaining = _remaining()
        if remaining > 0:
            ok, reason = self.send_button_strategy.wait(driver, last_message_element, remaining)
            if ok and self._check_content_ok(driver, last_message_element):
                return True, reason
            if ok:
                self.logger and self.logger.log(
                    f"send_button готов, но контент короткий ({self._get_content_len(driver, last_message_element)}). Ждём дальше."
                )

        # 4. Цикл: стабилизация текста/HTML + появление кнопок копирования
        while time.time() - start_time < timeout:
            if self.logger and (time.time() - last_debug_time) >= self.debug_interval:
                self._log_element_state(driver)
                last_debug_time = time.time()

            msg_text = ""
            try:
                msg_text = (last_message_element.text or "").strip()
            except Exception:
                pass

            # Кнопки копирования блоков кода (появление) + короткая стабилизация
            try:
                copy_buttons = last_message_element.find_elements(
                    By.CSS_SELECTOR, ", ".join(_coerce_list(self.selectors["copy_button"]))
                )
                if copy_buttons and copy_buttons[0].is_displayed():
                    remaining2 = _remaining()
                    if remaining2 > 0:
                        check_timeout = min(remaining2, 1.0)
                        ok_stab, reason_stab = self.text_strategy.wait(
                            driver, last_message_element, check_timeout
                        )
                        if ok_stab:
                            return True, f"кнопка 'Копировать' (блок кода) + стабилизация ({reason_stab})"
            except Exception:
                pass

            # Стабилизация текста (порог min_content_length)
            if len(msg_text) >= self.min_content_length:
                remaining2 = _remaining()
                if remaining2 > 0:
                    check_timeout = min(remaining2, 0.5)
                    ok, reason = self.text_strategy.wait(driver, last_message_element, check_timeout)
                    if ok:
                        return True, reason

            time.sleep(0.2)

        # 5. Запасной вариант – полная стабилизация
        return self.text_strategy.wait(driver, last_message_element, timeout=5)


class ResponseReadyStrategyFactory:
    @staticmethod
    def get_strategy(name: str, logger=None, selectors: dict = None, **kwargs):
        selectors = selectors or SELECTORS
        text_strategy = TextStabilizationStrategy(
            check_interval=kwargs.get('check_interval', 0.5),
            stable_duration=kwargs.get('stable_duration', 1.0),
            selectors=selectors,
        )
        button_strategy = CopyButtonAppearanceStrategy(
            check_interval=kwargs.get('check_interval', 0.5),
            selectors=selectors,
        )
        send_button_strategy = SendButtonStateStrategy(
            check_interval=kwargs.get('check_interval', 0.5),
            selectors=selectors,
        )
        copy_message_strategy = CopyMessageButtonStrategy(
            check_interval=kwargs.get('check_interval', 0.5),
            selectors=selectors,
        )
        copy_count_strategy = CopyButtonCountStrategy(
            check_interval=kwargs.get('check_interval', 0.5),
            stable_duration=kwargs.get('stable_duration', 1.0),
            selectors=selectors,
        )

        if name == "text_stabilization":
            return text_strategy
        elif name == "copy_button":
            return button_strategy
        elif name == "send_button":
            return send_button_strategy
        elif name == "copy_message":
            return copy_message_strategy
        elif name == "copy_count":
            return copy_count_strategy
        elif name == "combined":
            return CombinedStrategy(
                text_strategy,
                button_strategy,
                send_button_strategy,
                copy_message_strategy,
                copy_count_strategy,
                logger=logger,
                debug_interval=kwargs.get('debug_interval', 2.0),
                selectors=selectors,
                min_content_length=kwargs.get('min_content_length'),
            )
        else:
            raise ValueError(f"Неизвестная стратегия: {name}")
