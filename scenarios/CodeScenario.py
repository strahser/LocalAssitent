from typing import Optional, Callable

from config import config  # для доступа к ScenarioConfig
from core.response_processor import ResponseProcessor
from scenarios.ScenarioBase import ScenarioBase


class CodeScenario(ScenarioBase):
    def __init__(self, client, logger, config: config.ScenarioConfig):
        super().__init__(client, logger, config)
        self.processor = ResponseProcessor(
            extractor_type=config.extractor_type or "regex",
            script_timeout=config.timeout_script
        )

    def run(self, progress_callback: Optional[Callable[[int, int], None]] = None) -> bool:
        self.logger.info("🚀 Запуск сценария: Code")
        current_prompt = self.config.prompt_template
        for attempt in range(1, self.config.max_retries + 1):
            self.logger.info(f"🔄 Попытка {attempt}/{self.config.max_retries}")
            full_text = self.client.send_message(current_prompt)
            if full_text is None:
                if attempt < self.config.max_retries:
                    continue
                else:
                    self.logger.error("❌ Не удалось получить ответ")
                    return False

            self.logger.log_response(full_text)
            code = self.processor.extract_code(full_text)
            if code is None:
                if attempt < self.config.max_retries:
                    continue
                else:
                    return False

            self.logger.success("✅ Код извлечён")
            ok, err = self.processor.validate_syntax(code)
            if not ok:
                self.logger.warning(f"⚠️ Синтаксическая ошибка: {err}")
                if self.processor.is_truncation_error(err) and attempt < self.config.max_retries:
                    self.logger.info("🔄 Ошибка похожа на обрезание, повторяем запрос...")
                    continue
                elif self.config.auto_send_results and attempt < self.config.max_retries:
                    self.logger.info("🔄 Отправляем синтаксическую ошибку в ИИ для исправления...")
                    current_prompt = self.config.prompt_template + " Запрос: Исправь синтаксическую ошибку в коде:\n```\n" + err + "\n```\nВерни только исправленный код."
                    continue
                else:
                    self.logger.error("❌ Синтаксическая ошибка, автоматическое исправление отключено")
                    return False

            stdout, stderr, returncode = self.processor.execute_code(code)
            if returncode == 0:
                self.logger.success("✅ Код выполнен успешно")
                if stdout:
                    self.logger.info("📄 Результат:")
                    print(stdout)
                if stderr:
                    self.logger.warning("⚠️ Предупреждения:")
                    print(stderr)
                if self.config.auto_send_results:
                    result_prompt = f"Мой код выполнился успешно. Вывод:\n```\n{stdout}\n```\n\nЧто дальше?"
                    self.logger.info("📤 Отправка успешного результата в чат...")
                    self.client.send_message(self.config.prompt_template + " Запрос: " + result_prompt)
                self.logger.success("🏁 Сценарий завершён")
                return True
            else:
                error_text = stderr if stderr else stdout
                self.logger.error(f"❌ Код завершился с ошибкой (код {returncode})")
                if error_text:
                    self.logger.error(f"Ошибка: {error_text[:500]}")
                else:
                    error_text = "Unknown error"
                if self.config.auto_send_results and attempt < self.config.max_retries:
                    self.logger.info("🔄 Отправляем ошибку в ИИ для исправления...")
                    current_prompt = self.config.prompt_template + " Запрос: Исправь ошибку в коде:\n```\n" + error_text + "\n```\nВерни только исправленный код."
                    continue
                else:
                    self.logger.error("❌ Исправление ошибок не предусмотрено или попытки исчерпаны")
                    return False

        self.logger.error("❌ Исчерпаны все попытки")
        return False
