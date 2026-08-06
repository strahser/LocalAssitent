"""Tests for detection/response_ready.py optimization (offline, no selenium).

Покрывает:
  - factory принимает selectors и передаёт их стратегиям;
  - CopyButtonCountStrategy: счётчик растёт -> не готов; стабилен >0 -> готов;
  - TextStabilizationStrategy: стабильный текст + innerHTML -> готов;
  - CombinedStrategy: короткий ответ + кнопки копирования -> быстрый возврат.

Запуск: py -m pytest tests/test_response_ready_optimized.py -q
"""
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from detection.response_ready import (
    ResponseReadyStrategyFactory,
    CopyButtonCountStrategy,
    TextStabilizationStrategy,
    CombinedStrategy,
)
from detection.qwen_selectors import QWEN_SELECTORS


class FakeButton:
    def __init__(self, displayed=True):
        self._displayed = displayed

    def is_displayed(self):
        return self._displayed


class FakeElement:
    """Эмуляция WebElement: управляемый текст, innerHTML, кнопки."""

    def __init__(self, text="", html_len=0, buttons=None):
        self.text = text
        self._html_len = html_len
        self._buttons = buttons or []  # list[FakeButton]

    def find_elements(self, by, selector):
        # Упрощение: любой CSS-селектор возвращает наши кнопки
        return list(self._buttons)

    def find_element(self, by, selector):
        if self._buttons:
            return self._buttons[0]
        raise Exception("not found")

    def get_attribute(self, name):
        if name == "innerHTML":
            return "x" * self._html_len
        return None


class FakeDriver:
    """Эмуляция WebDriver: execute_script возвращает innerHTML length."""

    def __init__(self, messages=None):
        self.messages = messages or []

    def execute_script(self, script, element=None):
        if element is not None and hasattr(element, "_html_len"):
            return element._html_len
        return 0

    def find_elements(self, by, selector):
        return list(self.messages)


class GrowingElement:
    """Элемент, чей текст/кнопки растут при каждом обращении, потом стабилизируются.

    Каждый доступ (find_elements ИЛИ .text) инкрементирует счётчик чтений;
    кнопки копирования появляются после growth_steps чтений.
    """

    def __init__(self, growth_steps=3, final_text="Ответ готов" * 3, buttons_count=2):
        self._steps = growth_steps
        self._reads = 0
        self.final_text = final_text
        self.buttons_count = buttons_count

    def _tick(self):
        self._reads += 1
        return self._reads

    def _buttons(self):
        if self._tick() >= self._steps:
            return [FakeButton() for _ in range(self.buttons_count)]
        return []

    def find_elements(self, by, selector):
        return self._buttons()

    def find_element(self, by, selector):
        b = self._buttons()
        if b:
            return b[0]
        raise Exception("not found")

    @property
    def text(self):
        self._tick()
        return self.final_text


def test_factory_passes_selectors_to_strategies():
    for name in ("text_stabilization", "copy_button", "send_button",
                 "copy_message", "copy_count", "combined"):
        s = ResponseReadyStrategyFactory.get_strategy(name, selectors=QWEN_SELECTORS)
        assert s is not None
        # стратегии должны нести переданные селекторы
        assert getattr(s, "selectors", None) == QWEN_SELECTORS


def test_copy_button_count_grows_then_stable():
    el = GrowingElement(growth_steps=2, buttons_count=3)
    driver = FakeDriver()
    strat = CopyButtonCountStrategy(check_interval=0.05, stable_duration=0.15)
    ok, reason = strat.wait(driver, el, timeout=3.0)
    assert ok is True
    assert "стабильно" in reason


def test_copy_button_count_never_appears():
    el = FakeElement(text="долгий ответ без кода", html_len=50, buttons=[])
    driver = FakeDriver()
    strat = CopyButtonCountStrategy(check_interval=0.05, stable_duration=0.1)
    ok, reason = strat.wait(driver, el, timeout=0.5)
    assert ok is False


def test_text_stabilization_with_innerhtml():
    el = FakeElement(text="Стабильный ответ", html_len=120, buttons=[])
    driver = FakeDriver()
    strat = TextStabilizationStrategy(check_interval=0.05, stable_duration=0.15)
    ok, reason = strat.wait(driver, el, timeout=2.0)
    assert ok is True
    assert "стабилизация" in reason


def test_combined_short_answer_quick():
    """Короткий ответ (5 символов) + стабильные кнопки копирования -> быстро."""
    el = GrowingElement(growth_steps=1, final_text="Да.", buttons_count=2)
    driver = FakeDriver()
    strat = ResponseReadyStrategyFactory.get_strategy("combined", min_content_length=10)
    t0 = time.time()
    ok, reason = strat.wait(driver, el, timeout=10.0)
    elapsed = time.time() - t0
    assert ok is True
    assert elapsed < 3.0, f"должен вернуться быстро, заняло {elapsed:.2f}s"


def test_combined_falls_back_to_stabilization():
    """Ответ без кнопок копирования -> подтверждение через стабилизацию текста."""
    el = FakeElement(text="Обычный текстовый ответ без кода", html_len=200, buttons=[])
    driver = FakeDriver()
    strat = ResponseReadyStrategyFactory.get_strategy(
        "combined", check_interval=0.05, stable_duration=0.15, min_content_length=5
    )
    ok, reason = strat.wait(driver, el, timeout=5.0)
    assert ok is True


def test_factory_unknown_strategy_raises():
    try:
        ResponseReadyStrategyFactory.get_strategy("nope")
        assert False, "должно бросить ValueError"
    except ValueError:
        pass
