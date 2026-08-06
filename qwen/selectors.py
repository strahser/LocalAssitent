"""
selectors.py — CSS-селекторы для chat.qwen.ai.

Каждое значение — список селекторов в порядке приоритета:
HtmlChangeMonitor.marker / QwenClient используют первый совпавший.
"""
QWEN_SELECTORS = {
    # === Поле ввода ===
    "input_textarea": [
        "textarea",
        "div[contenteditable='true']",
        "[contenteditable='true']",
    ],

    # === Кнопка отправки ===
    "send_button": [
        "button[type='submit']",
        "div[role='button'][aria-label*='send' i]",
        "button[aria-label*='Send' i]",
    ],

    # === Кнопка копирования ответа ===
    # Наблюдаемый DOM (2026-08-06): кнопка div[role='button'][aria-label='Копировать']
    # в .response-message-footer, который СКРЫТ классом 'response-message-footer-none'
    # до наведения мыши на сообщение. См. README «Известные проблемы Qwen UI».
    "copy_answer_button": [
        "div[role='button'][aria-label='Копировать']",
        "div[role='button'][aria-label='Copy']",
        "button.copy-response-button",
        "button[aria-label*='copy' i]",
        "[data-testid*='copy' i]",
        "div[role='button'][aria-label*='copy' i]",
        "button[class*='copy' i]",
    ],

    # === Футер сообщения (панель действий: копировать/голосовать и т.п.) ===
    "response_footer": [
        "div.response-message-footer",
        "div[class*='message-footer']",
    ],

    # === Индикатор «думает» / загрузка ===
    "thinking_indicator": [
        "[class*='thinking' i]",
        "[class*='spinner' i]",
        "[class*='loading' i]",
        "div[class*='reasoning' i]",
    ],

    # === Чип прикреплённого файла ===
    "file_chip": [
        "[class*='file' i][class*='chip' i]",
        "[class*='attachment' i]",
        "[class*='file-preview' i]",
        "[class*='upload' i]",
    ],

    # === Контейнер чата ===
    "chat_container": [
        "main",
        "[class*='chat' i]",
        "div[class*='conversation' i]",
    ],

    # === Сообщение пользователя ===
    "user_message": [
        "[class*='user' i][class*='message' i]",
        "[data-role='user']",
        "div[class*='user']",
    ],

    # === Сообщение ассистента ===
    "assistant_message": [
        "[class*='assistant' i][class*='message' i]",
        "[data-role='assistant']",
        "article",
    ],
}
