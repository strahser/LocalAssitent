from core.interfaces import PromptLoader, OutputWriter
from typing import List

class FilePromptLoader(PromptLoader):
    def load_prompts(self, source: str) -> List[str]:
        with open(source, 'r', encoding='utf-8') as f:
            return [line.strip() for line in f if line.strip()]

class FileOutputWriter(OutputWriter):
    def write(self, data: str, destination: str, mode: str = "w") -> None:
        with open(destination, mode, encoding='utf-8') as f:
            f.write(data)
