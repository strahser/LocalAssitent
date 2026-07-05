import subprocess
import sys
import config

class DeepSeekClient:
    def __init__(self, logger, timeout=180):
        self.logger = logger
        self.timeout = timeout

    def _run_script(self, args, input_text=None):
        cmd_args = [sys.executable, config.SEND_MESSAGE_SCRIPT] + args
        try:
            result = subprocess.run(
                cmd_args,
                input=input_text,
                capture_output=True,
                text=True,
                encoding='utf-8',
                errors='replace',
                timeout=self.timeout
            )
            stdout, stderr, code = result.stdout.strip(), result.stderr.strip(), result.returncode
            if code != 0:
                self.logger.log(f"❌ Ошибка при вызове {config.SEND_MESSAGE_SCRIPT}: {stderr}", "ERROR")
                return None
            if not stdout:
                self.logger.log("❌ Пустой ответ от скрипта", "ERROR")
                return None
            return stdout
        except subprocess.TimeoutExpired:
            self.logger.log("Таймаут выполнения скрипта", "ERROR")
            return None
        except Exception as e:
            self.logger.log(f"Ошибка вызова {config.SEND_MESSAGE_SCRIPT}: {e}", "ERROR")
            return None

    def send_prompt(self, prompt):
        self.logger.log("📤 Отправка запроса в DeepSeek...")
        return self._run_script([], input_text=prompt)

    def new_chat(self):
        self.logger.log("🔄 Создание нового чата...")
        return self._run_script(["--new-chat"])

    def copy_response(self):
        self.logger.log("📋 Копирование последнего ответа...")
        return self._run_script(["--copy"])