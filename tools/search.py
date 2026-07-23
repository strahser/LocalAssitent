import os
import re
import sys
from pathlib import Path


def grep_search(pattern: str, root: str = ".", include: str = "*.py", max_results: int = 30) -> str:
    root = os.path.abspath(root)
    if not os.path.isdir(root):
        return f"ERROR: Not a directory: {root}"

    results = []
    exclude_dirs = {"__pycache__", ".git", "venv", ".venv", "node_modules", "build", "dist", ".opencode"}

    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in exclude_dirs]
        for fn in filenames:
            if include and not fn.endswith(tuple(include.split(","))):
                continue
            fp = os.path.join(dirpath, fn)
            try:
                with open(fp, "r", encoding="utf-8", errors="replace") as f:
                    for i, line in enumerate(f, 1):
                        if re.search(pattern, line):
                            rel = os.path.relpath(fp, root)
                            results.append(f"{rel}:{i}: {line.rstrip()}")
                            if len(results) >= max_results:
                                break
            except:
                continue
            if len(results) >= max_results:
                break

    if not results:
        return f"No matches for: {pattern}"
    header = f"--- grep '{pattern}' ({len(results)} results) ---\n"
    return header + "\n".join(results)


def glob_search(pattern: str, root: str = ".") -> str:
    root = os.path.abspath(root)
    matches = list(Path(root).rglob(pattern))
    exclude = {"__pycache__", ".git"}
    matches = [m for m in matches if not any(excl in m.parts for excl in exclude)]

    if not matches:
        return f"No files matching: {pattern}"
    header = f"--- glob '{pattern}' ({len(matches)} files) ---\n"
    return header + "\n".join(str(m.relative_to(root)) for m in matches[:100])


def main():
    if len(sys.argv) < 3:
        print("Usage: search.py grep <pattern> [root] [include]")
        print("       search.py glob <pattern> [root]")
        sys.exit(1)

    mode = sys.argv[1]
    if mode == "grep":
        pattern = sys.argv[2]
        root = sys.argv[3] if len(sys.argv) > 3 else "."
        include = sys.argv[4] if len(sys.argv) > 4 else "*.py"
        print(grep_search(pattern, root, include))
    elif mode == "glob":
        pattern = sys.argv[2]
        root = sys.argv[3] if len(sys.argv) > 3 else "."
        print(glob_search(pattern, root))
    else:
        print(f"Unknown mode: {mode}")


if __name__ == "__main__":
    main()
