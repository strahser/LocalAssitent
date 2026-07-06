import time
from abc import ABC, abstractmethod
from selenium.webdriver.common.by import By
from selenium.common.exceptions import StaleElementReferenceException
from core.message_finder import MessageFinder

class ResponseReadyStrategy(ABC):
    @abstractmethod
    def wait(self, driver, timeout: float) -> tuple[bool, str]:
        pass

class TextStabilizationStrategy(ResponseReadyStrategy):
    def __init__(self, check_interval: float = 1.0, stable_duration: float = 2.0):
        self.check_interval = check_interval
        self.stable_duration = stable_duration

    def wait(self, driver, timeout: float) -> tuple[bool, str]:
        start_time = time.time()
        stable_counter = 0.0
        last_text = None
        message_finder = MessageFinder(driver, None)
        while time.time() - start_time < timeout:
            last_msg = message_finder.get_last_assistant_message()
            if last_msg is None:
                time.sleep(self.check_interval)
                continue
            try:
                current_text = last_msg.text
            except StaleElementReferenceException:
                time.sleep(self.check_interval)
                continue
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
    def __init__(self, check_interval: float = 1.0):
        self.check_interval = check_interval

    def wait(self, driver, timeout: float) -> tuple[bool, str]:
        start_time = time.time()
        message_finder = MessageFinder(driver, None)
        while time.time() - start_time < timeout:
            last_msg = message_finder.get_last_assistant_message()
            if last_msg is None:
                time.sleep(self.check_interval)
                continue
            try:
                copy_buttons = last_msg.find_elements(By.CSS_SELECTOR, "span.ds-button__content span.code-info-button-text")
                if copy_buttons and copy_buttons[0].is_displayed():
                    return True, "появление кнопки 'Копировать'"
            except StaleElementReferenceException:
                pass
            time.sleep(self.check_interval)
        return False, "таймаут ожидания кнопки"

class SendButtonStateStrategy(ResponseReadyStrategy):
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

    def wait(self, driver, timeout: float) -> tuple[bool, str]:
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
            else:
                if not is_disabled:
                    return True, "кнопка отправки стала активной"
            time.sleep(self.check_interval)
        return False, "таймаут состояния кнопки"

class ActionPanelStrategy(ResponseReadyStrategy):
    def __init__(self, driver, config, check_interval: float = 1.0, logger=None):
        self.driver = driver
        self.config = config
        self.check_interval = check_interval
        self.logger = logger

    def wait(self, driver, timeout: float) -> tuple[bool, str]:
        if self.logger:
            self.logger.debug("Ожидание появления панели с 5 кнопками...")
        start_time = time.time()
        message_finder = MessageFinder(driver, self.config, logger=self.logger)
        while time.time() - start_time < timeout:
            last_msg = message_finder.get_last_assistant_message()
            if last_msg is None:
                time.sleep(self.check_interval)
                continue
            try:
                containers = last_msg.find_elements(By.XPATH, self.config.selectors["action_panel_container"])
                for container in containers:
                    buttons = container.find_elements(By.CSS_SELECTOR, "div[role='button']")
                    if len(buttons) == 5:
                        if self.logger:
                            self.logger.debug("Панель с 5 кнопками появилась.")
                        return True, "панель с 5 кнопками"
            except StaleElementReferenceException:
                pass
            except Exception:
                pass
            time.sleep(self.check_interval)
        return False, "таймаут ожидания панели"

class PanelCountStrategy(ResponseReadyStrategy):
    def __init__(self, driver, config, check_interval: float = 30.0, logger=None):
        self.driver = driver
        self.config = config
        self.check_interval = check_interval
        self.logger = logger

    def _count_panels(self, driver) -> int:
        xpath = ".//div[contains(@class, 'ds-flex') and not(ancestor::*[contains(@class, 'code') or contains(@class, 'highlight')]) and count(./div[@role='button']) = 5]"
        try:
            elements = driver.find_elements(By.XPATH, xpath)
            return len(elements)
        except Exception as e:
            if self.logger:
                self.logger.debug(f"Ошибка подсчета панелей: {e}")
            return 0

    def wait(self, driver, timeout: float) -> tuple[bool, str]:
        if self.logger:
            self.logger.debug(f"Ожидание увеличения количества панелей с 5 кнопками (интервал {self.check_interval} сек)...")
        initial_count = self._count_panels(driver)
        if self.logger:
            self.logger.debug(f"Начальное количество панелей: {initial_count}")
        start_time = time.time()
        current_count = initial_count
        while time.time() - start_time < timeout:
            time.sleep(self.check_interval)
            current_count = self._count_panels(driver)
            if current_count > initial_count:
                if self.logger:
                    self.logger.debug(f"Количество панелей увеличилось до {current_count} (было {initial_count}).")
                return True, f"увеличение панелей до {current_count}"
            else:
                if self.logger:
                    self.logger.debug(f"Количество панелей: {current_count} (ожидается > {initial_count})")
        return False, f"таймаут ожидания увеличения панелей (было {initial_count}, осталось {current_count})"

class CombinedStrategy(ResponseReadyStrategy):
    def __init__(self, text_strategy, button_strategy, send_button_strategy,
                 action_panel_strategy, panel_count_strategy=None,
                 logger=None, debug_interval: float = 2.0):
        self.text_strategy = text_strategy
        self.button_strategy = button_strategy
        self.send_button_strategy = send_button_strategy
        self.action_panel_strategy = action_panel_strategy
        self.panel_count_strategy = panel_count_strategy
        self.logger = logger
        self.debug_interval = debug_interval

    def wait(self, driver, timeout: float) -> tuple[bool, str]:
        start_time = time.time()
        if self.panel_count_strategy:
            ok, reason = self.panel_count_strategy.wait(driver, timeout)
            if ok:
                return True, reason
        remaining = timeout - (time.time() - start_time)
        if remaining > 0:
            ok, reason = self.action_panel_strategy.wait(driver, remaining)
            if ok:
                return True, reason
        remaining = timeout - (time.time() - start_time)
        if remaining > 0:
            ok, reason = self.send_button_strategy.wait(driver, remaining)
            if ok:
                return True, reason
        while time.time() - start_time < timeout:
            ok, _ = self.button_strategy.wait(driver, min(timeout - (time.time() - start_time), 0.5))
            if ok:
                rem = timeout - (time.time() - start_time)
                if rem > 0:
                    ok2, _ = self.text_strategy.wait(driver, min(rem, 1.0))
                    if ok2:
                        return True, "кнопка 'Копировать' + стабилизация"
            rem = timeout - (time.time() - start_time)
            if rem > 0:
                ok, reason = self.text_strategy.wait(driver, min(rem, 0.5))
                if ok:
                    return True, reason
            time.sleep(0.2)
        return self.text_strategy.wait(driver, 5)

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
            driver, config,
            check_interval=kwargs.get('check_interval', 1.0),
            logger=logger
        )
        panel_count_strategy = PanelCountStrategy(
            driver=driver, config=config,
            check_interval=kwargs.get('panel_check_interval', 30.0),
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
        elif name == "panel_count":
            return panel_count_strategy
        elif name == "combined":
            return CombinedStrategy(
                text_strategy, button_strategy, send_button_strategy,
                action_panel_strategy, panel_count_strategy,
                logger=logger,
                debug_interval=kwargs.get('debug_interval', 2.0)
            )
        else:
            raise ValueError(f"Неизвестная стратегия: {name}")
