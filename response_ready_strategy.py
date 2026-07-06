# response_ready_strategy.py
import time
from abc import ABC, abstractmethod
from selenium.webdriver.remote.webelement import WebElement
from selenium.webdriver.common.by import By
from selenium.common.exceptions import StaleElementReferenceException
from custom_selectors import SELECTORS
from action_panel_finder import ActionPanelFinder


class ResponseReadyStrategy(ABC):
    @abstractmethod
    def wait(self, driver, last_message_element: WebElement, timeout: float) -> tuple[bool, str]:
        pass


class TextStabilizationStrategy(ResponseReadyStrategy):
    def __init__(self, check_interval: float = 1.0, stable_duration: float = 2.0):
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
    """Ожидает появления кнопки копирования для блоков кода."""
    def __init__(self, check_interval: float = 1.0):
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


class SendButtonStateStrategy(ResponseReadyStrategy):
    """Отслеживает состояние кнопки отправки (disabled -> enabled)."""
    def __init__(self, check_interval: float = 1.0):
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




class ActionPanelStrategy(ResponseReadyStrategy):
    def __init__(self, driver, config, check_interval: float = 1.0, logger=None):
        self.driver = driver
        self.config = config
        self.check_interval = check_interval
        self.logger = logger
        self.panel_finder = ActionPanelFinder(driver, config, logger)

    def wait(self, driver, last_message_element: WebElement, timeout: float) -> tuple[bool, str]:
        if self.logger:
            self.logger.log("⏳ Ожидание появления панели с 5 кнопками...")
        start_time = time.time()
        while time.time() - start_time < timeout:
            try:
                # Проверяем, что элемент не устарел
                _ = last_message_element.tag_name
            except StaleElementReferenceException:
                # Обновляем ссылку на последнее сообщение
                try:
                    messages = driver.find_elements(By.XPATH, SELECTORS["assistant_messages"])
                    if messages:
                        last_message_element = messages[-1]
                        if self.logger:
                            self.logger.log("🔄 Обновлена ссылка на последнее сообщение.")
                    else:
                        time.sleep(self.check_interval)
                        continue
                except:
                    time.sleep(self.check_interval)
                    continue

            try:
                panel = self.panel_finder._find_action_panel(last_message_element)
                if panel:
                    buttons = panel.find_elements(By.CSS_SELECTOR, "div[role='button']")
                    if len(buttons) == 5:
                        if self.logger:
                            self.logger.log("✅ Панель с 5 кнопками появилась.")
                        return True, "панель с 5 кнопками"
            except StaleElementReferenceException:
                # Если элемент устарел в процессе, просто продолжим
                pass
            except Exception:
                pass
            time.sleep(self.check_interval)
        return False, "таймаут ожидания панели"


class CombinedStrategy(ResponseReadyStrategy):
    def __init__(self,
                 text_strategy: TextStabilizationStrategy,
                 button_strategy: CopyButtonAppearanceStrategy,
                 send_button_strategy: SendButtonStateStrategy,
                 action_panel_strategy: ActionPanelStrategy,
                 logger=None,
                 debug_interval: float = 2.0):
        self.text_strategy = text_strategy
        self.button_strategy = button_strategy
        self.send_button_strategy = send_button_strategy
        self.action_panel_strategy = action_panel_strategy
        self.logger = logger
        self.debug_interval = debug_interval

    def wait(self, driver, last_message_element: WebElement, timeout: float) -> tuple[bool, str]:
        start_time = time.time()
        last_debug_time = start_time

        # 1. Самая надёжная стратегия – панель с 5 кнопками
        ok, reason = self.action_panel_strategy.wait(driver, last_message_element, timeout)
        if ok:
            return True, reason

        # 2. Кнопка отправки (disabled -> enabled)
        remaining = timeout - (time.time() - start_time)
        if remaining > 0:
            ok, reason = self.send_button_strategy.wait(driver, last_message_element, remaining)
            if ok:
                return True, reason

        # 3. Стабилизация текста + кнопка копирования блоков кода
        while time.time() - start_time < timeout:
            # Проверяем кнопку копирования блоков кода
            try:
                copy_buttons = last_message_element.find_elements(By.CSS_SELECTOR, SELECTORS["copy_button"])
                if copy_buttons and copy_buttons[0].is_displayed():
                    remaining2 = timeout - (time.time() - start_time)
                    if remaining2 > 0:
                        check_timeout = min(remaining2, 1.0)
                        ok_stab, reason_stab = self.text_strategy.wait(driver, last_message_element, check_timeout)
                        if ok_stab:
                            return True, f"кнопка 'Копировать' (блок кода) + стабилизация"
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

        return self.text_strategy.wait(driver, last_message_element, timeout=5)


class ResponseReadyStrategyFactory:
    @staticmethod
    def get_strategy(name: str, driver=None, config=None, logger=None, **kwargs):
        text_strategy = TextStabilizationStrategy(
            check_interval=kwargs.get('check_interval', 1.0),
            stable_duration=kwargs.get('stable_duration', 2.0)
        )
        button_strategy = CopyButtonAppearanceStrategy(
            check_interval=kwargs.get('check_interval', 1.0)
        )
        send_button_strategy = SendButtonStateStrategy(
            check_interval=kwargs.get('check_interval', 1.0)
        )
        action_panel_strategy = ActionPanelStrategy(
            driver,
            config,
            check_interval=kwargs.get('check_interval', 1.0),
            logger=logger
        )

        if name == "text_stabilization":
            return text_strategy
        elif name == "copy_button":
            return button_strategy
        elif name == "send_button":
            return send_button_strategy
        elif name == "action_panel":
            return action_panel_strategy
        elif name == "combined":
            return CombinedStrategy(
                text_strategy,
                button_strategy,
                send_button_strategy,
                action_panel_strategy,
                logger=logger,
                debug_interval=kwargs.get('debug_interval', 2.0)
            )
        else:
            raise ValueError(f"Неизвестная стратегия: {name}")