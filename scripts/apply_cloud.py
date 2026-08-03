"""
apply_cloudai.py — применение ответа облачного ИИ (docs/AI_TASK_Tools_CloudAI_Responce.md).

Парсер:
- ищет строки-заголовки секций вида «^<путь>/<файл>.py$» (по одному на строку);
- код файла — строки до следующей секции/«### SUMMARY»;
- НЕ включает: пустые строки в начале/конце, строки из одних цифр (номера строк
  UI чата), строку «python» (метка языка), «// END OF FILE» (маркер полноты);
- маппинг UI-имён: tools/main.py -> tools/__main__.py, tools/init.py -> tools/__init__.py
  (секции, где ИИ потерял двойное подчёркивание).
- пишет файлы в кодировке utf-8.

Файлы без маркера «// END OF FILE» помечаются как НЕПОЛНЫЕ и пропускаются
(позволяет тут же увидеть, что дозапрашивать у чата).
"""
import os
import re
import sys

# скрипт живёт в scripts/, поэтому корень проекта — на уровень выше
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RESP = os.path.join(ROOT, "docs", "AI_TASK_Tools_CloudAI_Responce.md")

NAME_FIX = {
    "tools/main.py": "tools/__main__.py",
    "tools/init.py": "tools/__init__.py",
    "agents/main.py": "agents/__main__.py",
    "agents/init.py": "agents/__init__.py",
}

HEADER_RE = re.compile(r"^(?:[A-Za-z0-9_./-]+\.py|\.\.[/\\].*?\.py)$")


def clean_code(lines):
    """Убирает мусор UI из блока кода, оставляет чистый Python."""
    out = []
    for ln in lines:
        s = ln.rstrip()
        if not s.strip():
            continue
        if s.strip().isdigit():  # номера строк из UI чата
            continue
        if s.strip() == "python" or s.strip().startswith("```"):
            continue
        if s.strip() == "// END OF FILE":
            continue
        out.append(s)
    return out


def parse(response_path: str):
    with open(response_path, "r", encoding="utf-8") as f:
        lines = f.read().splitlines()

    files = {}  # имя -> (код, full_ok)
    cur = None
    buf = []
    for ln in lines:
        s = ln.strip()
        if HEADER_RE.match(s) and not s.startswith("//"):
            # новая секция файла
            if cur is not None:
                files[cur] = buf
            cur = s
            buf = []
            continue
        if cur is not None:
            buf.append(ln)
    if cur is not None:
        files[cur] = buf

    results = []
    for raw_name, raw_lines in files.items():
        name = NAME_FIX.get(raw_name, raw_name)
        code = clean_code(raw_lines)
        full_ok = any(ln.rstrip() == "// END OF FILE" for ln in raw_lines)
        results.append({
            "name": name,
            "raw_name": raw_name,
            "code": "\n".join(code) + "\n",
            "full_ok": full_ok,
        })
    return results


def apply(results, dry_run=True):
    written, skipped = [], []
    for r in results:
        if not r["full_ok"]:
            skipped.append((r["raw_name"], "END OF FILE not found"))
            continue
        path = os.path.join(ROOT, r["name"])
        parent = os.path.dirname(path)
        if parent:
            os.makedirs(parent, exist_ok=True)
        if dry_run:
            written.append((r["name"], len(r["code"])))
        else:
            with open(path, "w", encoding="utf-8") as f:
                f.write(r["code"])
            written.append((r["name"], len(r["code"])))
    return written, skipped


if __name__ == "__main__":
    dry = "--write" not in sys.argv
    results = parse(RESP)
    print(f"Секций файлов найдено: {len(results)}\n")
    for r in results:
        print(f"[{'OK ' if r['full_ok'] else 'CUT'} ] {r['name']:45s} "
              f"{sum(len(l)+1 for l in r['code'].splitlines()):6d} cимволов")
    written, skipped = apply(results, dry_run=dry)
    print(f"\n{'ПРЕДПРОСМОТР (dry)' if dry else 'ЗАПИСАНО'}: {len(written)} файлов")
    for name, size in written:
        print(f"  + {name} ({size} символов)")
    if skipped:
        print(f"\nНЕПОЛНЫЕ (пропущены, нужен дозапрос в чат): {len(skipped)}")
        for name, why in skipped:
            print(f"  ! {name}: {why}")