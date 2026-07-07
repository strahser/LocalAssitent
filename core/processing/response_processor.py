from typing import Optional, Tuple
from core.processing.extractors import ExtractorFactory
from core.processing.rules import RuleProcessor

class ResponseProcessor:
    def __init__(self, extractor_type: Optional[str] = "simple", script_timeout: int = 60):
        if extractor_type is None:
            extractor_type = "simple"
        self.extractor = ExtractorFactory.get_extractor(extractor_type)
        self.rule_processor = RuleProcessor(timeout=script_timeout)

    def extract_code(self, full_response: str) -> Optional[str]:
        return self.extractor.extract(full_response)

    def validate_syntax(self, code: str) -> Tuple[bool, str]:
        return self.rule_processor.check_syntax(code)

    def execute_code(self, code: str) -> Tuple[str, str, int]:
        return self.rule_processor.execute(code)

    @staticmethod
    def is_truncation_error(error_msg: str) -> bool:
        patterns = [
            "unexpected eof while parsing",
            "unterminated string literal",
            "unterminated triple-quoted string literal",
            "(' was never closed",
            "( was never closed",
            "'{' was never closed",
            "{ was never closed",
            "'[' was never closed",
            "[ was never closed",
            "expected one or more names after 'import'",
            "unexpected indent",
            "unexpected dedent",
            "invalid syntax",
        ]
        return any(p in error_msg.lower() for p in patterns)
