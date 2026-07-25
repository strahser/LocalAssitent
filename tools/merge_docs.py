"""
merge_docs.py – инструмент сведения документов для передачи внешнему ИИ.

Собирает файлы проекта (преимущественно C#) в один TXT-файл,
удобный для загрузки через эмуляцию кнопки загрузки в браузере.

Использование:
    python tools/merge_docs.py <директория> [опции]

Примеры:
    python tools/merge_docs.py . --ext .cs .py --output project_context.txt
    python tools/merge_docs.py . --pattern "*.cs" --max-size 50000
    python tools/merge_docs.py . --config merge_config.json
"""
import os
import sys
import json
import argparse
import fnmatch
from pathlib import Path
from datetime import datetime
from typing import List, Set, Optional

DEFAULT_EXTENSIONS = [".cs", ".py", ".xaml", ".csproj", ".sln", ".json", ".xml", ".config"]
DEFAULT_EXCLUDE_DIRS = {
    "__pycache__", ".git", ".venv", "venv", "node_modules",
    "build", "dist", ".idea", ".vs", "bin", "obj",
    "packages", ".opencode",
}
MAX_FILE_SIZE_DEFAULT = 100_000  # 100KB


def collect_files(
    root_dir: str,
    extensions: Optional[List[str]] = None,
    exclude_dirs: Optional[Set[str]] = None,
    include_patterns: Optional[List[str]] = None,
    exclude_patterns: Optional[List[str]] = None,
    max_file_size: int = MAX_FILE_SIZE_DEFAULT,
) -> List[Path]:
    """Собирает список файлов по критериям."""
    if extensions is None:
        extensions = DEFAULT_EXTENSIONS
    if exclude_dirs is None:
        exclude_dirs = DEFAULT_EXCLUDE_DIRS
    if include_patterns is None:
        include_patterns = []
    if exclude_patterns is None:
        exclude_patterns = []

    root = Path(root_dir).resolve()
    files = []

    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in exclude_dirs]

        for filename in filenames:
            filepath = Path(dirpath) / filename
            rel_path = filepath.relative_to(root)

            ext = filepath.suffix.lower()
            if extensions and ext not in extensions:
                continue

            if filepath.stat().st_size > max_file_size:
                continue

            if include_patterns and not any(
                fnmatch.fnmatch(str(rel_path), p) for p in include_patterns
            ):
                continue

            if any(fnmatch.fnmatch(str(rel_path), p) for p in exclude_patterns):
                continue

            files.append(filepath)

    files.sort(key=lambda f: (f.suffix, str(f.relative_to(root))))
    return files


def format_file_block(filepath: Path, root: Path, encoding: str = "utf-8") -> str:
    """Форматирует один файл как блок в выходном TXT."""
    rel_path = filepath.relative_to(root)
    try:
        content = filepath.read_text(encoding=encoding, errors="replace")
    except Exception as e:
        return (
            f"{'=' * 72}\n"
            f"FILE: {rel_path}\n"
            f"SIZE: {filepath.stat().st_size} bytes\n"
            f"ERROR: {e}\n"
            f"{'=' * 72}\n"
        )

    lines = content.splitlines()
    line_count = len(lines)

    separator = "=" * 72
    header = (
        f"{separator}\n"
        f"FILE: {rel_path}\n"
        f"LINES: {line_count}\n"
        f"SIZE: {filepath.stat().st_size} bytes\n"
        f"{separator}\n"
    )
    return header + content + "\n\n"


def merge_documents(
    root_dir: str,
    output_file: str = "merged_context.txt",
    extensions: Optional[List[str]] = None,
    exclude_dirs: Optional[Set[str]] = None,
    include_patterns: Optional[List[str]] = None,
    exclude_patterns: Optional[List[str]] = None,
    max_file_size: int = MAX_FILE_SIZE_DEFAULT,
    encoding: str = "utf-8",
    add_summary: bool = True,
    prompt: str = None,
    prompt_file: str = None,
) -> str:
    """Основная функция: собирает файлы и записывает в один TXT."""
    root = Path(root_dir).resolve()
    files = collect_files(
        root, extensions, exclude_dirs,
        include_patterns, exclude_patterns, max_file_size,
    )

    if not files:
        return "Файлы не найдены по указанным критериям."

    parts = []

    if add_summary:
        ext_stats = {}
        total_lines = 0
        for f in files:
            ext = f.suffix.lower()
            try:
                content = f.read_text(encoding=encoding, errors="replace")
                lines = len(content.splitlines())
            except Exception:
                lines = 0
            ext_stats[ext] = ext_stats.get(ext, 0) + 1
            total_lines += lines

        summary = (
            f"{'#' * 72}\n"
            f"# MERGED PROJECT CONTEXT\n"
            f"# Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
            f"# Project root: {root}\n"
            f"# Total files: {len(files)}\n"
            f"# Total lines: {total_lines}\n"
            f"# Extensions: {ext_stats}\n"
            f"{'#' * 72}\n\n"
        )
        parts.append(summary)

    for filepath in files:
        parts.append(format_file_block(filepath, root, encoding))

    prompt_text = None
    if prompt_file:
        pf = Path(prompt_file)
        if pf.exists():
            prompt_text = pf.read_text(encoding=encoding, errors="replace")
    if prompt and not prompt_text:
        prompt_text = prompt

    if prompt_text:
        parts.append(
            f"\n{'#' * 72}\n"
            f"# INSTRUCTION FOR AI\n"
            f"{'#' * 72}\n\n"
            f"{prompt_text}\n"
        )

    output_path = Path(output_file)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("".join(parts), encoding=encoding)

    return (
        f"Готово: {len(files)} файлов → {output_file}\n"
        f"Размер: {output_path.stat().st_size:,} байт"
    )


def load_config(config_path: str) -> dict:
    """Загружает JSON-конфиг для merge_docs."""
    with open(config_path, "r", encoding="utf-8") as f:
        return json.load(f)


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

    parser = argparse.ArgumentParser(
        description="Сведение документов проекта в один TXT для передачи внешнему ИИ",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Примеры:
  python tools/merge_docs.py . --ext .cs .py
  python tools/merge_docs.py . --ext .cs --output revit_plugin_context.txt
  python tools/merge_docs.py . --config merge_config.json
  python tools/merge_docs.py . --include "*.Command.cs" --exclude "*Tests*"
        """,
    )
    parser.add_argument("directory", help="Корневая директория проекта")
    parser.add_argument(
        "--ext", nargs="+", default=None,
        help=f"Расширения файлов (по умолчанию: {DEFAULT_EXTENSIONS})",
    )
    parser.add_argument(
        "--output", "-o", default="merged_context.txt",
        help="Выходной TXT-файл (по умолчанию: merged_context.txt)",
    )
    parser.add_argument(
        "--max-size", type=int, default=MAX_FILE_SIZE_DEFAULT,
        help=f"Макс. размер файла в байтах (по умолчанию: {MAX_FILE_SIZE_DEFAULT})",
    )
    parser.add_argument(
        "--include", nargs="*", default=None,
        help="Glob-паттерны для включения (например: *.cs *.xaml)",
    )
    parser.add_argument(
        "--exclude", nargs="*", default=None,
        help="Glob-паттерны для исключения (например: *Tests*)",
    )
    parser.add_argument(
        "--exclude-dir", nargs="*", default=None,
        help="Директории для исключения",
    )
    parser.add_argument(
        "--config", help="JSON-конфигурационный файл",
    )
    parser.add_argument(
        "--no-summary", action="store_true",
        help="Не добавлять сводную таблицу в начало файла",
    )
    parser.add_argument(
        "--encoding", default="utf-8",
        help="Кодировка файлов (по умолчанию: utf-8)",
    )
    parser.add_argument(
        "--prompt", default=None,
        help="Текст промпта для ИИ (добавляется в конец файла)",
    )
    parser.add_argument(
        "--prompt-file", default=None,
        help="Файл с промптом для ИИ (добавляется в конец merged-файла)",
    )

    args = parser.parse_args()

    if args.config:
        cfg = load_config(args.config)
        extensions = cfg.get("extensions", args.ext)
        exclude_dirs = set(cfg.get("exclude_dirs", DEFAULT_EXCLUDE_DIRS))
        include_patterns = cfg.get("include_patterns", args.include)
        exclude_patterns = cfg.get("exclude_patterns", args.exclude)
        max_file_size = cfg.get("max_file_size", args.max_size)
        output_file = cfg.get("output_file", args.output)
        encoding = cfg.get("encoding", args.encoding)
        add_summary = cfg.get("add_summary", not args.no_summary)
    else:
        extensions = args.ext
        exclude_dirs = set(args.exclude_dir) if args.exclude_dir else None
        include_patterns = args.include
        exclude_patterns = args.exclude
        max_file_size = args.max_size
        output_file = args.output
        encoding = args.encoding
        add_summary = not args.no_summary

    result = merge_documents(
        root_dir=args.directory,
        output_file=output_file,
        extensions=extensions,
        exclude_dirs=exclude_dirs,
        include_patterns=include_patterns,
        exclude_patterns=exclude_patterns,
        max_file_size=max_file_size,
        encoding=encoding,
        add_summary=add_summary,
        prompt=args.prompt,
        prompt_file=args.prompt_file,
    )
    print(result)


if __name__ == "__main__":
    main()
