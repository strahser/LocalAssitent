from dataclasses import dataclass, field
from typing import List, Optional, Union, Dict, Any

@dataclass
class StepConfig:
    name: str
    enabled: bool = True
    # Базовый класс, можно добавить общие поля

@dataclass
class NewChatStepConfig(StepConfig):
    name: str = "NewChatStep"
    enabled: bool = True

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
    output_file: str = "result.txt"
    mode: str = "w"

@dataclass
class LoadPromptsStepConfig(StepConfig):
    name: str = "LoadPromptsStep"
    input_file: str = "prompts.txt"

@dataclass
class LoopStepConfig(StepConfig):
    name: str = "LoopStep"
    for_each: str = "prompts"
    steps: List[StepConfig] = field(default_factory=list)

@dataclass
class IfErrorStepConfig(StepConfig):
    name: str = "IfErrorStep"
    sub_steps: List[StepConfig] = field(default_factory=list)

@dataclass
class PipelineConfig:
    description: str = ""
    steps: List[StepConfig] = field(default_factory=list)
