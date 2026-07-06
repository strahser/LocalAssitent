# scenarios.py
import config
from extractors import ExtractorFactory
from rules import RuleProcessor
import time
from abc import ABC, abstractmethod

class Scenario(ABC):
    def __init__(self, logger):
        self.logger = logger
        self.client = None

    def set_client(self, client):
        self.client = client

    @abstractmethod
    def run(self):
        pass

    def _extract_content(self, full_text: str) -> str:
        """По умолчанию возвращает полный текст ответа."""
        return full_text


class CodeScenario(Scenario):
    def __init__(self, logger):
        super().__init__(logger)
        cfg = config.SCENARIO_CONFIGS["code"]
        self.prompt_template = cfg["prompt_template"]
        self.max_retries = cfg["max_retries"]
        self.auto_send_results = cfg["auto_send_results"]
        self.timeout_script = cfg["timeout_script"]
        self.extractor = ExtractorFactory.get_extractor(cfg["extractor_type"])
        self.rule_processor = RuleProcessor(timeout=self.timeout_script)

    def _extract_content(self, full_text: str) -> str:
        code = self.extractor.extract(full_text)
        if not code:
            self.logger.log("❌ Не удалось извлечь код", "ERROR")
            return None
        return code

    def run(self):
        self.logger.log("🚀 Запуск сценария: Code")
        current_prompt = self.prompt_template
        for attempt in range(1, self.max_retries + 1):
            self.logger.log(f"Попытка {attempt}/{self.max_retries}")
            full_text = self.client.send_prompt(current_prompt)
            if full_text is None:
                if attempt < self.max_retries:
                    continue
                else:
                    self.logger.log("❌ Не удалось получить ответ", "ERROR")
                    return False
            self.logger.log_response(full_text)
            code = self._extract_content(full_text)
            if code is None:
                if attempt < self.max_retries:
                    continue
                else:
                    return False
            self.logger.log("✅ Код извлечён")
            ok, err = self.rule_processor.check_syntax(code)
            if not ok:
                self.logger.log(f"⚠️ Синтаксическая ошибка: {err}", "WARNING")
                if self._is_truncation_error(err) and attempt < self.max_retries:
                    self.logger.log("🔄 Ошибка похожа на обрезание, повторяем запрос...")
                    continue
                elif self.auto_send_results and attempt < self.max_retries:
                    self.logger.log("🔄 Отправляем синтаксическую ошибку в ИИ для исправления...")
                    current_prompt = self.prompt_template + " Запрос: Исправь синтаксическую ошибку в коде:\n```\n" + err + "\n```\nВерни только исправленный код."
                    continue
                else:
                    self.logger.log("❌ Синтаксическая ошибка, автоматическое исправление отключено", "ERROR")
                    return False
            stdout, stderr, returncode = self.rule_processor.execute(code)
            if returncode == 0:
                self.logger.log("✅ Код выполнен успешно", "SUCCESS")
                if stdout:
                    self.logger.log("📄 Результат:")
                    print(stdout)
                if stderr:
                    self.logger.log("⚠️ Предупреждения:", "WARNING")
                    print(stderr)
                if self.auto_send_results:
                    result_prompt = f"Мой код выполнился успешно. Вывод:\n```\n{stdout}\n```\n\nЧто дальше?"
                    self.logger.log("📤 Отправка успешного результата в чат...")
                    self.client.send_prompt(self.prompt_template + " Запрос: " + result_prompt)
                self.logger.log("🏁 Сценарий завершён", "SUCCESS")
                return True
            else:
                error_text = stderr if stderr else stdout
                self.logger.log(f"❌ Код завершился с ошибкой (код {returncode})", "ERROR")
                if error_text:
                    self.logger.log(f"Ошибка: {error_text[:500]}", "ERROR")
                else:
                    error_text = "Unknown error"
                if self.auto_send_results and attempt < self.max_retries:
                    self.logger.log("🔄 Отправляем ошибку в ИИ для исправления...")
                    current_prompt = self.prompt_template + " Запрос: Исправь ошибку в коде:\n```\n" + error_text + "\n```\nВерни только исправленный код."
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


class TextScenario(Scenario):
    def __init__(self, logger):
        super().__init__(logger)
        cfg = config.SCENARIO_CONFIGS["text"]
        self.prompt_template = cfg["prompt_template"]
        self.input_file = cfg["input_file"]
        self.output_file = cfg["output_file"]
        self.max_retries = cfg["max_retries"]
        self.create_new_chat = cfg.get("create_new_chat", False)
        self.delay = cfg.get("delay_between_questions", 1)

    def run(self):
        self.logger.log("🚀 Запуск сценария: Text")
        try:
            with open(self.input_file, 'r', encoding='utf-8') as f:
                questions = [line.strip() for line in f if line.strip()]
        except FileNotFoundError:
            self.logger.log(f"❌ Файл {self.input_file} не найден", "ERROR")
            return False
        if not questions:
            self.logger.log("❌ Файл с вопросами пуст", "ERROR")
            return False

        self.logger.log(f"📖 Найдено {len(questions)} вопросов")

        # Очищаем выходной файл перед началом
        with open(self.output_file, 'w', encoding='utf-8') as f:
            f.write("")  # создаём/очищаем

        for idx, q in enumerate(questions, 1):
            self.logger.log(f"📝 Вопрос {idx}/{len(questions)}: {q[:50]}...")

            if self.create_new_chat:
                self.logger.log("🔄 Создание нового чата...")
                self.client.new_chat()
                time.sleep(1)

            prompt = f"{self.prompt_template}\n\n{q}"
            response = self.client.send_prompt(prompt)

            # Формируем блок для записи
            if response is None:
                self.logger.log(f"❌ Не удалось получить ответ на вопрос {idx}", "ERROR")
                block = f"## Вопрос {idx}: {q}\n\n### Ответ\n\n*Ошибка получения ответа*\n\n---\n"
            else:
                self.logger.log(f"✅ Ответ на вопрос {idx} получен ({len(response)} символов)")
                block = f"## Вопрос {idx}: {q}\n\n### Ответ\n\n{response}\n\n---\n"

            # Немедленная запись в файл (добавление в конец)
            with open(self.output_file, 'a', encoding='utf-8') as f:
                f.write(block)

            # Пауза между вопросами, если не последний
            if idx < len(questions) and self.delay > 0:
                self.logger.log(f"⏳ Пауза {self.delay} сек перед следующим вопросом...")
                time.sleep(self.delay)

        self.logger.log(f"✅ Все ответы сохранены в {self.output_file}", "SUCCESS")
        return True


class ScenarioFactory:
    @staticmethod
    def get_scenario(name, logger):
        if name == "code":
            return CodeScenario(logger)
        elif name == "text":
            return TextScenario(logger)
        else:
            raise ValueError(f"Неизвестный сценарий: {name}")