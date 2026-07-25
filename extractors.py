# extractors.py – парсер кода из ответов DeepSeek
import re
from abc import ABC, abstractmethod

PYTHON_KEYWORDS_RE = re.compile(
    r'^(import|from|def|class|if|for|while|try|with|async|@|print|return|pass|break|continue|raise|except|finally|lambda|yield|global|nonlocal|#)'
)

PYTHON_LIKELY_PATTERNS = [
    r'\bimport\s+\w+',
    r'\bfrom\s+\w+\s+import',
    r'\bdef\s+\w+\s*\(',
    r'\bclass\s+\w+',
    r'\bif\s+.*:',
    r'\bfor\s+.*:',
    r'\bwhile\s+.*:',
    r'\btry\s*:',
    r'\bwith\s+.*:',
    r'print\s*\(',
    r'return\s+',
    r'@\w+',
    r'=\s*lambda',
]

CODE_SCORE_PATTERNS = [
    r'\bimport\b', r'\bfrom\b', r'\bdef\b', r'\bclass\b',
    r'\bif\b', r'\bfor\b', r'\bwhile\b', r'\btry\b',
    r'\bwith\b', r'\breturn\b', r'\bprint\b', r'\blambda\b',
]

STRIP_LINES = frozenset(('Копировать', 'Скачать', 'python', 'bash', 'cmd', '```', '```python', '```py'))


class BaseExtractor(ABC):
    @abstractmethod
    def extract(self, text: str) -> str:
        pass


class RegexExtractor(BaseExtractor):
    def extract(self, text: str) -> str:
        for method in (self._extract_code_blocks, self._extract_by_indentation, self._extract_loose_code):
            code = method(text)
            if code:
                return code
        return None

    def _extract_code_blocks(self, text: str) -> str:
        python_blocks = list(re.finditer(r'```python\s*(.*?)```', text, re.DOTALL))
        all_blocks = list(re.finditer(r'```(.*?)```', text, re.DOTALL))

        candidates = []
        for match in python_blocks:
            content = match.group(1).strip()
            if content:
                candidates.append(content)

        for match in all_blocks:
            content = match.group(1).strip()
            if not content:
                continue
            first_line = content.split('\n')[0].strip().lower()
            if first_line in ('python', 'py', 'python3') or first_line.startswith('python'):
                content = '\n'.join(content.split('\n')[1:]).strip()
            if content and self._is_likely_python(content):
                candidates.append(content)

        if not candidates:
            return None
        best = max(candidates, key=lambda c: (self._score_code(c), len(c)))
        return self._clean_block(best)

    def _extract_by_indentation(self, text: str) -> str:
        lines = text.splitlines()
        code_lines = []
        in_code = False
        for line in lines:
            stripped = line.strip()
            if stripped in STRIP_LINES:
                continue
            if PYTHON_KEYWORDS_RE.match(stripped):
                in_code = True
                code_lines.append(line)
            elif in_code and (line.startswith((' ', '\t')) or stripped == ''):
                code_lines.append(line)
            elif in_code and stripped == '':
                if code_lines and not code_lines[-1].strip():
                    code_lines.pop()
                break
            elif in_code:
                break
        if code_lines:
            code = '\n'.join(code_lines).strip()
            if len(code) >= 20 and self._is_likely_python(code):
                return self._clean_block(code)
        return None

    def _extract_loose_code(self, text: str) -> str:
        lines = text.splitlines()
        for i, line in enumerate(lines):
            stripped = line.strip()
            if stripped and PYTHON_KEYWORDS_RE.match(stripped):
                code_lines = []
                j = i
                while j < len(lines):
                    l = lines[j]
                    if l.strip() and not l.startswith((' ', '\t')) and not PYTHON_KEYWORDS_RE.match(l.strip()):
                        if not l.strip().startswith(('(', '[', '{')):
                            break
                    code_lines.append(l)
                    j += 1
                if code_lines:
                    code = '\n'.join(code_lines).strip()
                    if len(code) >= 20:
                        return self._clean_block(code)
                break
        return None

    def _is_likely_python(self, text: str) -> bool:
        score = sum(1 for pat in PYTHON_LIKELY_PATTERNS if re.search(pat, text))
        if '=' in text or '(' in text or ')' in text:
            score += 1
        if score >= 2 and len(text) > 20:
            return True
        lines = text.splitlines()
        indent_count = sum(1 for line in lines if line.startswith((' ', '\t')) and line.strip())
        return len(lines) > 3 and indent_count > len(lines) * 0.3

    def _score_code(self, code: str) -> int:
        score = sum(len(re.findall(p, code)) for p in CODE_SCORE_PATTERNS)
        score += len(code) // 100
        return score

    def _clean_block(self, code: str) -> str:
        code = re.sub(r'^```(python|py)?\s*', '', code, flags=re.MULTILINE)
        code = re.sub(r'```\s*$', '', code, flags=re.MULTILINE)
        return '\n'.join(
            line for line in code.splitlines()
            if line.strip() not in STRIP_LINES
        ).strip()


class SimpleExtractor(BaseExtractor):
    def extract(self, text: str) -> str:
        return text


class ExtractorFactory:
    @staticmethod
    def get_extractor(strategy="regex"):
        if strategy == "regex":
            return RegexExtractor()
        elif strategy == "simple":
            return SimpleExtractor()
        else:
            raise ValueError(f"Неизвестная стратегия: {strategy}")