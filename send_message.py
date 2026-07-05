# send_message.py
import sys
import io
import argparse
from config import SELENIUM_CONFIG
from Logger import Logger
from selenium_client import SeleniumDeepSeekClient

# Настройка кодировок для консоли
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')
sys.stdin = io.TextIOWrapper(sys.stdin.buffer, encoding='utf-8')


def main():
    # Разбор аргументов командной строки
    parser = argparse.ArgumentParser(description="Selenium клиент для DeepSeek")
    parser.add_argument("--new-chat", action="store_true", help="Создать новый чат")
    parser.add_argument("--copy", action="store_true", help="Скопировать последний ответ")
    parser.add_argument("--send", action="store_true", help="Отправить сообщение (по умолчанию)")
    args = parser.parse_args()

    # Инициализируем логгер (для вывода сообщений, можно использовать простой логгер)
    # В этом скрипте мы используем логгер только для консоли, но можно и в файл.
    logger = Logger(log_to_file=False, log_to_html=False)

    try:
        client = SeleniumDeepSeekClient(logger, SELENIUM_CONFIG)
    except Exception as e:
        logger.log(f"Не удалось инициализировать клиент: {e}", "ERROR")
        sys.exit(1)

    if args.new_chat:
        success = client.new_chat()
        client.close()
        sys.exit(0 if success else 1)
    elif args.copy:
        result = client.copy_last_response()
        client.close()
        if result is not None:
            print(result)
            sys.exit(0)
        else:
            sys.exit(1)
    else:
        # По умолчанию --send: читаем сообщение из stdin
        message = sys.stdin.read().strip()
        if not message:
            # Если не передано сообщение, используем тестовое
            message = "Привет! Расскажи, как дела?"
        result = client.send_message(message)
        client.close()
        if result is not None:
            print(result)
            sys.exit(0)
        else:
            sys.exit(1)


if __name__ == "__main__":
    main()