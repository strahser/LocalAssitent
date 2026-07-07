import os
from dataclasses import dataclass, field
from config.custom_selectors_config import SELECTORS
from config.constants import ScenarioType, ResponseStrategy, ExtractorType

USER_NAME = os.getlogin()
DEEPSEEK_URL = "https://chat.deepseek.com/a/chat/s/df0a17e8-235b-47e2-aeca-6a16d65734f0"
DEBUG_PORT = 9222
EDGE_USER_DATA_DIR = f"C:\\Users\\{USER_NAME}\\AppData\\Local\\Temp\\EdgeDebugProfile"

# Настройки логирования
LOG_TO_HTML = False
LOG_TO_FILE = False
SAVE_RESPONSES = True
LOG_FILE = "assistant.log"
HTML_LOG_FILE = "log.html"
LOG_LEVEL_CONSOLE = "INFO"
LOG_LEVEL_FILE = "DEBUG"
LOG_AUTO_CLEAR = True

@dataclass
class SeleniumConfig:
    debug_port: int = DEBUG_PORT
    edge_user_data_dir: str = EDGE_USER_DATA_DIR
    deepseek_url: str = DEEPSEEK_URL
    selenium_timeout: int = 300
    stable_timeout: int = 120
    stable_duration: int = 5
    check_interval: float = 20.0
    response_strategy: str = ResponseStrategy.PANEL_COUNT.value
    selectors: dict = field(default_factory=lambda: SELECTORS)

SELENIUM_CONFIG = SeleniumConfig()

# Активный сценарий (можно переопределить через аргумент командной строки)
SCENARIO = ScenarioType.TEXT.value
