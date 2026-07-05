# selectors.py – централизованное хранение CSS/XPath селекторов

SELECTORS = {
    "input_textarea": "textarea[placeholder*='Ask'], textarea",   # убрали динамический класс
    "send_button": "button[type='submit'], button[aria-label*='Send' i], button[aria-label*='Отправить' i], button.send, button[class*='send'], button[class*='submit']",
    "copy_button": "span.ds-button__content span.code-info-button-text",
    "new_chat_xpath": "//span[text()='New chat']",
    "assistant_messages": ".//div[contains(@class, 'message') and contains(@class, 'assistant')]",
}