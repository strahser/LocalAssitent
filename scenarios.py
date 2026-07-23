import re
import time
from abc import ABC, abstractmethod

from extractors import ExtractorFactory
from rules import RuleProcessor
from tools import read_file, grep_search, glob_search, list_dir, execute_code, write_file


class Scenario(ABC):
    def __init__(self, logger):
        self.logger = logger
        self.client = None
        self.config = {}

    def set_client(self, client):
        self.client = client

    def set_config(self, config: dict):
        self.config = config

    @abstractmethod
    def run(self):
        pass


class CodeScenario(Scenario):
    TOOL_PATTERN = re.compile(r"```tool:(\w+)\s*\n(.*?)```", re.DOTALL)

    def __init__(self, logger):
        super().__init__(logger)
        self.extractor = ExtractorFactory.get_extractor("regex")
        self.rule_processor = RuleProcessor()

    def _extract_code(self, full_text: str, code_from_block: str = None) -> str:
        if code_from_block:
            self.logger.log("✅ Код получен напрямую из блока кода")
            return code_from_block
        code = self.extractor.extract(full_text)
        if not code:
            self.logger.log("❌ Не удалось извлечь код из ответа", "ERROR")
        return code

    def _is_task_complete(self, text: str) -> bool:
        pattern = r"TASK_COMPLETE\s*:\s*(.+)"
        match = re.search(pattern, text, re.IGNORECASE | re.DOTALL)
        if match:
            summary = match.group(1).strip()
            self.logger.log(f"🏁 AI сообщил о завершении задачи: {summary}", "SUCCESS")
            return True
        return False

    def _parse_tool_blocks(self, text: str):
        blocks = []
        for match in self.TOOL_PATTERN.finditer(text):
            cmd = match.group(1).strip()
            args = match.group(2).strip()
            blocks.append((cmd, args))
        if blocks:
            self.logger.log(f"🔧 Найдено {len(blocks)} tool-блоков")
        return blocks

    def _execute_tool(self, cmd: str, args: str) -> str:
        self.logger.log(f"🔧 Выполнение tool:{cmd} с аргументами: {args[:100]}")
        try:
            lines = args.splitlines()
            first = lines[0] if lines else ""
            rest = "\n".join(lines[1:]) if len(lines) > 1 else ""

            if cmd == "read":
                parts = first.split()
                path = parts[0]
                offset = int(parts[1]) if len(parts) > 1 else 0
                limit = int(parts[2]) if len(parts) > 2 else 2000
                return read_file(path, offset, limit)
            elif cmd == "grep":
                parts = first.split(None, 2)
                pattern = parts[0]
                root = parts[1] if len(parts) > 1 else "."
                include = parts[2] if len(parts) > 2 else "*.py"
                return grep_search(pattern, root, include)
            elif cmd == "glob":
                parts = first.split(None, 1)
                pattern = parts[0]
                root = parts[1] if len(parts) > 1 else "."
                return glob_search(pattern, root)
            elif cmd == "ls":
                parts = first.split()
                path = parts[0] if parts else "."
                depth = int(parts[1]) if len(parts) > 1 else 2
                return list_dir(path, depth)
            elif cmd == "write":
                path = first
                content = rest
                force = "--force" in lines
                return write_file(path, content, force=force)
            elif cmd == "exec":
                return execute_code(args, timeout=30)
            else:
                return f"ERROR: Unknown tool '{cmd}'. Available: read, grep, glob, ls, write, exec"
        except Exception as e:
            return f"ERROR: {cmd} failed: {e}"

    def _extract_thinking(self, text: str) -> str:
        lines = text.splitlines()
        non_code_lines = []
        in_code = False
        in_tool = False
        for line in lines:
            if line.strip().startswith("```tool:"):
                in_tool = True
                continue
            if in_tool:
                if line.strip().startswith("```"):
                    in_tool = False
                continue
            if line.strip().startswith("```"):
                in_code = not in_code
                continue
            if not in_code:
                non_code_lines.append(line)
        return "\n".join(non_code_lines).strip()

    def run(self):
        self.logger.log("🚀 Запуск сценария: Code (итеративный цикл)")

        prompt_template = self.config.get("prompt_template", "")
        max_iterations = self.config.get("max_iterations", 30)
        auto_send = self.config.get("auto_send_results", True)
        timeout_script = self.config.get("timeout_script", 60)
        create_new_chat = self.config.get("create_new_chat", False)
        files = self.config.get("files", [])

        if create_new_chat:
            self.client.new_chat()
            time.sleep(2)

        if files:
            self.logger.log(f"📎 Прикрепление файлов: {files}")
            self.client.attach_files(files)
            time.sleep(1)

        current_prompt = prompt_template

        for iteration in range(1, max_iterations + 1):
            self.logger.log(f"🔁 Итерация {iteration}/{max_iterations}")

            if iteration == 1:
                result = self.client.send_prompt_with_code(current_prompt)
            else:
                result = self.client.continue_chat_with_code(current_prompt)

            if result is None:
                self.logger.log("❌ Не удалось получить ответ от DeepSeek", "ERROR")
                return False

            full_text, code_from_block = result
            self.logger.log_response(full_text)

            if self._is_task_complete(full_text):
                self.logger.log("✅ Задача завершена по решению AI", "SUCCESS")
                return True

            tool_blocks = self._parse_tool_blocks(full_text)
            if tool_blocks and auto_send and iteration < max_iterations:
                results = []
                for cmd, args in tool_blocks:
                    output = self._execute_tool(cmd, args)
                    results.append(f"--- tool:{cmd} result ---\n{output}")
                current_prompt = "\n\n".join(results) + "\n\nПроанализируй результаты и продолжи."
                continue

            code = self._extract_code(full_text, code_from_block)
            if code is None:
                thinking = self._extract_thinking(full_text)
                if thinking and iteration < max_iterations and auto_send:
                    self.logger.log("💭 AI прислал размышления без кода. Отправляем уточнение...")
                    current_prompt = (
                        "Пожалуйста, напиши код Python для решения задачи. "
                        "Помести его в блок ```python ... ```. "
                        "Если нужно прочитать файлы или поискать — используй ```tool:read ...``` и ```tool:grep ...```. "
                        "Когда задача решена — напиши TASK_COMPLETE: <описание>."
                    )
                    continue
                else:
                    self.logger.log("❌ Код не найден, AI не завершил задачу", "ERROR")
                    return False

            self.logger.log("✅ Код извлечён, проверка синтаксиса...")
            ok, err = self.rule_processor.check_syntax(code)
            if not ok:
                self.logger.log(f"⚠️ Синтаксическая ошибка: {err}", "WARNING")
                if auto_send and iteration < max_iterations:
                    current_prompt = (
                        f"Синтаксическая ошибка в коде:\n```\n{err}\n```\n"
                        "Исправь код и верни его в блоке ```python ... ```."
                    )
                    continue
                else:
                    self.logger.log("❌ Синтаксическая ошибка, исправление отключено", "ERROR")
                    return False

            self.rule_processor.timeout = timeout_script
            stdout, stderr, returncode = self.rule_processor.execute(code)

            if returncode == 0:
                self.logger.log("✅ Код выполнен успешно", "SUCCESS")
                result_summary = stdout.strip() if stdout else "(код выполнен без вывода)"
                if stdout:
                    self.logger.log("📄 Stdout:")
                    print(stdout)
                if stderr:
                    self.logger.log("⚠️ Stderr:", "WARNING")
                    print(stderr)

                if auto_send and iteration < max_iterations:
                    current_prompt = (
                        f"Код выполнился успешно. Результат:\n```\n{result_summary[:3000]}\n```\n\n"
                        "Если задача решена полностью — напиши TASK_COMPLETE: <описание>.\n"
                        "Если нужно ещё что-то сделать — напиши код в блоке ```python ... ```, "
                        "или используй ```tool:read ...``` для чтения файлов, "
                        "```tool:grep ...``` для поиска, "
                        "```tool:glob ...``` для поиска файлов."
                    )
                    continue
                else:
                    self.logger.log("🏁 Цикл завершён", "SUCCESS")
                    return True
            else:
                error_text = stderr.strip() or stdout.strip() or "Unknown error"
                self.logger.log(f"❌ Код завершился с ошибкой (код {returncode})", "ERROR")
                self.logger.log(f"Ошибка: {error_text[:500]}", "ERROR")

                if auto_send and iteration < max_iterations:
                    current_prompt = (
                        f"Код завершился с ошибкой:\n```\n{error_text[:3000]}\n```\n"
                        "Исправь код и верни его в блоке ```python ... ```."
                    )
                    continue
                else:
                    self.logger.log("❌ Исправление ошибок отключено или попытки исчерпаны", "ERROR")
                    return False

        self.logger.log(f"❌ Исчерпаны все итерации ({max_iterations})", "ERROR")
        return False


class TextScenario(Scenario):
    def __init__(self, logger):
        super().__init__(logger)

    def _format_qa(self, question: str, response: str) -> str:
        if response:
            return response.strip()
        return f"**Вопрос:** {question}\n\n**Ответ:** *[не получен]*\n\n---\n"

    def run(self):
        self.logger.log("🚀 Запуск сценария: Text (Q&A)")

        prompt_template = self.config.get("prompt_template", "")
        input_file = self.config.get("input_file", "questions.txt")
        output_file = self.config.get("output_file", "answers.md")
        create_new_chat = self.config.get("create_new_chat", False)
        delay = self.config.get("delay_between_questions", 1)

        try:
            with open(input_file, 'r', encoding='utf-8') as f:
                questions = [line.strip() for line in f if line.strip()]
        except FileNotFoundError:
            self.logger.log(f"❌ Файл {input_file} не найден", "ERROR")
            return False
        if not questions:
            self.logger.log("❌ Файл с вопросами пуст", "ERROR")
            return False

        self.logger.log(f"📖 Найдено {len(questions)} вопросов")
        answers = []

        for idx, q in enumerate(questions, 1):
            self.logger.log(f"📝 Вопрос {idx}/{len(questions)}: {q[:50]}...")

            if create_new_chat:
                self.client.new_chat()
                time.sleep(1)

            prompt = f"{prompt_template}\n\nВопрос: {q}"
            response = self.client.send_prompt(prompt)

            answers.append(self._format_qa(q, response))

            if response:
                self.logger.log(f"✅ Ответ на вопрос {idx} получен ({len(response)} символов)")
            else:
                self.logger.log(f"❌ Не удалось получить ответ на вопрос {idx}", "ERROR")

            if idx < len(questions) and delay > 0:
                self.logger.log(f"⏳ Пауза {delay} сек перед следующим вопросом...")
                time.sleep(delay)

        with open(output_file, 'w', encoding='utf-8') as f:
            f.write('\n'.join(answers))

        self.logger.log(f"✅ Все ответы сохранены в {output_file}", "SUCCESS")
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
