"""
Test selectors for Qwen Chat UI (chat.qwen.ai) against real HTML fragments.
Uses regex-based pattern matching to verify CSS/XPath selectors.

Run:  python tests/test_qwen_selectors.py   (standalone)
      python -m pytest tests/test_qwen_selectors.py -q
"""
import os
import re
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from detection.qwen_selectors import QWEN_SELECTORS

# === HTML-фрагменты на основе реального DOM Qwen (2026-08-01) ===

MODEL_SELECTOR_HTML = """
<div class="index-module__model-selector___rdCim ant-dropdown-trigger">
  <div class="index-module__model-selector-text___XvWe0">Qwen3.8-Max-Preview</div>
  <span class="anticon anticon-down"></span>
</div>
"""

MODEL_DROPDOWN_HTML = """
<ul class="ant-dropdown-menu" role="menu">
  <li class="ant-dropdown-menu-item" role="menuitem">Qwen3.8-Max-Preview</li>
  <li class="ant-dropdown-menu-item" role="menuitem">Qwen3-Max</li>
  <li class="ant-dropdown-menu-item" role="menuitem">Qwen-Max</li>
</ul>
"""

CHAT_HTML = """
<div class="chat-container">
  <div class="chat answer">
    <article>Пользователь отправил код.</article>
  </div>
  <div class="chat assistant">
    <article>Вот улучшенная версия кода:</article>
  </div>
</div>
"""

INPUT_HTML = """
<div class="index-module__chat-input___abc">
  <textarea placeholder="Ask anything..."></textarea>
  <div role="button" class="ant-btn ant-btn-primary">
    <span class="anticon anticon-send"></span>
  </div>
</div>
"""


def has_class(tag_html, class_name):
    m = re.search(r'class="([^"]*)"', tag_html)
    if not m:
        return False
    return class_name in m.group(1).split()


def count_tags(html, tag, class_name=None, attr_contains=None):
    pattern = rf'<{tag}\b[^>]*>'
    count = 0
    for m in re.finditer(pattern, html, re.DOTALL):
        tag_html = m.group()
        if class_name and not has_class(tag_html, class_name):
            continue
        if attr_contains:
            k, v = attr_contains
            if not re.search(rf'{k}\s*=\s*"[^"]*{re.escape(v)}[^"]*"', tag_html):
                continue
        count += 1
    return count


def test_model_selector_present():
    """Селектор модели (.index-module__model-selector___) присутствует в QWEN_SELECTORS."""
    sel = QWEN_SELECTORS["model_selector"]
    assert isinstance(sel, list) and len(sel) >= 3, "model_selector должен быть списком фолбэков"
    # Класс из реального HTML должен входить в фолбэки
    assert any("model-selector" in s for s in sel), "нет фолбэка по model-selector"


def test_model_selector_matches_html():
    """Реальный класс .index-module__model-selector___rdCim матчится фолбэком contains."""
    found = any(
        re.search(r'class="[^"]*model-selector[^"]*"', MODEL_SELECTOR_HTML)
        for _ in [0]
    )
    assert found, "class*='model-selector' должен находить элемент в HTML"
    assert count_tags(MODEL_SELECTOR_HTML, "div", class_name="index-module__model-selector___rdCim") == 1


def test_model_selector_text_matches():
    """Текст текущей модели виден в .index-module__model-selector-text__."""
    assert count_tags(MODEL_SELECTOR_HTML, "div", class_name="index-module__model-selector-text___XvWe0") == 1
    m = re.search(r'<div[^>]*model-selector-text[^>]*>(Qwen[^<]*)</div>', MODEL_SELECTOR_HTML)
    assert m and m.group(1) == "Qwen3.8-Max-Preview", "текст модели должен быть Qwen3.8-Max-Preview"


def test_model_options_match():
    """Пункты dropdown (.ant-dropdown-menu-item) матчатся селектором model_options."""
    sel = QWEN_SELECTORS["model_options"]
    assert any("ant-dropdown-menu-item" in s for s in sel), "model_options должен включать ant-dropdown-menu-item"
    assert count_tags(MODEL_DROPDOWN_HTML, "li", class_name="ant-dropdown-menu-item") == 3


def test_model_option_by_text_xpath():
    """XPath по тексту модели (fallback для стабильности) находит Qwen3.8-Max-Preview."""
    xp = QWEN_SELECTORS["model_option_by_text_xpath"]
    assert "{model}" in xp, "XPath должен содержать плейсхолдер {model}"
    xp_filled = xp.format(model="Qwen3.8-Max-Preview")
    # contains(., '...') в xpath → проверяем, что текст присутствует в HTML
    assert re.search(re.escape("Qwen3.8-Max-Preview"), MODEL_DROPDOWN_HTML)
    assert "contains" in xp_filled


def test_input_textarea_matches():
    """textarea матчится селектором input_textarea."""
    assert count_tags(INPUT_HTML, "textarea") == 1
    sel = QWEN_SELECTORS["input_textarea"]
    assert any("textarea" in s for s in sel)


def test_send_button_matches():
    """Кнопка отправки (ant-btn-primary) матчится селектором send_button."""
    assert count_tags(INPUT_HTML, "div", class_name="ant-btn-primary") == 1
    sel = QWEN_SELECTORS["send_button"]
    assert any("ant-btn-primary" in s for s in sel)


def test_assistant_messages_matches():
    """Блоки ответов ассистента матчатся (contains 'assistant')."""
    assert count_tags(CHAT_HTML, "div", class_name="assistant") == 1
    sel = QWEN_SELECTORS["assistant_messages"]
    assert any("assistant" in s for s in sel)


def test_structural_validity():
    """Все ключи QWEN_SELECTORS — непустые списки строк."""
    for key, val in QWEN_SELECTORS.items():
        assert val, f"ключ {key} пуст"
        if isinstance(val, list):
            assert all(isinstance(x, str) for x in val), f"ключ {key}: элементы должны быть строками"


if __name__ == "__main__":
    # Standalone runner (как в test_selectors.py)
    tests = [
        test_model_selector_present, test_model_selector_matches_html,
        test_model_selector_text_matches, test_model_options_match,
        test_model_option_by_text_xpath, test_input_textarea_matches,
        test_send_button_matches, test_assistant_messages_matches,
        test_structural_validity,
    ]
    passed = 0
    for t in tests:
        try:
            t()
            print(f"  [PASS] {t.__name__}")
            passed += 1
        except AssertionError as e:
            print(f"  [FAIL] {t.__name__}: {e}")
    total = len(tests)
    print("=" * 55)
    print(f"RESULT: {passed}/{total} tests passed")
    print("=" * 55)
    sys.exit(0 if passed == total else 1)
