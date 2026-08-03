"""
cli.py — командная строка пакета tools: `python -m tools ...`.

Примеры:
    python -m tools --list
    python -m tools read_file tools/safety.py
    python -m tools grep_search --pattern "TODO" --root . --include "*.py" --max-results 10
    python -m tools edit_file --path src/x.py --old "a" --new "b"
    python -m tools append_file --path notes.md --content "текст"
    python -m tools delete_file --path tmp.txt

По образцу agents/cli.py: `--list` выводит список инструментов, запуск
инструмента по имени, маппинг CLI-флагов в kwargs через _build_kwargs.
Выход: 0 — успех, 1 — ошибка.
"""
from __future__ import annotations

import argparse
import inspect
import json
import sys
from typing import Any, Dict, List, Optional, Sequence

from tools.registry import get_tool, list_tools, run_tool


def _coerce_value(value: str) -> Any:
    """Преобразует CLI-строку в int/bool, если это однозначно возможно."""
    if isinstance(value, str):
        stripped = value.strip()
        if stripped.lstrip("-").isdigit():
            return int(stripped)
        if stripped.lower() in ("true", "false"):
            return stripped.lower() == "true"
    return value


def _build_kwargs(extra: Sequence[str]) -> Dict[str, Any]:
    """Маппит флаги `--param value` / `--param=value` / `--flag` в kwargs.

    Позиционные аргументы собираются в список под ключом '_positional'
    (инструмент сам решает, как их использовать).
    """
    kwargs: Dict[str, Any] = {}
    positional: List[str] = []
    tokens = list(extra)
    i = 0
    while i < len(tokens):
        token = tokens[i]
        if token.startswith("--"):
            key = token[2:].replace("-", "_")
            if "=" in key:
                name, _, raw = key.partition("=")
                kwargs[name] = _coerce_value(raw)
            else:
                if i + 1 < len(tokens) and not tokens[i + 1].startswith("--"):
                    kwargs[key] = _coerce_value(tokens[i + 1])
                    i += 1
                else:
                    kwargs[key] = True
        else:
            positional.append(token)
        i += 1
    if positional:
        kwargs["_positional"] = positional
    return kwargs


def _resolve_positional(tool, kwargs: Dict[str, Any]) -> Dict[str, Any]:
    """Распаковывает позиционные аргументы в kwargs по сигнатуре инструмента.

    Позиционные значения (под ключом '_positional') сопоставляются с
    позиционными параметрами функции инструмента слева направо.
    """
    positional = kwargs.pop("_positional", None)
    if not positional:
        return kwargs
    try:
        params = list(inspect.signature(tool).parameters.values())
    except (ValueError, TypeError):
        return kwargs
    positional_params = [p for p in params if p.kind in (
        inspect.Parameter.POSITIONAL_ONLY,
        inspect.Parameter.POSITIONAL_OR_KEYWORD,
    )]
    for idx, value in enumerate(positional[:len(positional_params)]):
        name = positional_params[idx].name
        if name.startswith("_") or name in kwargs:
            continue
        kwargs[name] = _coerce_value(value) if isinstance(value, str) else value
    return kwargs


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="tools",
        description="Плагинные инструменты локального агента: "
        + ", ".join(list_tools()),
    )
    parser.add_argument("tool", nargs="?", help="Имя инструмента (см. --list)")
    parser.add_argument(
        "--list", action="store_true",
        help="Показать список доступных инструментов и выйти",
    )
    parser.add_argument("extra", nargs=argparse.REMAINDER,
                        help="Аргументы инструмента (--param value / позиционные)")
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

    parser = build_parser()
    args = parser.parse_args(argv)

    if args.list or not args.tool:
        for name in list_tools():
            print(name)
        return 0

    name = args.tool
    kwargs = _build_kwargs(args.extra)

    try:
        tool = get_tool(name)
    except KeyError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        print("Available tools: " + ", ".join(list_tools()), file=sys.stderr)
        return 1

    kwargs = _resolve_positional(tool, kwargs)

    try:
        result = run_tool(name, **kwargs)
    except TypeError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    if result is None:
        return 0

    if isinstance(result, str):
        print(result)
    else:
        try:
            print(json.dumps(result, ensure_ascii=False, indent=2))
        except TypeError:
            print(result)
    return 0


if __name__ == "__main__":
    sys.exit(main())
