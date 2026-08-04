"""
list_models.py – показать доступные провайдеры и модели облачных чатов.

Использование:
    python -m tools.list_models
"""
import sys


def list_models() -> str:
    """Возвращает строку со списком провайдеров и моделей (конвенция tools-модулей)."""
    try:
        from config import PROVIDERS, QWEN_MODELS, DEFAULT_QWEN_MODEL
    except Exception as e:
        return f"ERROR: не удалось импортировать config: {e}"

    lines = []
    lines.append("Доступные провайдеры облачных чатов:")
    for name, info in PROVIDERS.items():
        lines.append(f"  {name}: {info.get('name', name)} — {info.get('url', '')}")
    lines.append("")
    lines.append("Модели Qwen (облачный чат):")
    for m in QWEN_MODELS:
        marker = " (по умолчанию)" if m == DEFAULT_QWEN_MODEL else ""
        lines.append(f"  - {m}{marker}")
    return "\n".join(lines)


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    print(list_models())


if __name__ == "__main__":
    main()
