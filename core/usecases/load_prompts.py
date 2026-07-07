from core.interfaces import PromptLoader
from typing import List

class LoadPromptsUseCase:
    def __init__(self, loader: PromptLoader):
        self.loader = loader

    def execute(self, source: str) -> List[str]:
        return self.loader.load_prompts(source)
