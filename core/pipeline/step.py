from abc import ABC, abstractmethod
from typing import Dict, Any

class Step(ABC):
    """Базовый класс шага пайплайна."""
    @abstractmethod
    def execute(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Выполняет шаг, модифицирует контекст и возвращает его."""
        pass
