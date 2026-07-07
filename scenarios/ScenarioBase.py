from abc import ABC, abstractmethod
from typing import Optional, Callable

from config import config  # для доступа к ScenarioConfig


class ScenarioBase(ABC):
    def __init__(self, client, logger, config: config.ScenarioConfig):
        self.client = client
        self.logger = logger
        self.config = config

    @abstractmethod
    def run(self, progress_callback: Optional[Callable[[int, int], None]] = None) -> bool:
        pass