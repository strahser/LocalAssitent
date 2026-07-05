# extractors.py – улучшенный парсер кода из ответов DeepSeek
import re
from abc import ABC, abstractmethod


class BaseExtractor(ABC):
    @abstractmethod
    def extract(self, text: str) -> str:
        pass


class RegexExtractor(BaseExtractor):
    def extract(self, text: str) -> str:
        # 1. Пытаемся найти блоки кода с явным указанием python или без
        code = self._extract_code_blocks(text)
        if code:
            return code

        # 2. Эвристический поиск по отступам и ключевым словам
        code = self._extract_by_indentation(text)
        if code:
            return code

        # 3. Пробуем извлечь код, даже если он не в блоке (например, просто текст с import)
        code = self._extract_loose_code(text)
        if code:
            return code

        return None

    def _extract_code_blocks(self, text: str) -> str:
        """Ищет блоки ```python ... ``` или ``` ... ``` и выбирает лучший."""
        # Сначала ищем блоки с python
        python_blocks = list(re.finditer(r'```python\s*(.*?)```', text, re.DOTALL))
        all_blocks = list(re.finditer(r'```(.*?)```', text, re.DOTALL))

        candidates = []
        # Обрабатываем блоки с python
        for match in python_blocks:
            content = match.group(1).strip()
            if content:
                candidates.append(content)

        # Обрабатываем остальные блоки
        for match in all_blocks:
            content = match.group(1).strip()
            if not content:
                continue
            # Если блок начинается с явного указания языка, пропускаем (кроме python)
            first_line = content.split('\n')[0].strip().lower()
            if first_line in ('python', 'py', 'python3') or first_line.startswith('python'):
                content = '\n'.join(content.split('\n')[1:]).strip()
            if content and self._is_likely_python(content):
                candidates.append(content)

        if not candidates:
            return None

        # Выбираем кандидата с наибольшим количеством ключевых слов и длиной
        best = max(candidates, key=lambda c: (self._score_code(c), len(c)))
        return self._clean_block(best)

    def _extract_by_indentation(self, text: str) -> str:
        """Эвристический поиск: строки с отступами и ключевыми словами."""
        lines = text.splitlines()
        code_lines = []
        in_code = False
        for i, line in enumerate(lines):
            stripped = line.strip()
            # Пропускаем служебные строки
            if stripped in ('Копировать', 'Скачать', 'python', 'bash', 'cmd', '```', '```python', '```py'):
                continue
            # Если строка начинается с ключевого слова или является отступом
            if re.match(
                    r'^(import|from|def|class|if|for|while|try|with|async|@|print|return|pass|break|continue|raise|except|finally|lambda|yield|global|nonlocal|#)',
                    stripped):
                in_code = True
                code_lines.append(line)
            elif in_code and (line.startswith(' ') or line.startswith('\t') or stripped == ''):
                # Пустая строка внутри кода допустима
                code_lines.append(line)
            elif in_code and stripped == '':
                # Пустая строка вне блока – возможно конец
                if len(code_lines) > 0 and not code_lines[-1].strip():
                    code_lines.pop()  # удаляем последнюю пустую
                break
            elif in_code:
                # Если строка не похожа на код и не пустая, вероятно конец
                break
        if code_lines:
            code = '\n'.join(code_lines).strip()
            if len(code) >= 20 and self._is_likely_python(code):
                return self._clean_block(code)
        return None

    def _extract_loose_code(self, text: str) -> str:
        """Извлекает фрагменты кода без маркеров (например, если ответ начинается с import)."""
        lines = text.splitlines()
        code_lines = []
        for i, line in enumerate(lines):
            stripped = line.strip()
            if stripped and re.match(
                    r'^(import|from|def|class|if|for|while|try|with|async|@|print|return|pass|break|continue|raise|except|finally|lambda|yield|global|nonlocal|#)',
                    stripped):
                # Начинаем собирать код
                j = i
                while j < len(lines):
                    l = lines[j]
                    if l.strip() and not l.startswith(' ') and not l.startswith('\t') and not re.match(
                            r'^(import|from|def|class|if|for|while|try|with|async|@|print|return|pass|break|continue|raise|except|finally|lambda|yield|global|nonlocal|#)',
                            l.strip()):
                        # Если строка не является отступом и не ключевое слово, вероятно конец
                        # Но может быть просто переменная или вызов, тогда продолжаем
                        if not l.strip().startswith('(') and not l.strip().startswith('[') and not l.strip().startswith(
                                '{'):
                            break
                    code_lines.append(l)
                    j += 1
                break
        if code_lines:
            code = '\n'.join(code_lines).strip()
            if len(code) >= 20:
                return self._clean_block(code)
        return None

    def _is_likely_python(self, text: str) -> bool:
        """Проверяет, похож ли текст на код Python."""
        # Ищем характерные конструкции
        patterns = [
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
        score = 0
        for pat in patterns:
            if re.search(pat, text):
                score += 1
        # Дополнительно: наличие скобок, операторов
        if '=' in text or '(' in text or ')' in text:
            score += 1
        # Проверяем, что текст не слишком короткий и не содержит явно непитоновские конструкции
        if score >= 2 and len(text) > 20:
            return True
        # Если очень много строк с отступами – тоже код
        lines = text.splitlines()
        indent_count = sum(1 for line in lines if line.startswith((' ', '\t')) and line.strip())
        if len(lines) > 3 and indent_count > len(lines) * 0.3:
            return True
        return False

    def _score_code(self, code: str) -> int:
        """Оценивает качество кода по количеству ключевых слов и длине."""
        patterns = [
            r'\bimport\b', r'\bfrom\b', r'\bdef\b', r'\bclass\b',
            r'\bif\b', r'\bfor\b', r'\bwhile\b', r'\btry\b',
            r'\bwith\b', r'\breturn\b', r'\bprint\b', r'\blambda\b'
        ]
        score = sum(len(re.findall(p, code)) for p in patterns)
        # Учитываем длину
        score += len(code) // 100
        return score

    def _clean_block(self, code: str) -> str:
        """Очищает код от лишних маркеров и слов."""
        # Убираем возможные маркеры начала/конца
        code = re.sub(r'^```(python|py)?\s*', '', code, flags=re.MULTILINE)
        code = re.sub(r'```\s*$', '', code, flags=re.MULTILINE)
        # Убираем строки, содержащие только "Копировать" или "Скачать"
        lines = code.splitlines()
        cleaned = []
        for line in lines:
            stripped = line.strip()
            if stripped in ('Копировать', 'Скачать', 'python', 'bash', 'cmd'):
                continue
            cleaned.append(line)
        return '\n'.join(cleaned).strip()


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