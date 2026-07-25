"""
Отправка короткого промпта в DeepSeek для проверки.
"""
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agent.client import SeleniumDeepSeekClient
from logger import Logger
from config import SELENIUM_CONFIG


PROMPT = """Привет! Это тестовое сообщение. Ответь одним словом: "Работает" """


def main():
    print("=" * 60)
    print("  Тестовое сообщение в DeepSeek")
    print("=" * 60)

    logger = Logger(
        log_to_html=False,
        log_to_file=True,
        save_responses=True,
        log_file="test_send.log",
        html_file="test_send_log.html"
    )

    print("\n[1/2] Подключение к браузеру...")
    client = SeleniumDeepSeekClient(logger, SELENIUM_CONFIG)
    
    print("\n  Создание нового чата...")
    client.new_chat()
    time.sleep(3)

    print("\n[2/2] Отправка тестового сообщения...")
    start = time.time()
    result = client.send_message(PROMPT)
    elapsed = time.time() - start
    print(f"  Ответ получен за {elapsed:.1f} секунд")

    if result is None:
        print("\n[!] Не удалось получить ответ")
        client.close()
        logger.close()
        return False

    full_text, code_text = result
    print(f"\n  Ответ: {full_text}")

    client.close()
    logger.close()
    return True


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
