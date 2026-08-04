"""
send_to_cloud.py – отправить файл/merged-текст выбранному провайдеру и модели.

Использование (CLI):
    python -m tools.send_to_cloud --provider qwen --model Qwen3.8-Max-Preview --file merged.txt
    python -m tools.send_to_cloud --text "анализируй: ..." --provider deepseek
    python -m tools.send_to_cloud <source> [--provider qwen] [--model ...] [--output file.md] [--new-chat]

Как инструмент сценария (возвращает строку):
    from tools.send_to_cloud import send_to_cloud
    result = send_to_cloud("merged_context.txt", provider="qwen", model="Qwen3.8-Max-Preview")
"""
import argparse
import os
import sys
import time
from pathlib import Path


def _build_client(provider: str, logger, email: str = "", password: str = ""):
    """Создаёт клиент провайдера (ленивый импорт — клиенты подключают браузер)."""
    if provider == "qwen":
        from agent.QwenClient import QwenClient
        return QwenClient(logger, email=email, password=password)
    from agent.DeepSeekClient import DeepSeekClient
    return DeepSeekClient(logger, email=email, password=password)


def send_to_cloud(
    source: str,
    provider: str = "deepseek",
    model: str = None,
    output: str = None,
    new_chat: bool = False,
    prompt: str = None,
) -> str:
    """
    Отправляет содержимое файла (или inline-текст) в облачный чат и сохраняет ответ.

    Args:
        source: путь к файлу (TXT/MD/merged) ИЛИ сам текст, если файла нет.
        provider: 'deepseek' | 'qwen'.
        model: модель (обязательна/рекомендуется для qwen, напр. Qwen3.8-Max-Preview).
        output: куда сохранить ответ (по умолчанию pipeline_output/<provider>_response.md).
        new_chat: начать новый чат перед отправкой.
        prompt: доп. инструкция к содержимому source.

    Returns:
        Строка вида "OK: ..." или "ERROR: ..." (конвенция tools-модулей).
    """
    try:
        from Logger import Logger
        from config import PROVIDERS, DEFAULT_QWEN_MODEL
    except Exception as e:
        return f"ERROR: не удалось импортировать config/logger: {e}"

    if provider not in PROVIDERS:
        return f"ERROR: неизвестный провайдер '{provider}'. Доступны: {', '.join(PROVIDERS.keys())}"

    if model is None:
        model = DEFAULT_QWEN_MODEL if provider == "qwen" else ""

    # source: файл или inline-текст
    src_path = Path(source)
    if src_path.exists() and src_path.is_file():
        try:
            content = src_path.read_text(encoding="utf-8", errors="replace")
            label = f"файл {source}"
        except Exception as e:
            return f"ERROR: не удалось прочитать {source}: {e}"
    else:
        content = source
        label = "inline-текст"
        src_path = Path("inline_input.txt")

    full_prompt = content
    if prompt:
        full_prompt = f"{prompt}\n\n---\n\n{content}"

    logger = Logger(
        log_to_html=False,
        log_to_file=True,
        save_responses=True,
        log_file="send_to_cloud.log",
        html_file="send_to_cloud_log.html",
    )

    client = None
    try:
        email = os.environ.get(f"{provider.upper()}_EMAIL", os.environ.get("DEEPSEEK_EMAIL", ""))
        password = os.environ.get(f"{provider.upper()}_PASSWORD", os.environ.get("DEEPSEEK_PASSWORD", ""))
        client = _build_client(provider, logger, email=email, password=password)

        if new_chat:
            client.new_chat()
            time.sleep(2)

        if provider == "qwen" and model:
            sel = getattr(client, "select_model", None)
            if sel is not None:
                sel(model)

        result = client.send_prompt_with_code(full_prompt)
        if result is None:
            return f"ERROR: ответ от {provider} не получен"

        full_text, _ = result
    except Exception as e:
        return f"ERROR: {e}"
    finally:
        if client is not None:
            try:
                client.close()
            except Exception:
                pass
        logger.close()

    if output is None:
        out_dir = Path("pipeline_output")
        out_dir.mkdir(parents=True, exist_ok=True)
        model_tag = f"_{model}" if model else ""
        output = str(out_dir / f"{provider}{model_tag}_response.md")

    out_path = Path(output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        f"# Ответ {provider}{(' (' + model + ')') if model else ''}\n\n"
        f"**Источник:** {label}\n"
        f"**Дата:** {time.strftime('%Y-%m-%d %H:%M:%S')}\n\n"
        f"---\n\n{full_text}",
        encoding="utf-8",
    )
    return f"OK: ответ {provider} сохранён в {output} ({len(full_text)} символов)"


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

    parser = argparse.ArgumentParser(description="Отправка файла/текста в облачный чат")
    parser.add_argument("source", nargs="?", default=None,
                        help="Путь к файлу (или inline-текст)")
    parser.add_argument("--file", default=None,
                        help="Путь к файлу/merged-тексту для отправки")
    parser.add_argument("--text", default=None,
                        help="Inline-текст для отправки")
    parser.add_argument("--provider", default="deepseek", choices=["deepseek", "qwen"])
    parser.add_argument("--model", default=None, help="Модель (для qwen, напр. Qwen3.8-Max-Preview)")
    parser.add_argument("--output", "-o", default=None, help="Куда сохранить ответ")
    parser.add_argument("--new-chat", action="store_true", help="Начать новый чат")
    parser.add_argument("--prompt", default=None, help="Дополнительная инструкция")
    args = parser.parse_args()

    src = args.file or args.text or args.source
    if not src:
        parser.error("укажите источник: позиционный аргумент, --file или --text")

    result = send_to_cloud(
        source=src,
        provider=args.provider,
        model=args.model,
        output=args.output,
        new_chat=args.new_chat,
        prompt=args.prompt,
    )
    print(result)
    sys.exit(0 if result.startswith("OK") else 1)


if __name__ == "__main__":
    main()
