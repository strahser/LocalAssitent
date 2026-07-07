from typing import Dict, Any, Optional, List
from pathlib import Path
from datetime import datetime
from core.pipeline.step import Step
from core.interfaces import BrowserDriver, ResponseParser, CodeExecutor, PromptLoader, OutputWriter
from core.usecases.factory import UseCaseFactory

from config.pipeline_configs import PipelineConfig

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
            usecase = UseCaseFactory.create_new_chat(self.driver)
            usecase.execute()
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
        usecase = UseCaseFactory.create_send_message(self.driver)
        response = usecase.execute(prompt)
        context["response"] = response
        return context

class ExecuteCodeStep(Step):
    def __init__(self, executor: CodeExecutor, **kwargs):
        self.executor = executor

    def execute(self, context: Dict[str, Any]) -> Dict[str, Any]:
        code = context.get("code")
        if code:
            result = self.executor.execute(code)
            context["execution_result"] = result
            context["execution_stdout"] = result.stdout
            context["execution_stderr"] = result.stderr
            context["execution_returncode"] = result.returncode
            if result.returncode != 0:
                context["error"] = result.stderr or "Execution failed"
        return context

class SaveOutputStep(Step):
    def __init__(self, writer: OutputWriter, output_file: str = None, mode: str = "a"):
        self.writer = writer
        self.output_file = output_file
        self.mode = mode

    def execute(self, context: Dict[str, Any]) -> Dict[str, Any]:
        final_file = context.get("output_file_final", self.output_file)
        if final_file is None:
            raise ValueError("Не указан файл для сохранения")
        response = context.get("response") or ""
        prompt = context.get("prompt") or ""
        if response:
            block = f"## Вопрос\n\n{prompt}\n\n## Ответ\n\n{response}\n\n---\n"
            self.writer.write(block, final_file, self.mode)
        return context

class IfErrorStep(Step):
    def __init__(self, sub_steps: List[Dict], driver: BrowserDriver = None, parser: ResponseParser = None,
                 executor: CodeExecutor = None, loader: PromptLoader = None, writer: OutputWriter = None, **kwargs):
        self.sub_steps_config = sub_steps
        self.driver = driver
        self.parser = parser
        self.executor = executor
        self.loader = loader
        self.writer = writer

    def execute(self, context: Dict[str, Any]) -> Dict[str, Any]:
        if context.get("error"):
            from core.pipeline.factory import PipelineFactory
            sub_pipeline = PipelineFactory.create_from_config(
                {"steps": self.sub_steps_config},
                self.driver, self.parser, self.executor, self.loader, self.writer
            )
            sub_pipeline.context = context
            sub_pipeline.run()
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
                 parser: ResponseParser = None, executor: CodeExecutor = None,
                 loader: PromptLoader = None, writer: OutputWriter = None, **kwargs):
        self.for_each = for_each
        self.steps_config = steps
        self.driver = driver
        self.parser = parser
        self.executor = executor
        self.loader = loader
        self.writer = writer

    def execute(self, context: Dict[str, Any]) -> Dict[str, Any]:
        items = context.get(self.for_each, [])
        if not items:
            return context
        from core.pipeline.factory import PipelineFactory
        for item in items:
            sub_context = context.copy()
            sub_context["prompt"] = item
            sub_pipeline = PipelineFactory.create_from_config(
                PipelineConfig(steps=self.steps_config),
                self.driver, self.parser, self.executor, self.loader, self.writer
            )
            sub_pipeline.context = sub_context
            sub_pipeline.run()
        return context

class ExtractCodeStep(Step):
    def __init__(self, parser: ResponseParser, **kwargs):
        self.parser = parser

    def execute(self, context: Dict[str, Any]) -> Dict[str, Any]:
        response = context.get("response")
        if response:
            code = self.parser.extract_code(response)
            context["code"] = code
        return context