"""
collect_context.py – сбор контекста проекта (файлы из выбранных директорий) для передачи облачному ИИ.

Собирает содержимое файлов проекта (C# / Python, приоритет C#) в один TXT-файл
с добавлением в НАЧАЛО «общего задания» (описание задачи для облачного ИИ).
Временные файлы (bin, obj, .gigacode, *.plan.md, *AssemblyAttributes.cs, *.tmp,
*.log, *.user и др.) автоматически исключаются.

Использование:
    py tools/collect_context.py <директория> [опции]
    py tools/collect_context.py --dirs <дир1> <дир2> ... [опции]

Примеры:
    py tools/collect_context.py d:\\Projects\\HeatLossRevit2 --output context.txt
    py tools/collect_context.py --dirs C:\\ProjA C:\\ProjB --project-type cs --output cs_context.txt
    py tools/collect_context.py . --project-type py --no-task
"""
import os
import sys
import json
import argparse
import fnmatch
from pathlib import Path
from datetime import datetime
from typing import List, Set, Optional, Dict

try:
    from tools.merge_docs import format_file_block
except Exception:
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from merge_docs import format_file_block


PROJECT_ROOT = Path(__file__).resolve().parent.parent

DEFAULT_TEMP_EXCLUDE_DIRS = {
    "bin", "obj", ".git", ".gigacode", ".idea", ".vs", "__pycache__",
    "node_modules", "venv", ".venv", "build", "dist", "packages",
    "TestResults", "log", "logs", "publish", ".opencode", "temp",
}

TEMP_FILE_PATTERNS = [
    "*.tmp", "*.log", "*.user", "*.suo", "*.bak", "*.orig", "*.rej",
    "*.nupkg", "*.cache", "*.pyc", "*.plan.md", "*AssemblyAttributes.cs",
    "*.g.cs", "*.g.i.cs", "Thumbs.db", "*.DS_Store",
]

_CS_EXTS = [".cs", ".xaml", ".csproj", ".sln", ".config", ".xml", ".json"]
_PY_EXTS = [".py", ".txt", ".toml", ".cfg", ".ini", ".yaml", ".json"]
PROJECT_EXTENSIONS = {
    "cs": _CS_EXTS,
    "py": _PY_EXTS,
    "mixed": list(dict.fromkeys(_CS_EXTS + _PY_EXTS)),
    "unknown": list(dict.fromkeys(_CS_EXTS + _PY_EXTS)),
}

# Большие файлы (напр. ClimateDataRepository.cs, 340KB Revit-Репозиторий данных)
# по умолчанию НЕ передаются — они редко нужны облачному ИИ для анализа.
# Снизь/повысь через --max-size (для полного исходного кода — увеличь).
MAX_FILE_SIZE_DEFAULT = 100_000


def _prune(dirnames: List[str], exclude_dirs: Set[str]) -> None:
    """Отсекает временные поддиректории при os.walk."""
    dirnames[:] = [d for d in dirnames if d not in exclude_dirs]


def detect_project_types(dirs: List[str]) -> Dict[str, str]:
    """Определяет тип проекта для каждой директории: 'cs' | 'py' | 'mixed' | 'unknown'."""
    result = {}
    for d in dirs:
        root = Path(d).resolve()
        cs_count = 0
        py_count = 0
        for dirpath, dirnames, filenames in os.walk(root):
            _prune(dirnames, DEFAULT_TEMP_EXCLUDE_DIRS)
            for fn in filenames:
                fp = str(Path(dirpath) / fn)
                if fn.lower().endswith(".cs") and not is_temp_file(fp):
                    cs_count += 1
                elif fn.lower().endswith(".py") and not is_temp_file(fp):
                    py_count += 1
        if cs_count > 0 and py_count == 0:
            result[str(d)] = "cs"
        elif py_count > 0 and cs_count == 0:
            result[str(d)] = "py"
        elif cs_count > 0 and py_count > 0:
            result[str(d)] = "mixed"
        else:
            result[str(d)] = "unknown"
    return result


def get_extensions(project_type: str) -> List[str]:
    """Возвращает список расширений для типа проекта."""
    return PROJECT_EXTENSIONS.get(project_type, PROJECT_EXTENSIONS["unknown"])


def is_temp_file(rel_path) -> bool:
    """True, если имя (или путь) файла соответствует временному паттерну.

    Принимает str или Path; Path приводится к строке (у Path есть свой .replace)."""
    if isinstance(rel_path, os.PathLike):
        rel_path = os.fspath(rel_path)
    p = str(rel_path).replace("\\", "/")
    name = p.rsplit("/", 1)[-1]
    for pat in TEMP_FILE_PATTERNS:
        if fnmatch.fnmatch(name, pat) or fnmatch.fnmatch(p, pat):
            return True
    return False


def _collect_files_with_stats(
    root_dir,
    extensions: Optional[List[str]],
    exclude_dirs: Set[str],
    include_patterns: Optional[List[str]],
    exclude_patterns: Optional[List[str]],
    max_file_size: int,
) -> tuple:
    """Собирает файлы одной директории и возвращает (files, skipped_size, skipped_temp).

    Логика повторяет tools/merge_docs.collect_files, но дополнительно
    отсекает временные файлы по имени и считает пропуски для прозрачного отчёта.
    """
    root = Path(root_dir).resolve()
    kept = []
    skipped_size = 0
    skipped_temp = 0
    include_patterns = include_patterns or []
    exclude_patterns = exclude_patterns or []

    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in exclude_dirs]
        for filename in filenames:
            filepath = Path(dirpath) / filename
            rel_path = filepath.relative_to(root)
            rel_str = str(rel_path)

            ext = filepath.suffix.lower()
            if extensions and ext not in extensions:
                continue
            if include_patterns and not any(
                fnmatch.fnmatch(rel_str, p) for p in include_patterns
            ):
                continue
            if any(fnmatch.fnmatch(rel_str, p) for p in exclude_patterns):
                continue
            if is_temp_file(rel_path):
                skipped_temp += 1
                continue
            try:
                if filepath.stat().st_size > max_file_size:
                    skipped_size += 1
                    continue
            except OSError:
                continue
            kept.append(filepath)

    kept.sort(key=lambda f: (f.suffix, str(f.relative_to(root))))
    return kept, skipped_size, skipped_temp


def build_general_task(task_file: str) -> str:
    """Читает файл общего задания и оборачивает его разделителями (для вставки в начало)."""
    tf = Path(task_file)
    if not tf.exists():
        return ""
    try:
        content = tf.read_text(encoding="utf-8")
    except Exception:
        return ""
    sep = "=" * 72
    return (
        "\n" + sep + "\n"
        "# ОБЩЕЕ ЗАДАНИЕ ДЛЯ ОБЛАЧНОГО ИИ\n" + sep + "\n\n"
        + content + "\n\n"
    )


def collect_context(
    dirs,
    output_file: str = "cloud_context.txt",
    project_types: Optional[Dict[str, str]] = None,
    extensions: Optional[List[str]] = None,
    exclude_dirs: Optional[Set[str]] = None,
    max_file_size: int = MAX_FILE_SIZE_DEFAULT,
    encoding: str = "utf-8",
    add_task: bool = True,
    task_file: Optional[str] = None,
    local_prompt: Optional[str] = None,
    add_summary: bool = True,
    include_patterns: Optional[List[str]] = None,
    exclude_patterns: Optional[List[str]] = None,
) -> str:
    """Собирает файлы из директорий и отдельных файлов, добавляет задание, пишет один TXT.

    dirs: список путей — каждая запись может быть директорией или отдельным файлом.
    Файлы включаются как есть (с проверкой размера и «временности», без фильтра по
    расширению) — удобно когда пользователь явно перечислил конкретные файлы.
    """
    raw = [Path(d).resolve() for d in dirs if d]
    if not raw:
        return "Не указаны директории/файлы."

    dir_roots = [r for r in raw if r.is_dir()]
    file_roots = [r for r in raw if r.is_file()]
    not_found = [r for r in raw if not r.exists()]

    if not dir_roots and not file_roots:
        return "Не найдено ни директорий, ни файлов: " + "; ".join(str(r) for r in raw)

    if project_types is None:
        project_types = detect_project_types([str(r) for r in dir_roots])

    eff_exclude = set(DEFAULT_TEMP_EXCLUDE_DIRS) | (set(exclude_dirs) if exclude_dirs else set())

    collected = []  # [(root, files, skipped_size, skipped_temp)]
    total_skipped_size = 0
    total_skipped_temp = 0

    for root in dir_roots:
        pt = project_types.get(str(root), "unknown")
        ext = extensions if extensions else get_extensions(pt)
        files, skipped_size, skipped_temp = _collect_files_with_stats(
            str(root), ext, eff_exclude,
            include_patterns, exclude_patterns, max_file_size,
        )
        collected.append((root, files, skipped_size, skipped_temp))
        total_skipped_size += skipped_size
        total_skipped_temp += skipped_temp

    for r in file_roots:
        if is_temp_file(r):
            total_skipped_temp += 1
            continue
        try:
            if r.stat().st_size > max_file_size:
                total_skipped_size += 1
                continue
        except OSError:
            continue
        # root = родительская директория: format_file_block покажет "FILE: <имя>"
        collected.append((r.parent, [r], 0, 0))

    total_files = sum(len(files) for _, files, _, _ in collected)

    parts = []

    # «Локальный промпт пользователя» — самое начало (если задан): конкретная задача,
    # которую ИИ должен выполнить поверх общего TDL-задания.
    if local_prompt and str(local_prompt).strip():
        sep = "=" * 72
        parts.append(
            "\n" + sep + "\n"
            "# ЛОКАЛЬНЫЙ ПРОМПТ ПОЛЬЗОВАТЕЛЯ (ЗАДАЧА)\n" + sep + "\n\n"
            + str(local_prompt).strip() + "\n\n"
        )

    # «Общее задание» — в НАЧАЛО выходного файла
    if add_task:
        tfile = task_file or str(PROJECT_ROOT / "prompts" / "general_task.txt")
        task_text = build_general_task(tfile)
        if task_text:
            parts.append(task_text)

    if add_summary:
        ext_stats = {}
        total_lines = 0
        for _, files, _, _ in collected:
            for f in files:
                ext = f.suffix.lower()
                try:
                    lines = len(f.read_text(encoding=encoding, errors="replace").splitlines())
                except Exception:
                    lines = 0
                ext_stats[ext] = ext_stats.get(ext, 0) + 1
                total_lines += lines
        roots_line = "; ".join(str(r) for r in (dir_roots + file_roots + not_found))
        types_line = "; ".join(f"{r}={project_types.get(str(r), '?') if r.is_dir() else 'file'}"
                               for r in (dir_roots + file_roots))
        summary = (
            f"{'#' * 72}\n"
            f"# CLOUD PROJECT CONTEXT\n"
            f"# Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
            f"# Project roots: {roots_line}\n"
            f"# Project types: {types_line}\n"
            f"# Total files: {total_files}\n"
            f"# Total lines: {total_lines}\n"
            f"# Extensions: {ext_stats}\n"
            f"{'#' * 72}\n\n"
        )
        parts.append(summary)

    multi = len(collected) > 1
    for root, files, _, _ in collected:
        if multi:
            parts.append(f"\n{'#' * 72}\n# DIR: {root}\n{'#' * 72}\n\n")
        for f in files:
            parts.append(format_file_block(f, root, encoding))

    output_path = Path(output_file)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("".join(parts), encoding=encoding)

    types_line = "; ".join(f"{r}={project_types.get(str(r), '?') if r.is_dir() else 'file'}"
                           for r in (dir_roots + file_roots))
    return (
        f"Готово: {total_files} файлов → {output_file}\n"
        f"Размер: {output_path.stat().st_size:,} байт\n"
        f"Типы корней: {types_line}\n"
        + (f"Пропущено (не найдено): {not_found}\n" if not_found else "")
        + f"Исключено временных файлов (по имени): {total_skipped_temp}; "
        f"по размеру (> {max_file_size:,} байт): {total_skipped_size}"
    )


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

    parser = argparse.ArgumentParser(
        description="Сбор контекста проекта (C#/Python) в один TXT с общим заданием для облачного ИИ",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Примеры:
  py tools/collect_context.py d:\\Projects\\HeatLossRevit2 --output context.txt
  py tools/collect_context.py --dirs C:\\ProjA C:\\ProjB --project-type cs
  py tools/collect_context.py . --project-type py --no-task
        """,
    )
    parser.add_argument("directory", nargs="?", default=None,
                        help="Корневая директория проекта (или используйте --dirs)")
    parser.add_argument("--dirs", nargs="+", default=None,
                        help="Несколько корневых директорий")
    parser.add_argument("--project-type", choices=["auto", "cs", "py"], default="auto",
                        help="Тип проекта (auto = определить по содержимому; по умолчанию auto)")
    parser.add_argument("--ext", nargs="+", default=None,
                        help="Расширения файлов (переопределяет автодетект)")
    parser.add_argument("--output", "-o", default="cloud_context.txt",
                        help="Выходной TXT-файл (по умолчанию: cloud_context.txt)")
    parser.add_argument("--max-size", type=int, default=MAX_FILE_SIZE_DEFAULT,
                        help=f"Макс. размер файла в байтах (по умолчанию: {MAX_FILE_SIZE_DEFAULT})")
    parser.add_argument("--include", nargs="*", default=None, help="Glob-паттерны включения")
    parser.add_argument("--exclude", nargs="*", default=None, help="Glob-паттерны исключения")
    parser.add_argument("--exclude-dir", nargs="*", default=None, help="Директории исключения")
    parser.add_argument("--no-task", action="store_true",
                        help="Не добавлять общее задание в начало")
    parser.add_argument("--task", default=None, help="Путь к файлу общего задания")
    parser.add_argument("--no-summary", action="store_true", help="Не добавлять сводку")
    parser.add_argument("--encoding", default="utf-8", help="Кодировка (по умолчанию utf-8)")
    parser.add_argument("--config", default=None, help="JSON-конфигурационный файл")

    args = parser.parse_args()

    cfg = {}
    if args.config:
        with open(args.config, "r", encoding="utf-8") as f:
            cfg = json.load(f)

    dirs = args.dirs if args.dirs else ([args.directory] if args.directory else None)
    if not dirs:
        parser.error("укажите директорию (позиционный аргумент) или --dirs")

    # Расширения
    extensions = args.ext or cfg.get("extensions")
    project_types = None
    if args.project_type != "auto":
        if extensions is None:
            extensions = get_extensions(args.project_type)
        project_types = {str(Path(d).resolve()): args.project_type for d in dirs}

    # Исключаемые директории (объединение CLI + config)
    exclude_dirs = set()
    if args.exclude_dir:
        exclude_dirs.update(args.exclude_dir)
    if cfg.get("exclude_dirs"):
        exclude_dirs.update(cfg["exclude_dirs"])

    # Прочие опции: CLI имеет приоритет над config
    max_size = args.max_size if args.max_size != MAX_FILE_SIZE_DEFAULT else cfg.get("max_file_size", MAX_FILE_SIZE_DEFAULT)
    output = args.output if args.output != "cloud_context.txt" else cfg.get("output_file", args.output)
    encoding = args.encoding if args.encoding != "utf-8" else cfg.get("encoding", args.encoding)
    add_task = (not args.no_task) and bool(cfg.get("add_task", True))
    add_summary = (not args.no_summary) and bool(cfg.get("add_summary", True))

    result = collect_context(
        dirs,
        output_file=output,
        project_types=project_types,
        extensions=extensions,
        exclude_dirs=exclude_dirs,
        max_file_size=max_size,
        encoding=encoding,
        add_task=add_task,
        task_file=args.task,
        add_summary=add_summary,
        include_patterns=args.include,
        exclude_patterns=args.exclude,
    )
    print(result)


if __name__ == "__main__":
    main()