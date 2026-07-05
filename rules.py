# rules.py
import subprocess
import os
import tempfile


class RuleProcessor:
    """Обработчик правил: проверка синтаксиса, выполнение, анализ ошибок."""

    def __init__(self, timeout=60):
        self.timeout = timeout

    def check_syntax(self, code: str) -> tuple[bool, str]:
        """Проверяет синтаксис Python-кода."""
        try:
            compile(code, '<string>', 'exec')
            return True, ""
        except SyntaxError as e:
            return False, str(e)

    def execute(self, code: str) -> tuple[str, str, int]:
        """Выполняет код и возвращает stdout, stderr, returncode."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False, encoding='utf-8', newline='\n') as f:
            f.write(code)
            script_path = f.name
        try:
            result = subprocess.run(
                ['python', script_path],
                capture_output=True,
                text=True,
                encoding='utf-8',
                errors='replace',
                timeout=self.timeout
            )
            stdout, stderr, returncode = result.stdout.strip(), result.stderr.strip(), result.returncode
        except subprocess.TimeoutExpired:
            stdout, stderr, returncode = "", "Timeout", -1
        finally:
            os.unlink(script_path)
        return stdout, stderr, returncode

    def analyze_errors(self, stderr: str) -> str:
        """Извлекает ключевую информацию из stderr для отправки в исправление."""
        lines = stderr.splitlines()
        error_lines = [line for line in lines if "Error" in line or "Traceback" in line]
        if error_lines:
            return '\n'.join(error_lines[-3:])
        return stderr[-500:]