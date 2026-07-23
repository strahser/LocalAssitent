import subprocess
import sys
import tempfile
import os


def execute_code(code: str, timeout: int = 30) -> str:
    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False, encoding="utf-8") as f:
        f.write(code)
        tmpfile = f.name

    try:
        result = subprocess.run(
            [sys.executable, tmpfile],
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        output = ""
        if result.stdout:
            output += result.stdout
        if result.stderr:
            output += f"\n--- STDERR ---\n{result.stderr}"
        if result.returncode != 0 and not output:
            output = f"Exit code: {result.returncode}"
        return output if output else "(no output)"
    except subprocess.TimeoutExpired:
        return f"ERROR: Execution timed out after {timeout}s"
    except Exception as e:
        return f"ERROR: {e}"
    finally:
        try:
            os.unlink(tmpfile)
        except:
            pass


def main():
    if len(sys.argv) > 1:
        code = sys.argv[1]
    else:
        code = sys.stdin.read()
    timeout = int(sys.argv[2]) if len(sys.argv) > 2 else 30
    print(execute_code(code, timeout))


if __name__ == "__main__":
    main()
