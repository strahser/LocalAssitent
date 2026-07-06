# scenarios/scenarios.py
from config import config
from scenarios.extractors import ExtractorFactory
from scenarios.rules import RuleProcessor
import time
from abc import ABC, abstractmethod
from tqdm import tqdm

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
        return full_text

class CodeScenario(Scenario):
    def __init__(self, logger):
        super().__init__(logger)
        cfg = config.SCENARIO_CONFIGS["code"]  # теперь это ScenarioConfig
        self.prompt_template = cfg.prompt_template
        self.max_retries = cfg.max_retries
        self.auto_send_results = cfg.auto_send_results
        self.timeout_script = cfg.timeout_script
        self.extractor = ExtractorFactory.get_extractor(cfg.extractor_type)
        self.rule_processor = RuleProcessor(timeout=self.timeout_script)

    def _extract_content(self, full_text: str) -> str:
        code = self.extractor.extract(full_text)
        if not code:
            self.logger.error("❌ Не удалось извлечь код")
            return None
        return code

    def run(self):
        self.logger.info("🚀 Запуск сценария: Code")
        current_prompt = self.prompt_template
        for attempt in range(1, self.max_retries + 1):
            self.logger.info(f"🔄 Попытка {attempt}/{self.max_retries}")
            full_text = self.client.send_message(current_prompt)
            if full_text is None:
                if attempt < self.max_retries:
                    continue
                else:
                    self.logger.error("❌ Не удалось получить ответ")
                    return False
            self.logger.log_response(full_text)
            code = self._extract_content(full_text)
            if code is None:
                if attempt < self.max_retries:
                    continue
                else:
                    return False
            self.logger.success("✅ Код извлечён")
            ok, err = self.rule_processor.check_syntax(code)
            if not ok:
                self.logger.warning(f"⚠️ Синтаксическая ошибка: {err}")
                if self._is_truncation_error(err) and attempt < self.max_retries:
                    self.logger.info("🔄 Ошибка похожа на обрезание, повторяем запрос...")
                    continue
                elif self.auto_send_results and attempt < self.max_retries:
                    self.logger.info("🔄 Отправляем синтаксическую ошибку в ИИ для исправления...")
                    current_prompt = self.prompt_template + " Запрос: Исправь синтаксическую ошибку в коде:\n```\n" + err + "\n```\nВерни только исправленный код."
                    continue
                else:
                    self.logger.error("❌ Синтаксическая ошибка, автоматическое исправление отключено")
                    return False
            stdout, stderr, returncode = self.rule_processor.execute(code)
            if returncode == 0:
                self.logger.success("✅ Код выполнен успешно")
                if stdout:
                    self.logger.info("📄 Результат:")
                    print(stdout)
                if stderr:
                    self.logger.warning("⚠️ Предупреждения:")
                    print(stderr)
                if self.auto_send_results:
                    result_prompt = f"Мой код выполнился успешно. Вывод:\n```\n{stdout}\n```\n\nЧто дальше?"
                    self.logger.info("📤 Отправка успешного результата в чат...")
                    self.client.send_message(self.prompt_template + " Запрос: " + result_prompt)
                self.logger.success("🏁 Сценарий завершён")
                return True
            else:
                error_text = stderr if stderr else stdout
                self.logger.error(f"❌ Код завершился с ошибкой (код {returncode})")
                if error_text:
                    self.logger.error(f"Ошибка: {error_text[:500]}")
                else:
                    error_text = "Unknown error"
                if self.auto_send_results and attempt < self.max_retries:
                    self.logger.info("🔄 Отправляем ошибку в ИИ для исправления...")
                    current_prompt = self.prompt_template + " Запрос: Исправь ошибку в коде:\n```\n" + error_text + "\n```\nВерни только исправленный код."
                    continue
                else:
                    self.logger.error("❌ Исправление ошибок не предусмотрено или попытки исчерпаны")
                    return False
        self.logger.error("❌ Исчерпаны все попытки")
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
        cfg = config.SCENARIO_CONFIGS["text"]  # теперь это ScenarioConfig
        self.prompt_template = cfg.prompt_template
        self.input_file = cfg.input_file
        self.output_file = cfg.output_file
        self.max_retries = cfg.max_retries
        self.create_new_chat = cfg.create_new_chat
        self.delay = cfg.delay_between_questions

    def run(self):
        self.logger.info("🚀 Запуск сценария: Text")
        try:
            with open(self.input_file, 'r', encoding='utf-8') as f:
                questions = [line.strip() for line in f if line.strip()]
        except FileNotFoundError:
            self.logger.error(f"❌ Файл {self.input_file} не найден")
            return False
        if not questions:
            self.logger.error("❌ Файл с вопросами пуст")
            return False

        self.logger.info(f"📖 Найдено {len(questions)} вопросов")
        with open(self.output_file, 'w', encoding='utf-8') as f:
            f.write("")

        total_questions = len(questions)
        with tqdm(total=total_questions, desc="📊 Общий прогресс", unit="вопрос",
                  position=0, leave=True, colour='green', bar_format='{l_bar}{bar}| {n_fmt}/{total_fmt}') as pbar:
            for idx, q in enumerate(questions, 1):
                self.logger.info(f"📝 Вопрос {idx}/{total_questions}: {q[:50]}...")

                if self.create_new_chat:
                    self.logger.info("🔄 Создание нового чата...")
                    self.client.new_chat()
                    time.sleep(1)

                prompt = f"{self.prompt_template}\n\n{q}"
                response = self.client.send_message(prompt)

                if response is None:
                    self.logger.error(f"❌ Не удалось получить ответ на вопрос {idx}")
                    block = f"## Вопрос {idx}: {q}\n\n### Ответ\n\n*Ошибка получения ответа*\n\n---\n"
                else:
                    self.logger.info(f"✅ Ответ на вопрос {idx} получен ({len(response)} символов)")
                    block = f"## Вопрос {idx}: {q}\n\n### Ответ\n\n{response}\n\n---\n"

                with open(self.output_file, 'a', encoding='utf-8') as f:
                    f.write(block)

                if idx < len(questions) and self.delay > 0:
                    time.sleep(self.delay)

                pbar.update(1)

        self.logger.success(f"✅ Все ответы сохранены в {self.output_file}")
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