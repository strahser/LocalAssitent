import os
import subprocess
import sys

import config


# ------------------- Клиент DeepSeek -------------------
class DeepSeekClient:
    def __init__(self, logger, timeout=180):
        self.logger = logger
        self.timeout = timeout

    def send_prompt(self, prompt):
        self.logger.log("📤 Отправка запроса в DeepSeek...")
        cmd_args = [sys.executable, config.SEND_MESSAGE_SCRIPT]
        try:
            result = subprocess.run(
                cmd_args,
                input=prompt,
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
                self.logger.log("❌ Пустой ответ от DeepSeek", "ERROR")
                return None
            self.logger.log("✅ Текст ответа получен")
            self.logger.log(f"📄 Текст (первые 300 символов): {stdout[:300]}...")
            return stdout
        except subprocess.TimeoutExpired:
            self.logger.log("Таймаут ожидания ответа от DeepSeek", "ERROR")
            return None
        except Exception as e:
            self.logger.log(f"Ошибка вызова send_message: {e}", "ERROR")
            return None
