"""
Интерфейсы (абстракции) для всей системы.
"""
from abc import ABC, abstractmethod
from typing import Optional, List, Dict, Any
from dataclasses import dataclass

@dataclass
class ExecutionResult:
    stdout: str
    stderr: str
    returncode: int

class BrowserDriver(ABC):
    """Контракт для управления браузером."""
    @abstractmethod
    def send_message(self, prompt: str) -> None:
        """Отправляет сообщение (заполняет поле и нажимает отправку)."""
        pass

    @abstractmethod
    def new_chat(self) -> None:
        """Создаёт новый чат."""
        pass

    @abstractmethod
    def attach_file(self, file_path: str) -> None:
        """Прикрепляет файл (пока заглушка)."""
        pass

    @abstractmethod
    def close(self) -> None:
        """Закрывает браузер."""
        pass

class ResponseParser(ABC):
    """Парсинг ответа для извлечения структурированных данных."""
    @abstractmethod
    def extract_code(self, text: str) -> Optional[str]:
        """Извлекает код из текста ответа."""
        pass

    @abstractmethod
    def extract_data(self, text: str) -> Dict[str, Any]:
        """Извлекает произвольные данные (для будущего расширения)."""
        pass

class CodeExecutor(ABC):
    """Выполнение извлечённого кода."""
    @abstractmethod
    def execute(self, code: str) -> ExecutionResult:
        """Выполняет код и возвращает результат."""
        pass

class PromptLoader(ABC):
    """Загрузка промптов из источника."""
    @abstractmethod
    def load_prompts(self, source: str) -> List[str]:
        """Загружает список промптов (вопросов)."""
        pass

class OutputWriter(ABC):
    """Запись результатов в выходной поток."""
    @abstractmethod
    def write(self, data: str, destination: str, mode: str = "w") -> None:
        """Записывает данные в файл или другой выход."""
        pass
