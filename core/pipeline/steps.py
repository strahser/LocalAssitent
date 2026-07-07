import subprocess
import tempfile
import os
from typing import Dict, Any, Optional, List
from pathlib import Path
from datetime import datetime
from core.pipeline.step import Step
from core.interfaces import BrowserDriver, PromptLoader, OutputWriter
from core.processing.extractors import ExtractorFactory

class InitOutputFileStep(Step):
    def __init__(self, output_file: str, suffix: bool = True):
        self.base_name = output_file
        self.suffix = suffix

    def execute(self, context: Dict[str, Any]) -> Dict[str, Any]:
        if self.suffix:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            file_path = Path(self.base_name)
            final_name = f"{file_path.stem}_{timestamp}{file_path.suffix}"
            context["output_file_final"] = str(final_name)
        else:
            context["output_file_final"] = self.base_name
        return context

class NewChatStep(Step):
    def __init__(self, driver: BrowserDriver, enabled: bool = True, **kwargs):
        self.driver = driver
        self.enabled = enabled

    def execute(self, context: Dict[str, Any]) -> Dict[str, Any]:
        if self.enabled:
            self.driver.new_chat()
        return context

class SendPromptStep(Step):
    def __init__(self, driver: BrowserDriver, prompt_template: str = None, **kwargs):
        self.driver = driver
        self.prompt_template = prompt_template

    def execute(self, context: Dict[str, Any]) -> Dict[str, Any]:
        prompt = self.prompt_template
        if prompt and "{" in prompt:
            prompt = prompt.format(**context)
        else:
            prompt = context.get("prompt", prompt)
        response = self.driver.send_message(prompt)
        context["response"] = response
        return context

class ExtractCodeStep(Step):
    def __init__(self, extractor_type: str = "simple", **kwargs):
        self.extractor_type = extractor_type

    def execute(self, context: Dict[str, Any]) -> Dict[str, Any]:
        response = context.get("response")
        if response:
            extractor = ExtractorFactory.get_extractor(self.extractor_type)
            code = extractor.extract(response)
            context["code"] = code
        return context

class ExecuteCodeStep(Step):
    def __init__(self, timeout: int = 60, **kwargs):
        self.timeout = timeout

    def execute(self, context: Dict[str, Any]) -> Dict[str, Any]:
        code = context.get("code")
        if code:
            stdout, stderr, returncode = self._run_code(code)
            context["execution_result"] = {"stdout": stdout, "stderr": stderr, "returncode": returncode}
            context["execution_stdout"] = stdout
            context["execution_stderr"] = stderr
            context["execution_returncode"] = returncode
            if returncode != 0:
                context["error"] = stderr or "Execution failed"
            else:
                # Если ошибка была, но сейчас успешно, удаляем error
                context.pop("error", None)
        return context

    def _run_code(self, code: str):
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False, encoding='utf-8', newline='\n') as f:
            f.write(code)
            script_path = f.name
        try:
            # Устанавливаем PYTHONIOENCODING для корректного вывода в UTF-8
            env = os.environ.copy()
            env["PYTHONIOENCODING"] = "utf-8"
            result = subprocess.run(
                ['python', script_path],
                capture_output=True,
                text=True,
                encoding='utf-8',
                errors='replace',
                timeout=self.timeout,
                env=env
            )
            stdout, stderr, returncode = result.stdout.strip(), result.stderr.strip(), result.returncode
        except subprocess.TimeoutExpired:
            stdout, stderr, returncode = "", "Timeout", -1
        finally:
            os.unlink(script_path)
        return stdout, stderr, returncode

class SaveOutputStep(Step):
    def __init__(self, writer: OutputWriter, output_file: str = None, mode: str = "a"):
        self.writer = writer
        self.output_file = output_file
        self.mode = mode

    def execute(self, context: Dict[str, Any]) -> Dict[str, Any]:
        # Приоритет: context["output_file_final"] > self.output_file
        final_file = context.get("output_file_final")
        if final_file is None:
            final_file = self.output_file
        if final_file is None:
            raise ValueError("Не указан файл для сохранения")

        prompt = context.get("prompt") or ""
        response = context.get("response") or ""
        stdout = context.get("execution_stdout", "").strip()
        stderr = context.get("execution_stderr", "").strip()

        block = f"## Вопрос\n\n{prompt}\n\n## Ответ\n\n{response}\n"
        if stdout:
            block += f"\n## Вывод\n\n```\n{stdout}\n```\n"
        if stderr:
            block += f"\n## Ошибки\n\n```\n{stderr}\n```\n"
        block += "\n---\n"

        self.writer.write(block, final_file, self.mode)
        return context

class IfErrorStep(Step):
    def __init__(self, sub_steps: List[Dict], driver: BrowserDriver = None,
                 loader: PromptLoader = None, writer: OutputWriter = None, **kwargs):
        self.sub_steps_config = sub_steps
        self.driver = driver
        self.loader = loader
        self.writer = writer

    def execute(self, context: Dict[str, Any]) -> Dict[str, Any]:
        if context.get("error"):
            from core.pipeline.factory import PipelineFactory
            from config.pipeline_configs import PipelineConfig
            sub_config = PipelineConfig(steps=self.sub_steps_config)
            sub_pipeline = PipelineFactory.create_from_config(
                sub_config,
                driver=self.driver,
                loader=self.loader,
                writer=self.writer
            )
            sub_pipeline.context = context
            sub_pipeline.run()
            # Если после выполнения подшагов ошибка исчезла, удаляем её и из родительского контекста
            if sub_pipeline.context.get("error") is None:
                context.pop("error", None)
        return context

class LoadPromptsStep(Step):
    def __init__(self, loader: PromptLoader, input_file: str, **kwargs):
        self.loader = loader
        self.input_file = input_file

    def execute(self, context: Dict[str, Any]) -> Dict[str, Any]:
        prompts = self.loader.load_prompts(self.input_file)
        context["prompts"] = prompts
        return context

class LoopStep(Step):
    def __init__(self, for_each: str, steps: List[Dict], driver: BrowserDriver = None,
                 loader: PromptLoader = None, writer: OutputWriter = None, **kwargs):
        self.for_each = for_each
        self.steps_config = steps
        self.driver = driver
        self.loader = loader
        self.writer = writer

    def execute(self, context: Dict[str, Any]) -> Dict[str, Any]:
        items = context.get(self.for_each, [])
        if not items:
            return context
        from core.pipeline.factory import PipelineFactory
        from config.pipeline_configs import PipelineConfig
        for item in items:
            sub_context = context.copy()
            sub_context["prompt"] = item
            sub_pipeline = PipelineFactory.create_from_config(
                PipelineConfig(steps=self.steps_config),
                driver=self.driver,
                loader=self.loader,
                writer=self.writer
            )
            sub_pipeline.context = sub_context
            sub_pipeline.run()
            # Обновляем родительский контекст результатами последнего выполнения (если нужно)
            # Здесь можно добавить агрегацию, но пока просто копируем результат
            context.update(sub_pipeline.context)
        return context