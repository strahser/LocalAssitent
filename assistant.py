# assistant.py – оркестратор

import sys
import argparse
import config
from DeepSeekClient import DeepSeekClient
from Logger import Logger
from extractors import ExtractorFactory
from rules import RuleProcessor


# ------------------- Оркестратор -------------------
class Orchestrator:
    def __init__(self, logger):
        self.logger = logger
        self.extractor = ExtractorFactory.get_extractor("regex")
        self.rule_processor = RuleProcessor(timeout=config.TIMEOUT_SCRIPT)
        self.client = DeepSeekClient(logger, timeout=config.TIMEOUT_DEEPSEEK)
        self.max_retries = config.MAX_RETRIES

    def run(self, chat_mode=False):
        full_prompt = config.BASE_PROMPT
        self.logger.log(f"🚀 Запуск ассистента")
        self.logger.log(f"📝 Запрос: {full_prompt}")
        self.logger.log(f"💬 Интерактивный режим: {'включён' if chat_mode else 'выключен'}")

        current_prompt = full_prompt
        for attempt in range(1, self.max_retries + 1):
            self.logger.log(f"Попытка {attempt}/{self.max_retries}")

            # Получить ответ
            full_text = self.client.send_prompt(current_prompt)
            if full_text is None:
                if attempt < self.max_retries:
                    continue
                else:
                    self.logger.log("❌ Не удалось получить ответ после всех попыток", "ERROR")
                    return False

            self.logger.log_response(full_text)
            # Извлечь код
            code = self.extractor.extract(full_text)
            if not code:
                self.logger.log("❌ Не удалось извлечь код из ответа", "ERROR")
                if attempt < self.max_retries:
                    self.logger.log("🔄 Повторная попытка...")
                    continue
                else:
                    self.logger.log("❌ Исчерпаны все попытки извлечения кода", "ERROR")
                    return False

            self.logger.log("✅ Код извлечён")
            self.logger.log(f"📄 Код (первые 200 символов):\n{code[:200]}...")
            self.logger.log_response(full_text, code)

            # Проверка синтаксиса
            ok, err = self.rule_processor.check_syntax(code)
            if not ok:
                self.logger.log(f"⚠️ Синтаксическая ошибка: {err}", "WARNING")
                if self._is_truncation_error(err) and attempt < self.max_retries:
                    self.logger.log("🔄 Ошибка похожа на обрезание, повторяем запрос...")
                    continue
                elif chat_mode and config.AUTO_SEND_RESULTS and attempt < self.max_retries:
                    self.logger.log("🔄 Отправляем синтаксическую ошибку в ИИ для исправления...")
                    current_prompt = config.BASE_PROMPT + "Запрос: Исправь синтаксическую ошибку в коде:\n```\n" + err + "\n```\nВерни только исправленный код."
                    continue
                else:
                    self.logger.log("❌ Синтаксическая ошибка, автоматическое исправление отключено", "ERROR")
                    return False

            # Выполнение
            stdout, stderr, returncode = self.rule_processor.execute(code)
            if returncode == 0:
                self.logger.log("✅ Код выполнен успешно", "SUCCESS")
                if stdout:
                    self.logger.log("📄 Результат:")
                    print(stdout)  # выводим результат напрямую
                if stderr:
                    self.logger.log("⚠️ Предупреждения:", "WARNING")
                    print(stderr)
                # Если включён чат, можно отправить результат в ИИ для доп. предложений
                if chat_mode and config.AUTO_SEND_RESULTS:
                    result_prompt = f"Мой код выполнился успешно. Вывод:\n```\n{stdout}\n```\n\nЧто дальше?"
                    self.logger.log("📤 Отправка успешного результата в чат...")
                    self.client.send_prompt(config.BASE_PROMPT + "Запрос: " + result_prompt)
                self.logger.log("🏁 Ассистент завершил работу", "SUCCESS")
                return True
            else:
                error_text = stderr if stderr else stdout
                self.logger.log(f"❌ Код завершился с ошибкой (код {returncode})", "ERROR")
                if error_text:
                    self.logger.log(f"Ошибка: {error_text[:500]}", "ERROR")
                else:
                    error_text = "Unknown error"
                if chat_mode and config.AUTO_SEND_RESULTS and attempt < self.max_retries:
                    self.logger.log("🔄 Отправляем ошибку в ИИ для исправления...")
                    current_prompt = config.BASE_PROMPT + "Запрос: Исправь ошибку в коде:\n```\n" + error_text + "\n```\nВерни только исправленный код."
                    continue
                else:
                    self.logger.log("❌ Исправление ошибок не предусмотрено или попытки исчерпаны", "ERROR")
                    return False

        self.logger.log("❌ Исчерпаны все попытки", "ERROR")
        return False

    @staticmethod
    def _is_truncation_error(error_msg):
        patterns = [
            "unexpected eof while parsing",
            "unterminated string literal",
            "unterminated triple-quoted string literal",
            "(' was never closed",
            "( was never closed",
            "'{' was never closed",
            "{ was never closed",
            "'[' was never closed",
            "[ was never closed",
            "expected one or more names after 'import'",
            "unexpected indent",
            "unexpected dedent",
            "invalid syntax",
        ]
        return any(p in error_msg.lower() for p in patterns)

# ------------------- Точка входа -------------------
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--chat', action='store_true', help='Включить интерактивный режим')
    parser.add_argument('--log-html', action='store_true', help='Включить логирование в HTML')
    parser.add_argument('--log-file', action='store_true', help='Включить логирование в файл')
    parser.add_argument('--save-responses', action='store_true', help='Сохранять ответы в файлы')
    parser.add_argument('prompt', nargs='*', default=None, help='Запрос (если не указан, берётся из config)')
    args = parser.parse_args()

    # Определяем параметры логирования: из аргументов или из config
    log_html = args.log_html or config.LOG_TO_HTML
    log_file = args.log_file or config.LOG_TO_FILE
    save_resp = args.save_responses or config.SAVE_RESPONSES

    logger = Logger(log_to_html=log_html, log_to_file=log_file, save_responses=save_resp)

    chat_mode = args.chat or config.CHAT_MODE
    if args.prompt is not None:
        user_prompt = ' '.join(args.prompt)
    else:
        user_prompt = config.USER_PROMPT

    orchestrator = Orchestrator(logger)
    success = orchestrator.run(chat_mode=chat_mode)
    logger.close()
    sys.exit(0 if success else 1)

if __name__ == "__main__":
    main()