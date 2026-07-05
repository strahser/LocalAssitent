# response_ready_strategy.py
import time
from abc import ABC, abstractmethod
from selenium.webdriver.remote.webelement import WebElement
from selenium.webdriver.common.by import By
from selenium.common.exceptions import StaleElementReferenceException
from selectors import SELECTORS


class ResponseReadyStrategy(ABC):
    @abstractmethod
    def wait(self, driver, last_message_element: WebElement, timeout: float) -> tuple[bool, str]:
        pass


class TextStabilizationStrategy(ResponseReadyStrategy):
    def __init__(self, check_interval: float = 0.5, stable_duration: float = 1.0):
        self.check_interval = check_interval
        self.stable_duration = stable_duration

    def wait(self, driver, last_message_element: WebElement, timeout: float) -> tuple[bool, str]:
        start_time = time.time()
        stable_counter = 0.0
        last_text = None
        while time.time() - start_time < timeout:
            try:
                current_text = last_message_element.text
            except StaleElementReferenceException:
                try:
                    messages = driver.find_elements(By.XPATH, SELECTORS["assistant_messages"])
                    if messages:
                        last_message_element = messages[-1]
                        current_text = last_message_element.text
                    else:
                        return False, "Сообщения не найдены"
                except:
                    return False, "Ошибка при обновлении элемента"

            if last_text is None:
                last_text = current_text
                time.sleep(self.check_interval)
                continue

            if current_text == last_text:
                stable_counter += self.check_interval
            else:
                stable_counter = 0.0
                last_text = current_text

            if stable_counter >= self.stable_duration:
                return True, "стабилизация текста"
            time.sleep(self.check_interval)
        return False, "таймаут стабилизации"


class CopyButtonAppearanceStrategy(ResponseReadyStrategy):
    """Ожидает появления кнопки копирования для блоков кода (старое)"""
    def __init__(self, check_interval: float = 0.5):
        self.check_interval = check_interval

    def wait(self, driver, last_message_element: WebElement, timeout: float) -> tuple[bool, str]:
        start_time = time.time()
        while time.time() - start_time < timeout:
            try:
                copy_buttons = last_message_element.find_elements(By.CSS_SELECTOR, SELECTORS["copy_button"])
                if copy_buttons and copy_buttons[0].is_displayed():
                    return True, "появление кнопки 'Копировать' (блок кода)"
            except StaleElementReferenceException:
                try:
                    messages = driver.find_elements(By.XPATH, SELECTORS["assistant_messages"])
                    if messages:
                        last_message_element = messages[-1]
                        continue
                except:
                    pass
            time.sleep(self.check_interval)
        return False, "таймаут ожидания кнопки (блок кода)"


class CopyMessageButtonStrategy(ResponseReadyStrategy):
    """
    Ожидает появления кнопки копирования всего сообщения.
    Использует селектор copy_message_button.
    """
    def __init__(self, check_interval: float = 0.5):
        self.check_interval = check_interval

    def wait(self, driver, last_message_element: WebElement, timeout: float) -> tuple[bool, str]:
        start_time = time.time()
        while time.time() - start_time < timeout:
            try:
                copy_btn = last_message_element.find_element(By.CSS_SELECTOR, SELECTORS["copy_message_button"])
                if copy_btn and copy_btn.is_displayed():
                    return True, "появление кнопки копирования сообщения"
            except:
                pass
            time.sleep(self.check_interval)
        return False, "таймаут ожидания кнопки копирования сообщения"


class SendButtonStateStrategy(ResponseReadyStrategy):
    """
    Стратегия, отслеживающая состояние кнопки отправки.
    - Ждём, пока кнопка станет disabled (начало генерации).
    - Затем ждём, пока кнопка перестанет быть disabled (конец генерации).
    """
    def __init__(self, check_interval: float = 0.5):
        self.check_interval = check_interval

    def _get_send_button(self, driver):
        try:
            buttons = driver.find_elements(By.CSS_SELECTOR, "div[role='button']")
            for btn in buttons:
                classes = btn.get_attribute("class") or ""
                if "ds-button--circle" in classes:
                    return btn
        except:
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
    """
    Комбинированная стратегия: проверяет несколько условий.
    Порядок:
    1. Состояние кнопки отправки (disabled -> enabled).
    2. Появление кнопки копирования сообщения.
    3. Стабилизация текста.
    """
    def __init__(self,
                 text_strategy: TextStabilizationStrategy,
                 button_strategy: CopyButtonAppearanceStrategy,
                 send_button_strategy: SendButtonStateStrategy,
                 copy_message_strategy: CopyMessageButtonStrategy,
                 logger=None,
                 debug_interval: float = 2.0):
        self.text_strategy = text_strategy
        self.button_strategy = button_strategy
        self.send_button_strategy = send_button_strategy
        self.copy_message_strategy = copy_message_strategy
        self.logger = logger
        self.debug_interval = debug_interval

    def _log_element_state(self, driver):
        if not self.logger:
            return
        try:
            input_box = driver.find_element(By.CSS_SELECTOR, SELECTORS["input_textarea"])
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

    def wait(self, driver, last_message_element: WebElement, timeout: float) -> tuple[bool, str]:
        start_time = time.time()
        last_debug_time = start_time

        # 1. Пробуем стратегию по кнопке отправки (самая надёжная)
        ok, reason = self.send_button_strategy.wait(driver, last_message_element, timeout)
        if ok:
            return True, reason

        # 2. Пробуем стратегию появления кнопки копирования сообщения
        remaining = timeout - (time.time() - start_time)
        if remaining > 0:
            ok, reason = self.copy_message_strategy.wait(driver, last_message_element, remaining)
            if ok:
                return True, reason

        # 3. Пробуем стабилизацию текста + появление кнопки копирования блоков кода
        while time.time() - start_time < timeout:
            if self.logger and (time.time() - last_debug_time) >= self.debug_interval:
                self._log_element_state(driver)
                last_debug_time = time.time()

            # Проверяем кнопку копирования блоков кода
            try:
                copy_buttons = last_message_element.find_elements(By.CSS_SELECTOR, SELECTORS["copy_button"])
                if copy_buttons and copy_buttons[0].is_displayed():
                    # Если кнопка появилась, ждём стабилизации текста 1 секунду
                    remaining2 = timeout - (time.time() - start_time)
                    if remaining2 > 0:
                        check_timeout = min(remaining2, 1.0)
                        ok_stab, reason_stab = self.text_strategy.wait(driver, last_message_element, check_timeout)
                        if ok_stab:
                            return True, f"кнопка 'Копировать' (блок кода) + стабилизация ({reason_stab})"
                        else:
                            # если стабилизация не подтвердилась, продолжаем ждать
                            pass
            except:
                pass

            # Проверяем стабилизацию текста
            remaining2 = timeout - (time.time() - start_time)
            if remaining2 > 0:
                check_timeout = min(remaining2, 0.5)
                ok, reason = self.text_strategy.wait(driver, last_message_element, check_timeout)
                if ok:
                    return True, reason

            time.sleep(0.2)

        # Запасной вариант – полная стабилизация
        return self.text_strategy.wait(driver, last_message_element, timeout=5)


class ResponseReadyStrategyFactory:
    @staticmethod
    def get_strategy(name: str, logger=None, **kwargs):
        text_strategy = TextStabilizationStrategy(
            check_interval=kwargs.get('check_interval', 0.5),
            stable_duration=kwargs.get('stable_duration', 1.0)
        )
        button_strategy = CopyButtonAppearanceStrategy(
            check_interval=kwargs.get('check_interval', 0.5)
        )
        send_button_strategy = SendButtonStateStrategy(
            check_interval=kwargs.get('check_interval', 0.5)
        )
        copy_message_strategy = CopyMessageButtonStrategy(
            check_interval=kwargs.get('check_interval', 0.5)
        )

        if name == "text_stabilization":
            return text_strategy
        elif name == "copy_button":
            return button_strategy
        elif name == "send_button":
            return send_button_strategy
        elif name == "copy_message":
            return copy_message_strategy
        elif name == "combined":
            return CombinedStrategy(
                text_strategy,
                button_strategy,
                send_button_strategy,
                copy_message_strategy,
                logger=logger,
                debug_interval=kwargs.get('debug_interval', 2.0)
            )
        else:
            raise ValueError(f"Неизвестная стратегия: {name}")