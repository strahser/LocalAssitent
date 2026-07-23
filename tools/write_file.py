import os
import sys


def write_file(path: str, content: str, force: bool = False) -> str:
    abs_path = os.path.abspath(path)
    if os.path.exists(abs_path) and not force:
        return f"WARNING: File already exists: {path}. Set force=True to overwrite."

    os.makedirs(os.path.dirname(abs_path) or ".", exist_ok=True)
    try:
        with open(abs_path, "w", encoding="utf-8") as f:
            f.write(content)
        return f"OK: Written {len(content)} bytes to {path}"
    except Exception as e:
        return f"ERROR: Cannot write file: {e}"


def main():
    if len(sys.argv) < 3:
        print("Usage: write_file <path> <content> [--force]")
        sys.exit(1)

    path = sys.argv[1]
    content = sys.argv[2]
    force = "--force" in sys.argv
    print(write_file(path, content, force))


if __name__ == "__main__":
    main()
