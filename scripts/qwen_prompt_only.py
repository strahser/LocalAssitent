"""
qwen_prompt_only.py — отправить БОЛЬШОЙ ПРОМПТ (без вложений) в открытый чат chat.qwen.ai.

Подключается к уже запущенному Edge (debug-порт 9222), НЕ открывает новый URL
(сохраняет текущую беседу), вставляет промпт в textarea, ждёт ответ, сохраняет.

Пример:
    python scripts/qwen_prompt_only.py --prompt-file prompt.md --output answer.md
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

from logger import Logger
from qwen.client import QwenClient


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="qwen_prompt_only")
    parser.add_argument("--prompt-file", required=True, help="Файл с текстом промпта")
    parser.add_argument("--output", default="qwen_answer.md", help="Выходной markdown")
    parser.add_argument("--port", type=int, default=9222, help="Debug-порт Edge")
    parser.add_argument("--timeout-thinking", type=float, default=180, dest="timeout_thinking")
    parser.add_argument("--timeout-answer", type=float, default=900, dest="timeout_answer")
    args = parser.parse_args(argv)

    logger = Logger(log_to_file=True, log_file="qwen_prompt_only.log")
    client = QwenClient(logger, url="https://chat.qwen.ai")

    with open(args.prompt_file, "r", encoding="utf-8") as f:
        prompt = f.read()
    logger.log(f"Промпт загружен: {len(prompt)} символов")

    client.connect(debug_port=args.port)

    # НЕ вызываем open_chat() — сохраняем текущую беседу пользователя.
    if not client.send_prompt(prompt):
        print("❌ Не удалось отправить промпт", file=sys.stderr)
        return 1
    print("✅ Промпт отправлен")

    snap = client.wait_thinking_started(args.timeout_thinking)
    client.monitor.log_stage("thinking_started", snap, 0)

    snap = client.wait_answer_ready(args.timeout_answer)
    client.monitor.log_stage("answer_ready", snap, 0)

    answer = client.extract_answer()
    if not answer:
        print("❌ Ответ не извлечён", file=sys.stderr)
        return 1

    output = client.save_answer(answer, args.output)
    print(f"✅ Ответ сохранён: {output} (длина {len(answer)})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
