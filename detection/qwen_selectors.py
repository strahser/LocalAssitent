"""
qwen_selectors.py – селекторы интерфейса Qwen Chat (chat.qwen.ai).

Селекторы основаны на:
  - наблюдаемом HTML (модель-selector): .index-module__model-selector___rdCim,
    .index-module__model-selector-text___XvWe0, .ant-dropdown-trigger (2026-08-01);
  - общих паттернах Ant Design (dropdown-меню) и конвенциях Qwen UI.

ВАЖНО: UI Qwen часто меняется (CSS-module хэши вида ___rdCim нестабильны),
поэтому каждый ключ содержит СПИСОК фолбэков (как в detection/selectors.py),
и используются contains-матчи/XPATH по тексту, где возможно.
"""
QWEN_SELECTORS = {
    # === Поле ввода ===
    "input_textarea": [
        "textarea.message-input-textarea",
        "textarea[placeholder*='Ask']",
        "textarea",
        "div[contenteditable='true']",
    ],

    # === Кнопка отправки ===
    "send_button": [
        "button.send-button",
        "button.send-button:not([disabled])",
        "div[role='button'][aria-label='Отправить сообщение']",
        "div.omni-button-content-btn",
        "div[role='button'].ant-btn-primary",
        "div[role='button'] svg[data-icon='send']",
        "div[role='button']",
    ],

    # === Сообщения ассистента ===
    "assistant_messages": [
        "//div[contains(@class, 'qwen-chat-message-assistant')]",
        ".//div[contains(@class, 'chat') and contains(@class, 'assistant')]",
        ".//div[contains(@class, 'message') and contains(@class, 'assistant')]",
        ".//div[contains(@class, 'answer')]",
        ".//article",
        "//div[@role='article']",
    ],

    # === Селектор модели (dropdown) ===
    # Триггер: кликабельный элемент с названием текущей модели
    "model_selector": [
        "div[role='button'][aria-label='Select Model']",
        "div.index-module__model-selector___rdCim",
        "div[class*='model-selector']",
        "div[class*='model-selector'] span[class*='model-selector-text']",
        "span[class*='model-selector-text']",
        "div.ant-dropdown-trigger",
    ],
    "model_selector_text": [
        "div[class*='model-selector-text']",
        "span[class*='model-selector-text']",
        "div[class*='model-selector'] span",
    ],

    # Пункты выпадающего меню моделей (наблюдаемый HTML 2026-08-01):
    #   список: div.index-module__model-list___-NnN5[role='listbox']
    #   пункт:  div.index-module__model-item___MkLlj[role='option']
    #           имя:   div.index-module__model-item-name___X8Hec span
    "model_options": [
        "div[role='option'][class*='model-item']",
        "li.ant-dropdown-menu-item",
        ".ant-dropdown-menu-item",
        "div.ant-select-item",
        ".ant-select-item-option",
    ],
    "model_option_by_text_xpath": (
        "//*[contains(@class, 'model-item') and @role='option']"
        "[contains(., '{model}')]"
        "| //*[contains(@class, 'ant-dropdown-menu-item') or contains(@class, 'ant-select-item')]"
        "[contains(., '{model}')]"
    ),

    # === Копирование / код ===
    # Кнопки копирования блоков кода / сообщений Qwen (аналог copy_answer_button
    # из qwen/selectors.py + data-testid/class-фолбэки).
    "copy_button": [
        "button[aria-label*='copy' i]",
        "[data-testid*='copy' i]",
        "div[role='button'][aria-label*='copy' i]",
        "button[class*='copy' i]",
    ],
    "copy_message_button": [
        "div[data-testid='copy-button']",
        "button[aria-label*='Copy']",
        "div[role='button']:not(.ant-btn-primary)",
    ],
    "code_block": [
        "div[class*='code-block']",
        "pre",
    ],

    # === Прикрепление файлов ===
    "attach_button": [
        "div[role='button'] svg[data-icon='paperclip']",
        "div[role='button'] svg[data-icon='attach']",
        "div.anticon-paperclip",
        "input[type='file']",
    ],
    "file_input": "input[type='file']",

    # === Новый чат ===
    "new_chat_xpath": [
        "//span[contains(text(), 'New chat')]",
        "//button[contains(text(), 'New chat')]",
        "//span[contains(text(), 'Новый чат')]",
        "//div[contains(@class, 'new-chat')]",
    ],

    # === Ошибки ===
    "error_elements": [
        "//div[contains(text(), 'error') or contains(text(), 'Error')]",
        "//div[@role='alert']",
    ],
}
