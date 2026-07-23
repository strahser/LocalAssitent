import os
import sys


def read_file(path: str, offset: int = 0, limit: int = 2000) -> str:
    abs_path = os.path.abspath(path)
    if not os.path.exists(abs_path):
        return f"ERROR: File not found: {path}"
    if not os.path.isfile(abs_path):
        return f"ERROR: Not a file: {path}"

    try:
        with open(abs_path, "r", encoding="utf-8", errors="replace") as f:
            lines = f.readlines()
    except Exception as e:
        return f"ERROR: Cannot read file: {e}"

    total = len(lines)
    if offset < 0:
        offset = 0
    if limit <= 0:
        limit = total

    selected = lines[offset:offset + limit]
    content = "".join(selected)
    header = f"--- {path} (lines {offset+1}-{min(offset+limit, total)} of {total}) ---\n"
    return header + content.rstrip("\n")


def main():
    if len(sys.argv) < 2:
        print("Usage: read_file <path> [offset] [limit]")
        sys.exit(1)

    path = sys.argv[1]
    offset = int(sys.argv[2]) if len(sys.argv) > 2 else 0
    limit = int(sys.argv[3]) if len(sys.argv) > 3 else 2000
    print(read_file(path, offset, limit))


if __name__ == "__main__":
    main()
