import os
from dataclasses import dataclass, field
from typing import Optional
from config.custom_selectors_config import SELECTORS
from config.pipeline_configs import PIPELINE_DEFINITIONS

USER_NAME = os.getlogin()
DEEPSEEK_URL = "https://chat.deepseek.com/a/chat/s/df0a17e8-235b-47e2-aeca-6a16d65734f0"
DEBUG_PORT = 9222
EDGE_USER_DATA_DIR = f"C:\\Users\\{USER_NAME}\\AppData\\Local\\Temp\\EdgeDebugProfile"

# Настройки логирования (оставлены как глобальные для обратной совместимости)
LOG_TO_HTML = False
LOG_TO_FILE = False
SAVE_RESPONSES = True
LOG_FILE = "assistant.log"
HTML_LOG_FILE = "log.html"
LOG_LEVEL_CONSOLE = "INFO"
LOG_LEVEL_FILE = "DEBUG"
LOG_AUTO_CLEAR = True

@dataclass
class ScenarioConfig:
    """Конфигурация сценария (code или text)."""
    prompt_template: str
    response_mode: str
    extractor_type: Optional[str] = None
    max_retries: int = 2
    auto_send_results: bool = True
    timeout_script: int = 60
    timeout_deepseek: int = 300
    create_new_chat: bool = False
    delay_between_questions: int = 0
    input_file: Optional[str] = None
    output_file: Optional[str] = None
    description: Optional[str] = None

# Конфигурация для сценария "code"
CODE_SCENARIO = ScenarioConfig(
    prompt_template=(
        "Напиши Python-скрипт, который создаёт резервную копию папки logs. "
        "ОТВЕТЬ ТОЛЬКО КОДОМ В БЛОКЕ ```python ... ```, БЕЗ ПОЯСНЕНИЙ И ЛИШНЕГО ТЕКСТА. "
        "Начинай ответ сразу с ```python. "
        "Если добавляешь пояснения – помещай их в комментарии внутри кода."
    ),
    response_mode="code",
    extractor_type="regex",
    max_retries=2,
    auto_send_results=True,
    timeout_script=60,
    timeout_deepseek=300,
    create_new_chat=False,
    delay_between_questions=0,
    description="Генерация и выполнение Python-кода"
)

# Конфигурация для сценария "text"
TEXT_SCENARIO = ScenarioConfig(
    prompt_template=(
        "Ответь на вопрос подробно и структурировано в формате markdown "
    ),
    response_mode="full",
    extractor_type="simple",
    max_retries=1,
    auto_send_results=False,
    timeout_script=30,
    timeout_deepseek=300,
    create_new_chat=False,
    delay_between_questions=5,
    input_file="tests/questions.txt",
    output_file="answers.md",
    description="Обработка вопросов из текстового файла"
)

# Словарь сценариев (значения – экземпляры ScenarioConfig)
SCENARIO_CONFIGS = {
    "code": CODE_SCENARIO,
    "text": TEXT_SCENARIO
}

# Активный сценарий (по умолчанию "text")
SCENARIO = "text"

@dataclass
class SeleniumConfig:
    """Конфигурация для подключения к браузеру и работы с Selenium."""
    debug_port: int = DEBUG_PORT
    edge_user_data_dir: str = EDGE_USER_DATA_DIR
    deepseek_url: str = DEEPSEEK_URL
    selenium_timeout: int = 300
    stable_timeout: int = 120
    stable_duration: int = 5
    check_interval: float = 20.0
    response_strategy: str = "panel_count"
    selectors: dict = field(default_factory=lambda: SELECTORS)

# Экземпляр конфигурации Selenium
SELENIUM_CONFIG = SeleniumConfig()