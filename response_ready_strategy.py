# response_ready_strategy.py
import time
from abc import ABC, abstractmethod
from selenium.webdriver.remote.webelement import WebElement
from selenium.webdriver.common.by import By
from selenium.common.exceptions import StaleElementReferenceException, TimeoutException
from selectors import SELECTORS


class ResponseReadyStrategy(ABC):
    """Абстрактная стратегия определения готовности ответа."""

    @abstractmethod
    def wait(self, driver, last_message_element: WebElement, timeout: float) -> bool:
        """
        Ожидает готовности ответа.
        :param driver: экземпляр WebDriver
        :param last_message_element: элемент последнего сообщения ассистента
        :param timeout: максимальное время ожидания
        :return: True, если ответ готов, иначе False
        """
        pass


class TextStabilizationStrategy(ResponseReadyStrategy):
    """
    Стратегия по стабилизации текста: ждёт, пока текст в последнем сообщении перестанет меняться.
    """

    def __init__(self, check_interval: float = 0.5, stable_duration: float = 2.0):
        self.check_interval = check_interval
        self.stable_duration = stable_duration

    def wait(self, driver, last_message_element: WebElement, timeout: float) -> bool:
        start_time = time.time()
        stable_counter = 0.0
        last_text = None
        while time.time() - start_time < timeout:
            try:
                current_text = last_message_element.text
            except StaleElementReferenceException:
                # Если элемент устарел, пытаемся найти последнее сообщение заново
                try:
                    messages = driver.find_elements(By.XPATH, SELECTORS["assistant_messages"])
                    if messages:
                        last_message_element = messages[-1]
                        current_text = last_message_element.text
                    else:
                        return False
                except:
                    return False

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
                return True
            time.sleep(self.check_interval)
        return False


class CopyButtonAppearanceStrategy(ResponseReadyStrategy):
    """
    Стратегия по появлению кнопки «Копировать» в последнем сообщении.
    """

    def __init__(self, check_interval: float = 0.5):
        self.check_interval = check_interval

    def wait(self, driver, last_message_element: WebElement, timeout: float) -> bool:
        start_time = time.time()
        while time.time() - start_time < timeout:
            try:
                # Ищем кнопку копирования внутри сообщения
                copy_buttons = last_message_element.find_elements(By.CSS_SELECTOR, SELECTORS["copy_button"])
                if copy_buttons and copy_buttons[0].is_displayed():
                    return True
            except StaleElementReferenceException:
                # Если элемент устарел, перезапрашиваем последнее сообщение
                try:
                    messages = driver.find_elements(By.XPATH, SELECTORS["assistant_messages"])
                    if messages:
                        last_message_element = messages[-1]
                        continue
                except:
                    pass
                return False
            time.sleep(self.check_interval)
        return False


class CombinedStrategy(ResponseReadyStrategy):
    """
    Комбинированная стратегия: ждёт либо стабилизации текста, либо появления кнопки.
    """

    def __init__(self,
                 text_strategy: TextStabilizationStrategy,
                 button_strategy: CopyButtonAppearanceStrategy):
        self.text_strategy = text_strategy
        self.button_strategy = button_strategy

    def wait(self, driver, last_message_element: WebElement, timeout: float) -> bool:
        # Запускаем обе стратегии параллельно или последовательно? Для простоты попробуем сначала кнопку, потом текст.
        # Но можно и комбинировать: ждём до timeout, проверяя оба условия.
        start_time = time.time()
        while time.time() - start_time < timeout:
            # Проверяем кнопку
            try:
                copy_buttons = last_message_element.find_elements(By.CSS_SELECTOR, SELECTORS["copy_button"])
                if copy_buttons and copy_buttons[0].is_displayed():
                    return True
            except:
                pass
            # Проверяем стабильность (используем короткий интервал)
            # Здесь можно вызвать упрощённую проверку, но для простоты используем текст-стратегию с маленьким таймаутом
            # Но проще: попробуем вызвать wait с таймаутом 0.1? Нет, лучше отдельно.
            # Для простоты сделаем последовательно: сначала кнопка, потом текст.
            # Но можем просто вернуть результат одной из них, но лучше комбинировать.
            # Реализуем: проверяем стабильность с малым временем.
            # Используем внутренний метод для проверки стабильности за короткий интервал.
            # Однако, чтобы не усложнять, просто вернём результат от первой успешной.
            # Можно сделать так: если кнопка появилась – готово, иначе ждём стабилизации.
            # Поэтому в этом цикле сначала проверяем кнопку, если нет – ждём чек-интервал.
            time.sleep(0.2)
        # После timeout пробуем текстовую стабилизацию как запасной вариант
        return self.text_strategy.wait(driver, last_message_element, timeout=5)  # короткий запасной таймаут


class ResponseReadyStrategyFactory:
    """
    Фабрика для создания стратегий по имени.
    """
    @staticmethod
    def get_strategy(name: str, **kwargs):
        if name == "text_stabilization":
            return TextStabilizationStrategy(
                check_interval=kwargs.get('check_interval', 0.5),
                stable_duration=kwargs.get('stable_duration', 2.0)
            )
        elif name == "copy_button":
            return CopyButtonAppearanceStrategy(
                check_interval=kwargs.get('check_interval', 0.5)
            )
        elif name == "combined":
            text_strategy = TextStabilizationStrategy(
                check_interval=kwargs.get('check_interval', 0.5),
                stable_duration=kwargs.get('stable_duration', 2.0)
            )
            button_strategy = CopyButtonAppearanceStrategy(
                check_interval=kwargs.get('check_interval', 0.5)
            )
            return CombinedStrategy(text_strategy, button_strategy)
        else:
            raise ValueError(f"Неизвестная стратегия: {name}")