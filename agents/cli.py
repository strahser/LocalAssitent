"""
cli.py — командная строка для запуска локальных агентов.

Примеры:
    python -m agents --list
    python -m agents web_search --query "python как читать файл" --max-results 5
    python -m agents page_parser --url https://example.com --max-chars 3000
    python -m agents local_data --query "TODO" --root . --max-results 10
    python -m agents qa --query "Что такое dataclass?" --context "..."
    python -m agents merge --root . --output context.txt
    python -m agents browser --url https://example.com --action open

Запуск: `python -m agents <name> [options]`. Выход: 0 — успех, 1 — ошибка.
"""
import argparse
import json
import sys

from agents.registry import get_agent, list_agents, run_agent


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="agents",
        description="Плагинные локальные агенты: "
        + ", ".join(list_agents()),
    )
    parser.add_argument("agent", nargs="?", help="Имя агента (см. --list)")
    parser.add_argument(
        "--list", action="store_true",
        help="Показать список доступных агентов и выйти",
    )
    parser.add_argument(
        "--query", default="",
        help="Запрос/вопрос (web_search, local_data, qa)",
    )
    parser.add_argument(
        "--root", default="",
        help="Корневая директория (local_data, merge)",
    )
    parser.add_argument(
        "--url", default="",
        help="URL (page_parser, browser)",
    )
    parser.add_argument(
        "--max-results", type=int, default=0,
        help="Максимум результатов (web_search, local_data)",
    )
    parser.add_argument(
        "--max-chars", type=int, default=0,
        help="Лимит символов извлечённого текста (page_parser)",
    )
    parser.add_argument(
        "--context", default="",
        help="Контекст для вопроса (qa)",
    )
    parser.add_argument(
        "--action", default="",
        help="Действие браузера: open/screenshot/extract_text (browser)",
    )
    parser.add_argument(
        "--output", default="",
        help="Выходной файл (merge: merged_context.txt, browser: screenshot.png)",
    )
    return parser


def _build_kwargs(name: str, args) -> dict:
    """Маппинг CLI-аргументов в kwargs конкретного агента (контракт)."""
    kwargs = {}
    if name == "web_search":
        if args.query:
            kwargs["query"] = args.query
        if args.max_results:
            kwargs["max_results"] = args.max_results
    elif name == "page_parser":
        if args.url:
            kwargs["url"] = args.url
        if args.max_chars:
            kwargs["max_chars"] = args.max_chars
    elif name == "local_data":
        if args.query:
            kwargs["query"] = args.query
        if args.root:
            kwargs["root"] = args.root
        if args.max_results:
            kwargs["max_results"] = args.max_results
    elif name == "qa":
        if args.query:
            kwargs["question"] = args.query
        if args.context:
            kwargs["context"] = args.context
    elif name == "browser":
        kwargs["action"] = args.action or "open"
        if args.url:
            kwargs["url"] = args.url
    elif name == "merge":
        if args.root:
            kwargs["root_dir"] = args.root
        if args.output:
            kwargs["output_file"] = args.output
    return kwargs


def main(argv=None) -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

    parser = build_parser()
    args = parser.parse_args(argv)

    if args.list or not args.agent:
        for name in list_agents():
            agent = get_agent(name)
            print(f"{name}: {agent.description}")
        return 0

    name = args.agent
    kwargs = _build_kwargs(name, args)

    try:
        result = run_agent(name, **kwargs)
    except KeyError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        print("Available agents: " + ", ".join(list_agents()), file=sys.stderr)
        return 1

    if not result.ok:
        print(f"ERROR: {result.error}", file=sys.stderr)
        return 1

    print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
