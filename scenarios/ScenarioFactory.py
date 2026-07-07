# scenarios/ScenarioFactory.py

from config import config  # для доступа к ScenarioConfig
from scenarios.CodeScenario import CodeScenario
from scenarios.TextScenario import TextScenario


class ScenarioFactory:
    @staticmethod
    def get_scenario(name: str, client, logger, config: config.ScenarioConfig):
        if name == "code":
            return CodeScenario(client, logger, config)
        elif name == "text":
            return TextScenario(client, logger, config)
        else:
            raise ValueError(f"Неизвестный сценарий: {name}")
