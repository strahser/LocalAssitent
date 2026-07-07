from enum import Enum

class ScenarioType(str, Enum):
    CODE = "code"
    TEXT = "text"

class ResponseStrategy(str, Enum):
    PANEL_COUNT = "panel_count"

class ExtractorType(str, Enum):
    REGEX = "regex"
    SIMPLE = "simple"
