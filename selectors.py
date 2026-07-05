SELECTORS = {
    "input_textarea": "textarea[placeholder*='Ask'], textarea",
    "send_button": "div[role='button']",
    "copy_button": "span.ds-button__content span.code-info-button-text",  # для блоков кода (не используется)
    "action_panel_container": ".//div[contains(@class, 'ds-flex') and not(ancestor::*[contains(@class, 'code') or contains(@class, 'highlight')])]",
    "assistant_messages": [
        ".//div[contains(@class, 'message') and contains(@class, 'assistant')]",
        ".//div[contains(@class, 'message')]",
        ".//div[contains(@class, 'assistant')]"
    ],
    "new_chat_xpath": "//span[text()='New chat']",
}