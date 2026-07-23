import os
import sys
from pathlib import Path


def list_dir(path: str = ".", max_depth: int = 2, show_hidden: bool = False) -> str:
    root = os.path.abspath(path)
    if not os.path.isdir(root):
        return f"ERROR: Not a directory: {path}"

    lines = []
    exclude = {"__pycache__", ".git", ".venv", "venv", "node_modules", "build", "dist"}

    def _walk(dirpath, depth):
        if depth > max_depth:
            return
        try:
            entries = sorted(Path(dirpath).iterdir(), key=lambda x: (not x.is_dir(), x.name.lower()))
        except PermissionError:
            return

        for entry in entries:
            if entry.name.startswith(".") and not show_hidden:
                continue
            if entry.name in exclude:
                continue
            indent = "  " * depth
            suffix = "/" if entry.is_dir() else ""
            lines.append(f"{indent}{entry.name}{suffix}")
            if entry.is_dir():
                _walk(str(entry), depth + 1)

    lines.append(f"./ {os.path.basename(root)}/")
    _walk(root, 1)
    return "\n".join(lines)


def main():
    path = sys.argv[1] if len(sys.argv) > 1 else "."
    max_depth = int(sys.argv[2]) if len(sys.argv) > 2 else 2
    show_hidden = "--all" in sys.argv
    print(list_dir(path, max_depth, show_hidden))


if __name__ == "__main__":
    main()
