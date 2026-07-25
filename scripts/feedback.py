"""
Отправка файлов проекта в DeepSeek для обратной связи.

Использование:
    python scripts/feedback.py                # в текущем чате
    python scripts/feedback.py --new-chat     # в новом чате
"""
import argparse
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agent.client import SeleniumDeepSeekClient
from logger import Logger
from config import SELENIUM_CONFIG

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

KEY_FILES = [
    "main.py",
    "config.py",
    "scenarios.py",
    "agent/client.py",
    "agent/browser/manager.py",
    "agent/handlers/message_sender.py",
    "agent/handlers/response_reader.py",
    "agent/handlers/file_attacher.py",
    "detection/element_finder.py",
    "tools/safety.py",
    "tools/execute.py",
    "tools/read_file.py",
    "tests/test_safety.py",
]

PROMPT = """Проанализируй код проекта LocalAssitent и дай обратную связь.

## Описание
LocalAssitent — это локальный AI-агент, который автоматизирует веб-интерфейс DeepSeek Chat через Selenium + Edge CDP.

## Исходный код проекта

{code}

## Задача
Дай краткую обратную связь (300-500 слов):
1. Что сделано хорошо
2. Что можно улучшить в первую очередь
3. Критические замечания

Будь конкретным, указывай файлы и строки."""


def collect_code() -> str:
    parts = []
    for rel_path in KEY_FILES:
        abs_path = os.path.join(PROJECT_ROOT, rel_path)
        if os.path.exists(abs_path):
            try:
                with open(abs_path, "r", encoding="utf-8") as f:
                    content = f.read()
                parts.append(f"### {rel_path}\n```python\n{content}\n```\n")
            except Exception as e:
                parts.append(f"### {rel_path}\n[Ошибка: {e}]\n")
    return "\n".join(parts)


def main(new_chat: bool = False) -> bool:
    print("=" * 60)
    print("  Отправка файлов в DeepSeek")
    print("=" * 60)

    logger = Logger(
        log_to_html=False,
        log_to_file=True,
        save_responses=True,
        log_file="feedback.log",
        html_file="feedback_log.html",
    )

    print("\n[1/3] Сбор файлов...")
    code = collect_code()
    print(f"  Собрано {len(code)} символов из {len(KEY_FILES)} файлов")

    prompt = PROMPT.format(code=code)
    print(f"  Промпт: {len(prompt)} символов")

    print("\n[2/3] Подключение к браузеру...")
    client = SeleniumDeepSeekClient(logger, SELENIUM_CONFIG)

    if new_chat:
        print("  Создание нового чата...")
        client.new_chat()
        time.sleep(3)

    print("\n[3/3] Отправка и ожидание ответа...")
    print("  (это может занять 1-3 минуты)")
    start = time.time()
    result = client.send_message(prompt)
    elapsed = time.time() - start
    print(f"  Ответ получен за {elapsed:.1f} секунд")

    if result is None:
        print("\n[!] Не удалось получить ответ")
        client.close()
        logger.close()
        return False

    full_text, _ = result

    output_dir = os.path.join(PROJECT_ROOT, "pipeline_output")
    os.makedirs(output_dir, exist_ok=True)

    md_path = os.path.join(output_dir, "deepseek_feedback.md")
    with open(md_path, "w", encoding="utf-8") as f:
        f.write("# Обратная связь от DeepSeek\n\n")
        f.write(f"**Дата:** {time.strftime('%Y-%m-%d %H:%M:%S')}\n\n")
        f.write(f"**Время ответа:** {elapsed:.1f} сек\n\n")
        f.write("---\n\n")
        f.write(full_text)
    print(f"\n  Ответ сохранен: {md_path}")

    print("\n" + "=" * 60)
    print("  ГОТОВО")
    print("=" * 60)

    client.close()
    logger.close()
    return True


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Отправка файлов проекта в DeepSeek")
    parser.add_argument("--new-chat", action="store_true", help="Создать новый чат")
    args = parser.parse_args()
    success = main(new_chat=args.new_chat)
    sys.exit(0 if success else 1)
