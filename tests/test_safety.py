"""
Unit-тесты для модуля безопасности tools/safety.py
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tools.safety import safe_join, is_safe_path, PROJECT_ROOT


class TestSafety(unittest.TestCase):

    def test_project_root_exists(self):
        """PROJECT_ROOT должен существовать."""
        self.assertTrue(os.path.isdir(PROJECT_ROOT))

    def test_safe_join_relative_path(self):
        """Относительный путь должен работать."""
        result = safe_join("main.py")
        self.assertTrue(result.endswith("main.py"))
        self.assertTrue(result.startswith(PROJECT_ROOT))

    def test_safe_join_nested_path(self):
        """Вложенный путь должен работать."""
        result = safe_join("agent/selenium_client.py")
        self.assertIn("selenium_client.py", result)
        self.assertTrue(result.startswith(PROJECT_ROOT))

    def test_safe_join_dangerous_path(self):
        """Попытка выхода за пределы проекта должна вызвать ошибку."""
        with self.assertRaises(ValueError):
            safe_join("../../../etc/passwd")

    def test_safe_join_absolute_path_outside(self):
        """Абсолютный путь за пределами проекта должен вызвать ошибку."""
        with self.assertRaises(ValueError):
            safe_join("/etc/passwd")

    def test_is_safe_path_safe(self):
        """Безопасный путь должен возвращать True."""
        self.assertTrue(is_safe_path("main.py"))

    def test_is_safe_path_unsafe(self):
        """Небезопасный путь должен возвращать False."""
        self.assertFalse(is_safe_path("../../../etc/passwd"))

    def test_safe_join_current_dir(self):
        """Текущая директория должна быть безопасной."""
        result = safe_join(".")
        self.assertEqual(result, PROJECT_ROOT)


if __name__ == "__main__":
    unittest.main()
