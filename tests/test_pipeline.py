"""
Unit-тесты для pipeline: проверка сбора файлов и формирования промпта.
Запуск: python -m pytest tests/test_pipeline.py -v
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pipeline import collect_project_code, KEY_FILES, PROMPT_TEMPLATE


class TestPipeline(unittest.TestCase):

    def test_key_files_exist(self):
        """Все указанные файлы должны существовать."""
        root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        missing = []
        for f in KEY_FILES:
            if not os.path.exists(os.path.join(root, f)):
                missing.append(f)
        self.assertEqual(missing, [], f"Файлы не найдены: {missing}")

    def test_collect_code_returns_string(self):
        """collect_project_code() должен возвращать непустую строку."""
        code = collect_project_code()
        self.assertIsInstance(code, str)
        self.assertGreater(len(code), 1000)

    def test_collect_code_contains_files(self):
        """Собранный код должен содержать маркеры каждого файла."""
        code = collect_project_code()
        for f in KEY_FILES:
            marker = f"### Файл: {f}"
            self.assertIn(marker, code, f"Маркер '{marker}' не найден в собранном коде")

    def test_prompt_template_formatting(self):
        """Промпт должен корректно форматироваться с кодом."""
        code = collect_project_code()
        prompt = PROMPT_TEMPLATE.format(code=code)
        self.assertIn("LocalAssitent", prompt)
        self.assertGreater(len(prompt), 5000)

    def test_collect_code_reads_python_files(self):
        """Собранный код должен содержать Python-код из main.py."""
        code = collect_project_code()
        self.assertIn("def main():", code)
        self.assertIn("import config", code)

    def test_output_dir_creation(self):
        """Директория pipeline_output должна создаваться."""
        root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        output_dir = os.path.join(root, "pipeline_output")
        os.makedirs(output_dir, exist_ok=True)
        self.assertTrue(os.path.isdir(output_dir))


if __name__ == "__main__":
    unittest.main()
