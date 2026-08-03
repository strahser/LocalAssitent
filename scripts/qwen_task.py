"""
qwen_task.py — CLI: запуск задачи в chat.qwen.ai (файл → ответ).

Пример:
    python scripts/qwen_task.py --file task.txt --prompt "Проанализируй" \
        --output answer.md --port 9222

Выход: 0 — успех, 1 — ошибка.
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

from Logger import Logger
from qwen.client import QwenClient


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="qwen_task",
        description="Задача для chat.qwen.ai: файл → промпт → ответ",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Примеры:\n"
            "  python scripts/qwen_task.py --file task.txt --prompt \"Анализ\"\n"
            "  python scripts/qwen_task.py --file task.txt --prompt \"Анализ\" "
            "--output answer.md --port 9222\n"
        ),
    )
    parser.add_argument("--file", required=True, help="Путь к файлу-заданию")
    parser.add_argument("--prompt", required=True, help="Промпт к файлу")
    parser.add_argument("--output", default="qwen_answer.md",
                        help="Выходной markdown-файл (по умолчанию qwen_answer.md)")
    parser.add_argument("--port", type=int, default=9222,
                        help="Порт отладки Edge (по умолчанию 9222)")
    parser.add_argument("--url", default="https://chat.qwen.ai", help="URL чата")
    parser.add_argument("--timeout-file", type=float, default=30, dest="timeout_file",
                        help="Таймаут ожидания файла (сек)")
    parser.add_argument("--timeout-thinking", type=float, default=120,
                        dest="timeout_thinking", help="Таймаут начала генерации (сек)")
    parser.add_argument("--timeout-answer", type=float, default=600,
                        dest="timeout_answer", help="Таймаут ответа (сек)")
    return parser


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)

    logger = Logger(log_to_file=True, log_file="qwen_task.log")
    client = QwenClient(logger, url=args.url)

    logger.log(f"🚀 qwen_task: file={args.file}")
    client.connect(debug_port=args.port)

    result = client.run_task(
        file_path=args.file,
        prompt=args.prompt,
        output_file=args.output,
        timeout_file=args.timeout_file,
        timeout_thinking=args.timeout_thinking,
        timeout_answer=args.timeout_answer,
    )

    stages = result["stages"]
    print(f"🏁 file_received:    {stages['file_received']:.1f}s")
    print(f"🏁 thinking_started: {stages['thinking_started']:.1f}s")
    print(f"🏁 answer_ready:     {stages['answer_ready']:.1f}s")

    if result["ok"]:
        print(f"✅ Ответ сохранён: {result['output_file']} "
              f"(длина {len(result['answer'])})")
        return 0
    print(f"❌ Ошибка: {result['error']}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
