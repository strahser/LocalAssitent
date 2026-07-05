# selectors.py – централизованное хранение CSS/XPath селекторов
# selectors.py – централизованное хранение CSS/XPath селекторов

SELECTORS = {
    "input_textarea": "textarea[placeholder*='Ask'], textarea",
    "send_button": "div[role='button']",  # упрощённый селектор
    "copy_button": "span.ds-button__content span.code-info-button-text",
    "new_chat_xpath": "//span[text()='New chat']",
    "assistant_messages": ".//div[contains(@class, 'message') and contains(@class, 'assistant')]",
}