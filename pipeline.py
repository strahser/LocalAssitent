"""
Pipeline: Сбор файлов проекта → Запрос к DeepSeek → Сохранение ответа

Использование:
    python pipeline.py                              # стандартный pipeline
    python pipeline.py --merged <файл.txt>          # из merged-файла
    python pipeline.py --prompt-file <промпт.txt>   # свой промпт
"""
import argparse
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import SELENIUM_CONFIG, PIPELINE_FILES
from agent.deepseek_client import DeepSeekClient
from logger import Logger


PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))

DEFAULT_PROMPT = """Проанализируй код проекта LocalAssitent и дай рекомендации по улучшению.

## Описание проекта
LocalAssitent — это локальный AI-агент, который автоматизирует веб-интерфейс DeepSeek Chat через Selenium + Edge CDP.

## Исходный код проекта

{code}

## Задача
Проанализируй код и дай конкретные рекомендации по улучшению:
1. Архитектура и структура
2. Надежность и обработка ошибок
3. Безопасность
4. Производительность
5. Тестируемость
6. Новые возможности

Для каждой рекомендации укажи файлы, пример кода и приоритет."""


def collect_project_code() -> str:
    """Собирает код всех ключевых файлов проекта."""
    parts = []
    for rel_path in PIPELINE_FILES:
        abs_path = os.path.join(PROJECT_ROOT, rel_path)
        if os.path.exists(abs_path):
            try:
                with open(abs_path, "r", encoding="utf-8") as f:
                    content = f.read()
                parts.append(f"### Файл: {rel_path}\n```python\n{content}\n```\n")
            except Exception as e:
                parts.append(f"### Файл: {rel_path}\n[Ошибка чтения: {e}]\n")
        else:
            parts.append(f"### Файл: {rel_path}\n[Файл не найден]\n")
    return "\n".join(parts)


def load_merged_file(merged_path: str) -> str:
    """Читает merged-файл целиком."""
    with open(merged_path, "r", encoding="utf-8") as f:
        return f.read()


def run_pipeline(merged_file: str = None, prompt_file: str = None, prompt_text: str = None):
    """Основной pipeline: сбор → запрос → сохранение."""
    print("=" * 60)
    print("  PIPELINE: Анализ проекта LocalAssitent через DeepSeek")
    print("=" * 60)

    logger = Logger(
        log_to_html=False,
        log_to_file=True,
        save_responses=True,
        log_file=os.path.join(PROJECT_ROOT, "pipeline.log"),
        html_file=os.path.join(PROJECT_ROOT, "pipeline_log.html"),
    )

    if merged_file:
        print(f"\n[1/4] Чтение merged-файла: {merged_file}")
        prompt = load_merged_file(merged_file)
        print(f"  Прочитано: {len(prompt)} символов")
    else:
        print("\n[1/4] Сбор кода проекта...")
        code = collect_project_code()
        print(f"  Собрано {len(code)} символов из {len(PIPELINE_FILES)} файлов")

        if prompt_file:
            with open(prompt_file, "r", encoding="utf-8") as f:
                template = f.read()
        else:
            template = DEFAULT_PROMPT

        prompt = template.format(code=code) if "{code}" in template else template + "\n\n" + code
        print(f"  Промпт: {len(prompt)} символов")

    print("\n[2/4] Подключение к DeepSeek...")
    timeout = 300
    client = DeepSeekClient(
        logger,
        timeout=timeout,
        email=os.environ.get("DEEPSEEK_EMAIL", ""),
        password=os.environ.get("DEEPSEEK_PASSWORD", ""),
    )

    print("\n[3/4] Отправка запроса и ожидание ответа...")
    print("  (это может занять 1-3 минуты)")
    start_time = time.time()
    result = client.send_prompt_with_code(prompt)
    elapsed = time.time() - start_time
    print(f"  Ответ получен за {elapsed:.1f} секунд")

    if result is None:
        print("\n[!] Не удалось получить ответ от DeepSeek")
        logger.log("Pipeline завершен с ошибкой: ответ не получен", "ERROR")
        client.close()
        logger.close()
        return False

    full_text, code_text = result

    print("\n[4/4] Сохранение ответа...")
    output_dir = os.path.join(PROJECT_ROOT, "pipeline_output")
    os.makedirs(output_dir, exist_ok=True)

    md_path = os.path.join(output_dir, "deepseek_analysis.md")
    with open(md_path, "w", encoding="utf-8") as f:
        f.write("# Анализ проекта LocalAssitent от DeepSeek\n\n")
        f.write(f"**Дата:** {time.strftime('%Y-%m-%d %H:%M:%S')}\n\n")
        f.write(f"**Время ответа:** {elapsed:.1f} сек\n\n")
        f.write("---\n\n")
        f.write(full_text)
    print(f"  Ответ сохранен: {md_path}")

    if code_text:
        code_path = os.path.join(output_dir, "suggested_code.py")
        with open(code_path, "w", encoding="utf-8") as f:
            f.write(code_text)
        print(f"  Код сохранен: {code_path}")

    print("\n" + "=" * 60)
    print("  PIPELINE ЗАВЕРШЕН УСПЕШНО")
    print(f"  Результат: {md_path}")
    print("=" * 60)

    client.close()
    logger.close()
    return True


def main():
    parser = argparse.ArgumentParser(description="Pipeline анализа проекта через DeepSeek")
    parser.add_argument("--merged", help="Путь к merged TXT-файлу (вместо сбора файлов)")
    parser.add_argument("--prompt-file", help="Файл с промптом")
    parser.add_argument("--prompt", help="Текст промпта (inline)")
    parser.add_argument("--email", default=None, help="Email для DeepSeek")
    parser.add_argument("--password", default=None, help="Пароль для DeepSeek")
    args = parser.parse_args()

    if args.email:
        os.environ["DEEPSEEK_EMAIL"] = args.email
    if args.password:
        os.environ["DEEPSEEK_PASSWORD"] = args.password

    success = run_pipeline(
        merged_file=args.merged,
        prompt_file=args.prompt_file,
        prompt_text=args.prompt,
    )
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
