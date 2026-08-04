import os
import re
import sys
import time
import subprocess
from abc import ABC, abstractmethod

from config import PIPELINE_FILES, DEFAULT_QWEN_MODEL
from extractors import ExtractorFactory
from rules import RuleProcessor
from tools import read_file, grep_search, glob_search, list_dir, execute_code, write_file
from tools.merge_docs import merge_documents, merge_documents_multi
from tools.send_to_cloud import send_to_cloud
from tools.list_models import list_models


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
            elif cmd == "merge":
                return self._run_merge_tool(first, rest)
            elif cmd == "send_to_cloud":
                return send_to_cloud(args)
            elif cmd == "list_models":
                return list_models()
            else:
                return f"ERROR: Unknown tool '{cmd}'. Available: read, grep, glob, ls, write, exec, merge, send_to_cloud, list_models"
        except Exception as e:
            return f"ERROR: {cmd} failed: {e}"

    def _run_merge_tool(self, first: str, rest: str) -> str:
        """Обрабатывает tool:merge — сведение файлов в один TXT.

        Формат:
            ```tool:merge
            <dir1> [<dir2> ...]
            [--ext .cs .py] [--output <файл>]
            ```
        """
        dirs = [d for d in first.split() if d and not d.startswith("--")]
        if not dirs:
            return "ERROR: merge: укажите хотя бы одну директорию"

        extensions = None
        output_file = "merged_context.txt"
        tokens = rest.split()
        i = 0
        while i < len(tokens):
            tok = tokens[i]
            if tok == "--ext" and i + 1 < len(tokens):
                extensions = []
                i += 1
                while i < len(tokens) and not tokens[i].startswith("--"):
                    extensions.append(tokens[i])
                    i += 1
                continue
            if tok == "--output" and i + 1 < len(tokens):
                output_file = tokens[i + 1]
                i += 2
                continue
            i += 1

        if len(dirs) == 1:
            return merge_documents(root_dir=dirs[0], output_file=output_file, extensions=extensions)
        return merge_documents_multi(
            root_dirs=dirs, output_file=output_file, extensions=extensions
        )

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

        paste_clipboard = self.config.get("paste_clipboard", False)
        if paste_clipboard:
            self.logger.log("📋 Вставка файлов из буфера обмена (Ctrl+V)...")
            self.client.paste_files_from_clipboard()
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

            paste_clipboard = self.config.get("paste_clipboard", False)
            if paste_clipboard:
                self.logger.log("📋 Вставка файлов из буфера обмена (Ctrl+V)...")
                self.client.paste_files_from_clipboard()
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


class MergeScenario(Scenario):
    def __init__(self, logger):
        super().__init__(logger)

    def run(self):
        self.logger.log("🚀 Запуск сценария: Merge (сведение документов)")

        merge_dir = self.config.get("merge_dir", ".")
        extensions = self.config.get("extensions", None)
        output_file = self.config.get("output_file", "merged_context.txt")
        max_file_size = self.config.get("max_file_size", 100_000)
        exclude_dirs = self.config.get("exclude_dirs", None)

        self.logger.log(f"📂 Директория: {merge_dir}")
        self.logger.log(f"📄 Выходной файл: {output_file}")
        if extensions:
            self.logger.log(f"🔍 Расширения: {extensions}")

        result = merge_documents(
            root_dir=merge_dir,
            output_file=output_file,
            extensions=extensions,
            exclude_dirs=set(exclude_dirs) if exclude_dirs else None,
            max_file_size=max_file_size,
        )
        self.logger.log(f"✅ {result}", "SUCCESS")
        return True


class ImproveScenario(CodeScenario):
    """
    Непрерывный цикл улучшения кода (до отмены пользователем):
        анализ кода → рекомендации/улучшения (tool-блоки) → применение →
        проверка (py_compile + pytest) → переоценка → повтор.

    Остановка: ответ AI содержит NO_IMPROVEMENTS / TASK_COMPLETE,
    достигнут max_iterations (0 = бесконечно), либо Ctrl+C.
    """

    DONE_PATTERN = re.compile(r"\b(NO_IMPROVEMENTS|NO_IMPROVEMENT|TASK_COMPLETE)\b", re.IGNORECASE)

    def __init__(self, logger):
        super().__init__(logger)

    def _project_root(self) -> str:
        return os.path.dirname(os.path.abspath(__file__))

    def _load_prompt(self, key: str, default_rel: str, fallback: str = "") -> str:
        rel = self.config.get(key, default_rel)
        path = os.path.join(self._project_root(), rel)
        try:
            with open(path, "r", encoding="utf-8") as f:
                return f.read()
        except FileNotFoundError:
            self.logger.log(f"⚠️ Промпт-файл {path} не найден, использую дефолтный", "WARNING")
            return fallback

    def _cap_code(self, code: str, max_chars: int = 120_000) -> str:
        """Qwen ограничивает сообщение 131072 символами. Обрезаем код с пометкой."""
        if len(code) <= max_chars:
            return code
        head = code[:max_chars]
        return (
            head
            + "\n\n# ============================================================\n"
            + f"# [ПРИМЕЧАНИЕ] Полный объединённый код проекта сохранён в файле "
            + "pipeline_output/improve_merged.txt (полный объём больше лимита "
            + f"сообщения: {len(code)} символов). Показаны первые {max_chars}.\n"
            + "# Для остальных файлов используй tool:read для чтения нужных файлов.\n"
            + "# ============================================================\n"
        )

    def _merged_file_path(self) -> str:
        cfg = self.config
        out_dir = os.path.join(self._project_root(), cfg.get("output_dir", "pipeline_output"))
        return os.path.join(out_dir, "improve_merged.txt")

    def _attach_merged(self) -> bool:
        """Прикрепляет merged-файл к чату Qwen (drag-and-drop через DataTransfer).

        Qwen НЕ может прочитать длинный промпт с кодом (лимит 131072 символа) —
        уведомляет об этом ошибкой. Поэтому код проекта передаём файлом-вложением,
        а в промпт пишем только короткую инструкцию.

        send_keys в input[type='file'] Qwen игнорирует (файл не появляется),
        поэтому используем эмуляцию настоящего drag-and-drop (DataTransfer).
        """
        path = self._merged_file_path()
        if not os.path.exists(path):
            self.logger.log(f"⚠️ Merged-файл не найден: {path}", "WARNING")
            return False
        try:
            if hasattr(self.client, "attach_files_drop"):
                ok = self.client.attach_files_drop([path])
                if ok:
                    self.logger.log(f"📎 Merged-файл прикреплён (drag-and-drop): {path}")
                else:
                    self.logger.log("⚠️ Не удалось прикрепить merged-файл (drop)", "WARNING")
                return ok
            ok = self.client.attach_files([path])
            if ok:
                self.logger.log(f"📎 Merged-файл прикреплён: {path}")
            else:
                self.logger.log("⚠️ Не удалось прикрепить merged-файл", "WARNING")
            return ok
        except Exception as e:
            self.logger.log(f"⚠️ Ошибка прикрепления merged-файла: {e}", "WARNING")
            return False

    def _collect_code(self) -> str:
        """Собирает код проекта: merge_documents (несколько директорий) или PIPELINE_FILES."""
        cfg = self.config
        mode = cfg.get("collect_mode", "merge")

        if mode == "merge":
            dirs = cfg.get("merge_dirs") or [cfg.get("merge_dir", ".")]
            out_dir = os.path.join(self._project_root(), cfg.get("output_dir", "pipeline_output"))
            os.makedirs(out_dir, exist_ok=True)
            out_file = os.path.join(out_dir, "improve_merged.txt")
            try:
                if len(dirs) > 1:
                    merge_documents_multi(root_dirs=dirs, output_file=out_file,
                                          extensions=cfg.get("merge_extensions"))
                else:
                    merge_documents(root_dir=dirs[0], output_file=out_file,
                                    extensions=cfg.get("merge_extensions"))
                with open(out_file, "r", encoding="utf-8") as f:
                    return f.read()
            except Exception as e:
                return f"ERROR: не удалось собрать код: {e}"

        # Режим PIPELINE_FILES
        parts = []
        for rel_path in PIPELINE_FILES:
            abs_path = os.path.join(self._project_root(), rel_path)
            if os.path.exists(abs_path):
                try:
                    with open(abs_path, "r", encoding="utf-8") as f:
                        parts.append(f"### Файл: {rel_path}\n```python\n{f.read()}\n```\n")
                except Exception as e:
                    parts.append(f"### Файл: {rel_path}\n[Ошибка чтения: {e}]\n")
            else:
                parts.append(f"### Файл: {rel_path}\n[Файл не найден]\n")
        return "\n".join(parts)

    def _verify(self) -> str:
        """Проверка после применения улучшений: py_compile всех .py + pytest."""
        self.logger.log("🧪 Проверка: py_compile + pytest...")
        root = self._project_root()
        report = []
        try:
            r1 = subprocess.run(
                [sys.executable, "-m", "py_compile", "main.py", "config.py", "scenarios.py", "pipeline.py"],
                cwd=root, capture_output=True, text=True, timeout=120,
            )
            report.append(f"py_compile: {'OK' if r1.returncode == 0 else 'FAIL'}\n{r1.stdout}{r1.stderr}"[:500])
        except Exception as e:
            report.append(f"py_compile: ERROR {e}")
        try:
            r2 = subprocess.run(
                [sys.executable, "-m", "pytest", "tests/", "-q"],
                cwd=root, capture_output=True, text=True, timeout=300,
            )
            report.append(f"pytest: {'OK' if r2.returncode == 0 else 'FAIL'}\n{r2.stdout}{r2.stderr}"[:800])
        except Exception as e:
            report.append(f"pytest: ERROR {e}")
        return "\n".join(report)

    def _save_iteration(self, output_dir: str, iteration: int, prompt: str, response: str):
        try:
            os.makedirs(output_dir, exist_ok=True)
            path = os.path.join(output_dir, f"improve_iteration_{iteration:03d}.md")
            with open(path, "w", encoding="utf-8") as f:
                f.write(f"# Improve-итерация {iteration}\n\n## Промпт\n\n{prompt}\n\n## Ответ AI\n\n{response}\n")
            self.logger.log(f"💾 Итерация сохранена: {path}")
        except Exception as e:
            self.logger.log(f"⚠️ Не удалось сохранить итерацию: {e}", "WARNING")

    def run(self):
        self.logger.log("🚀 Запуск сценария: Improve (непрерывный цикл улучшения)")
        cfg = self.config
        provider = cfg.get("provider", "qwen")
        model = cfg.get("model", DEFAULT_QWEN_MODEL)
        max_iterations = cfg.get("max_iterations", 0)  # 0 = до отмены
        output_dir = os.path.join(self._project_root(), cfg.get("output_dir", "pipeline_output"))
        delay = cfg.get("delay_between_questions", 3)

        if provider == "qwen" and model:
            try:
                self.client.select_model(model)
            except Exception as e:
                self.logger.log(f"⚠️ Не удалось выбрать модель {model}: {e}", "WARNING")

        self.logger.log(f"📚 Сбор кода проекта (режим: {cfg.get('collect_mode', 'merge')})...")
        code = self._collect_code()
        merged_path = self._merged_file_path()
        code_len = len(code)
        if os.path.exists(merged_path):
            code_len = os.path.getsize(merged_path)
        self.logger.log(f"   Собрано {code_len} символов (файл: {merged_path})")

        analyze_prompt = self._load_prompt(
            "prompt_analyze_file", "prompts/improve_analyze.txt",
            fallback="Проанализируй код проекта и улучши его. Используй ```tool:...``` для изменений.",
        )
        review_prompt = self._load_prompt(
            "prompt_review_file", "prompts/improve_review.txt",
            fallback="Вот обновлённый код и предыдущая обратная связь. Продолжи улучшение или напиши NO_IMPROVEMENTS.",
        )

        # Qwen не может прочитать длинный промпт с кодом (лимит 131072 символа).
        # Код проекта передаём прикреплённым файлом (drag-and-drop), промпт — короткий.
        attached = self._attach_merged()
        if not attached:
            self.logger.log("⚠️ Продолжаю без вложения файла (код будет усечён в промпте)", "WARNING")

        iteration = 0
        current_prompt = analyze_prompt + "\n\n[Код проекта прикреплён файлом improve_merged.txt]"
        try:
            while True:
                iteration += 1
                if max_iterations and iteration > max_iterations:
                    self.logger.log(f"⏹ Достигнут лимит итераций ({max_iterations})", "SUCCESS")
                    return True

                self.logger.log(f"🔁 Итерация {iteration}" + (f"/{max_iterations}" if max_iterations else ""))

                if attached and hasattr(self.client, "send_message_with_attached_file"):
                    # После drag-and-drop текстаrea/кнопка недоступны Selenium —
                    # используем JS-путь (ввод nativeSetter + JS-клик по send-button).
                    result = self.client.send_message_with_attached_file(current_prompt)
                elif iteration == 1:
                    result = self.client.send_prompt_with_code(current_prompt)
                else:
                    result = self.client.continue_chat_with_code(current_prompt)

                if result is None:
                    self.logger.log("❌ Не удалось получить ответ от AI", "ERROR")
                    return False

                full_text, _ = result
                self.logger.log_response(full_text)
                self._save_iteration(output_dir, iteration, current_prompt, full_text)

                if self.DONE_PATTERN.search(full_text):
                    self.logger.log("✅ AI сообщил: улучшений больше не требуется", "SUCCESS")
                    return True

                tool_blocks = self._parse_tool_blocks(full_text)
                if tool_blocks:
                    self.logger.log(f"🔧 Применяю {len(tool_blocks)} изменений...")
                    results = []
                    for cmd, args in tool_blocks:
                        output = self._execute_tool(cmd, args)
                        results.append(f"--- tool:{cmd} result ---\n{output}")
                    current_prompt = (
                        "\n\n".join(results)
                        + "\n\nПроверь результат применения изменений. "
                        "Если нужно — продолжай улучшение, иначе напиши NO_IMPROVEMENTS."
                    )
                    continue

                # Нет tool-блоков → переоценка обновлённого кода
                self.logger.log("🧪 Проверка после улучшений...")
                verify_report = self._verify()
                code = self._cap_code(self._collect_code())
                current_prompt = (
                    review_prompt
                    + "\n\n[Обновлённый код проекта прикреплён файлом improve_merged.txt]"
                    + "\n\n## Предыдущая обратная связь\n" + full_text[:6000]
                    + "\n\n## Проверка\n" + verify_report[:1500]
                    + "\n\nПродолжи улучшение (tool-блоками) или напиши NO_IMPROVEMENTS."
                )

                if delay > 0:
                    time.sleep(delay)
        except KeyboardInterrupt:
            self.logger.log("🛑 Остановлено пользователем (Ctrl+C)", "SUCCESS")
            return True
        except Exception as e:
            self.logger.log(f"❌ Ошибка цикла улучшения: {e}", "ERROR")
            return False


class ScenarioFactory:
    @staticmethod
    def get_scenario(name, logger):
        scenarios = {
            "code": CodeScenario,
            "text": TextScenario,
            "merge": MergeScenario,
            "improve": ImproveScenario,
        }
        cls = scenarios.get(name)
        if cls is None:
            raise ValueError(f"Неизвестный сценарий: {name}")
        return cls(logger)
