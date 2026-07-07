import time
from typing import Optional, Callable

from config import config  # для доступа к ScenarioConfig
from scenarios.ScenarioBase import ScenarioBase


class TextScenario(ScenarioBase):
    def __init__(self, client, logger, config: config.ScenarioConfig):
        super().__init__(client, logger, config)

    def run(self, progress_callback: Optional[Callable[[int, int], None]] = None) -> bool:
        self.logger.info("🚀 Запуск сценария: Text")
        try:
            with open(self.config.input_file, 'r', encoding='utf-8') as f:
                questions = [line.strip() for line in f if line.strip()]
        except FileNotFoundError:
            self.logger.error(f"❌ Файл {self.config.input_file} не найден")
            return False
        if not questions:
            self.logger.error("❌ Файл с вопросами пуст")
            return False

        self.logger.info(f"📖 Найдено {len(questions)} вопросов")
        # Очищаем выходной файл
        with open(self.config.output_file, 'w', encoding='utf-8') as f:
            f.write("")

        total = len(questions)
        for idx, q in enumerate(questions, 1):
            self.logger.info(f"📝 Вопрос {idx}/{total}: {q[:50]}...")

            if self.config.create_new_chat:
                self.logger.info("🔄 Создание нового чата...")
                self.client.new_chat()
                time.sleep(1)

            prompt = f"{self.config.prompt_template}\n\n{q}"
            response = self.client.send_message(prompt)

            if response is None:
                self.logger.error(f"❌ Не удалось получить ответ на вопрос {idx}")
                block = f"## Вопрос {idx}: {q}\n\n### Ответ\n\n*Ошибка получения ответа*\n\n---\n"
            else:
                self.logger.info(f"✅ Ответ на вопрос {idx} получен ({len(response)} символов)")
                block = f"## Вопрос {idx}: {q}\n\n### Ответ\n\n{response}\n\n---\n"

            with open(self.config.output_file, 'a', encoding='utf-8') as f:
                f.write(block)

            if idx < total and self.config.delay_between_questions > 0:
                time.sleep(self.config.delay_between_questions)

            if progress_callback:
                progress_callback(idx, total)

        self.logger.success(f"✅ Все ответы сохранены в {self.config.output_file}")
        return True