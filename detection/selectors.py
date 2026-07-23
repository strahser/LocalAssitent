SELECTORS = {
    # === Поле ввода ===
    "input_textarea": [
        "textarea._27c9245",
        "textarea[placeholder*='Ask'], textarea",
        "textarea",
        "div[contenteditable='true']"
    ],

    # === Кнопка отправки ===
    "send_button": "div[role='button'].ds-button--circle",
    "send_button_circle": "div[role='button']",

    # === Сообщения ассистента ===
    "assistant_messages": [
        ".//div[contains(@class, 'message') and contains(@class, 'assistant')]",
        ".//div[contains(@class, 'ds-article')]",
        ".//div[contains(@class, '_0fcaa63')]",
        ".//div[contains(@class, 'assistant')]",
        ".//article",
        "//div[contains(@class, 'message')]",
        "//div[@role='article']"
    ],

    # === Копирование всего сообщения ===
    "copy_message_button": [
        "div[data-testid='copy-button']",
        "button[aria-label*='Copy']",
        "div[role='button']:not(.ds-button--circle)"
    ],

    # === Блоки кода — новый точный парсинг ===
    "code_block": [
        "div.md-code-block",
        "div.ds-markdown-code-block"
    ],
    "code_block_copy_button": [
        "button.ds-markdown-code-copy-button",
        "span.code-info-button-text"
    ],
    "code_block_pre": "pre",
    "code_language_label": "span.d813de27",

    # === Кнопка копирования для блоков кода (старый селектор) ===
    "copy_button": "span.ds-button__content span.code-info-button-text",

    # === Панель действий (для копирования сообщения) ===
    "action_panel_container": ".//div[contains(@class, 'ds-flex') and not(ancestor::*[contains(@class, 'code') or contains(@class, 'highlight')])]",

    # === Прикрепление файлов ===
    "attach_button": [
        "div[role='button'].ds-button--iconLabelPrimary",
        "div[role='button'] svg path[d*='M5.5498 9.75']/ancestor::div[role='button']",
        "div.ds-icon-button"
    ],
    "file_input": "input[type='file']",

    # === Новый чат ===
    "new_chat_xpath": [
        "//span[text()='New chat']",
        "//span[text()='New Chat']",
        "//a[contains(text(), 'New chat')]",
        "//span[contains(text(), 'Новый чат')]",
        "//a[contains(text(), 'Новый чат')]",
        "//button[contains(text(), 'Новый чат')]",
        "//*[contains(@class, 'new-chat') or contains(@class, 'newChat')]"
    ],

    # === Ошибки ===
    "error_elements": [
        "//div[contains(text(), 'error') or contains(text(), 'Error')]",
        "//div[contains(@class, 'error')]",
        "//div[@role='alert']"
    ],

    # === Селектор для кнопки отправки (send button state) ===
    "send_button_state": "div[role='button']"
}
