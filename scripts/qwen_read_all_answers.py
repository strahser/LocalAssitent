"""
Чтение ВСЕХ ответов ассистента из уже открытого чата chat.qwen.ai.

Для каждого ответа: наведение → снятие класса скрытия футера → клик по кнопке
«Копировать» → чтение буфера обмена → нормализация текста → сохранение в markdown.

Использует QwenClient.extract_all_answers / save_all_answers (qwen/client.py).

Пример:
    python scripts/qwen_read_all_answers.py [--port 9222] [--output out.md]

Браузер Edge должен быть запущен с --remote-debugging-port=<port> и открыт нужный чат.
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

from selenium import webdriver
from selenium.webdriver.edge.options import Options

from logger import Logger
from qwen.client import QwenClient

OUTPUT_DEFAULT = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "pipeline_output", "qwen_chat_all_answers.md",
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="qwen_read_all_answers",
        description="Копирование всех ответов Qwen из открытого чата в markdown",
        epilog=(
            "Примеры:\n"
            "  python scripts/qwen_read_all_answers.py\n"
            "  python scripts/qwen_read_all_answers.py --port 9222\n"
            "  python scripts/qwen_read_all_answers.py --output out.md\n"
        ),
    )
    parser.add_argument("--port", type=int, default=9222,
                        help="Порт отладки Edge (по умолчанию 9222)")
    parser.add_argument("--output", default=OUTPUT_DEFAULT,
                        help="Выходной markdown-файл")
    parser.add_argument("--url", default="https://chat.qwen.ai",
                        help="URL чата (нужен только для журнала)")
    return parser


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)

    logger = Logger(log_to_file=True, log_file="qwen_read_all_answers.log")

    options = Options()
    options.add_experimental_option("debuggerAddress", f"127.0.0.1:{args.port}")
    options.page_load_strategy = "eager"
    driver = webdriver.Edge(options=options)

    client = QwenClient(logger, driver=driver, url=args.url)
    client.connect()

    print(f"URL: {driver.current_url}")
    answers = client.extract_all_answers()

    if not answers:
        print("❌ Ответы ассистента не найдены. Убедитесь, что открыт нужный чат.")
        return 1

    for a in answers:
        status = "ERR: " + (a["error"] or "") if a["error"] else "OK"
        print(f"  Ответ {a['index']}: {len(a['text'])} симв. — {status}")

    out = client.save_all_answers(answers, args.output,
                                  chat_id=driver.current_url.rstrip("/").rsplit("/", 1)[-1])
    print(f"✅ Сохранено: {out}")

    try:
        driver.quit()
    except Exception:
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
