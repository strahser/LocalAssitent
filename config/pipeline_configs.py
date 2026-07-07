from dataclasses import dataclass, field
from typing import List, Optional, Any, Dict, Union

# Базовый класс для конфигурации шага
@dataclass
class StepConfig:
    name: str
    enabled: bool = True

# Конкретные шаги
@dataclass
class NewChatStepConfig(StepConfig):
    name: str = "NewChatStep"

@dataclass
class SendPromptStepConfig(StepConfig):
    name: str = "SendPromptStep"
    prompt_template: Optional[str] = None

@dataclass
class ExtractCodeStepConfig(StepConfig):
    name: str = "ExtractCodeStep"

@dataclass
class ExecuteCodeStepConfig(StepConfig):
    name: str = "ExecuteCodeStep"

@dataclass
class SaveOutputStepConfig(StepConfig):
    name: str = "SaveOutputStep"
    output_file: str = "output.txt"
    mode: str = "a"

@dataclass
class IfErrorStepConfig(StepConfig):
    name: str = "IfErrorStep"
    sub_steps: List[StepConfig] = field(default_factory=list)

@dataclass
class LoadPromptsStepConfig(StepConfig):
    name: str = "LoadPromptsStep"
    input_file: str = "prompts.txt"

@dataclass
class InitOutputFileStepConfig(StepConfig):
    name: str = "InitOutputFileStep"
    output_file: str = "output.txt"
    suffix: bool = True

@dataclass
class LoopStepConfig(StepConfig):
    name: str = "LoopStep"
    for_each: str = ""
    steps: List[StepConfig] = field(default_factory=list)

@dataclass
class PipelineConfig:
    description: str = ""
    steps: List[StepConfig] = field(default_factory=list)

# Предопределённые сценарии
CODE_PIPELINE = PipelineConfig(
    description="Генерация и выполнение Python кода",
    steps=[
        NewChatStepConfig(enabled=False),
        SendPromptStepConfig(
            prompt_template="Напиши Python-скрипт, который создаёт резервную копию папки logs. ОТВЕТЬ ТОЛЬКО КОДОМ В БЛОКЕ ```python ... ```, БЕЗ ПОЯСНЕНИЙ."
        ),
        ExtractCodeStepConfig(),
        ExecuteCodeStepConfig(),
        IfErrorStepConfig(
            sub_steps=[
                SendPromptStepConfig(
                    prompt_template="Исправь ошибку в коде:\n```\n{error}\n```\nВерни только исправленный код."
                ),
                ExtractCodeStepConfig(),
                ExecuteCodeStepConfig()
            ]
        ),
        SaveOutputStepConfig(output_file="result.txt")
    ]
)

TEXT_PIPELINE = PipelineConfig(
    description="Обработка вопросов из файла",
    steps=[
        LoadPromptsStepConfig(input_file="tests/questions.txt"),
        InitOutputFileStepConfig(output_file="answers.md"),
        LoopStepConfig(
            for_each="prompts",
            steps=[
                SendPromptStepConfig(
                    prompt_template="Ответь на вопрос подробно и структурировано в формате markdown:\n\n{prompt}"
                ),
                SaveOutputStepConfig(output_file="answers.md", mode="a")
            ]
        )
    ]
)

# Словарь сценариев
PIPELINE_DEFINITIONS = {
    "code": CODE_PIPELINE,
    "text": TEXT_PIPELINE
}
