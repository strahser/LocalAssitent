from core.interfaces import ResponseParser
from typing import Optional

class ExtractCodeUseCase:
    def __init__(self, parser: ResponseParser):
        self.parser = parser

    def execute(self, text: str) -> Optional[str]:
        return self.parser.extract_code(text)
