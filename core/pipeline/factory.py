from typing import Dict, Any, Type, List
from core.pipeline.step import Step
from core.pipeline.steps import (
    InitOutputFileStep,
    NewChatStep, SendPromptStep, ExtractCodeStep,
    ExecuteCodeStep, SaveOutputStep, IfErrorStep, LoadPromptsStep, LoopStep
)
from core.interfaces import BrowserDriver, PromptLoader, OutputWriter
from core.pipeline.pipeline import Pipeline
from config.pipeline_configs import PipelineConfig, StepConfig

class PipelineFactory:
    @staticmethod
    def create_from_config(config: PipelineConfig,
                           driver: BrowserDriver,
                           loader: PromptLoader,
                           writer: OutputWriter) -> Pipeline:
        steps = []
        for step_config in config.steps:
            step_class = PipelineFactory._get_step_class(step_config.name)
            kwargs = {}
            # Передаём необходимые зависимости
            if "driver" in step_class.__init__.__code__.co_varnames:
                kwargs["driver"] = driver
            if "loader" in step_class.__init__.__code__.co_varnames:
                kwargs["loader"] = loader
            if "writer" in step_class.__init__.__code__.co_varnames:
                kwargs["writer"] = writer

            # Передаём параметры из конфига (кроме name и enabled)
            for key, value in step_config.__dict__.items():
                if key not in ("name", "enabled"):
                    kwargs[key] = value
            if "enabled" in step_class.__init__.__code__.co_varnames:
                kwargs["enabled"] = step_config.enabled

            steps.append(step_class(**kwargs))
        return Pipeline(steps)

    @staticmethod
    def _get_step_class(name: str) -> Type[Step]:
        mapping = {
            "NewChatStep": NewChatStep,
            "InitOutputFileStep": InitOutputFileStep,
            "SendPromptStep": SendPromptStep,
            "ExtractCodeStep": ExtractCodeStep,
            "ExecuteCodeStep": ExecuteCodeStep,
            "SaveOutputStep": SaveOutputStep,
            "IfErrorStep": IfErrorStep,
            "LoadPromptsStep": LoadPromptsStep,
            "LoopStep": LoopStep,
        }
        if name not in mapping:
            raise ValueError(f"Неизвестный шаг: {name}")
        return mapping[name]
