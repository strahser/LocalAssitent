# config.py
import os
from selectors import SELECTORS

# ---------- ОБЩИЕ НАСТРОЙКИ ----------
USER_NAME = os.getlogin()
DEEPSEEK_URL = "https://chat.deepseek.com/a/chat/s/df0a17e8-235b-47e2-aeca-6a16d65734f0"
DEBUG_PORT = 9222
EDGE_USER_DATA_DIR = f"C:\\Users\\{USER_NAME}\\AppData\\Local\\Temp\\EdgeDebugProfile"

# ---------- НАСТРОЙКИ ЛОГИРОВАНИЯ ----------
LOG_TO_HTML = False
LOG_TO_FILE = True
SAVE_RESPONSES = True
LOG_FILE = "assistant.log"
HTML_LOG_FILE = "log.html"

# ---------- КОНФИГУРАЦИЯ СЦЕНАРИЕВ ----------
SCENARIO_CONFIGS = {
    "code": {
        "prompt_template": (
            "Напиши Python-скрипт, который создаёт резервную копию папки logs. "
            "ОТВЕТЬ ТОЛЬКО КОДОМ В БЛОКЕ ```python ... ```, БЕЗ ПОЯСНЕНИЙ И ЛИШНЕГО ТЕКСТА. "
            "Начинай ответ сразу с ```python. "
            "Если добавляешь пояснения – помещай их в комментарии внутри кода."
        ),
        "response_mode": "code",
        "extractor_type": "regex",
        "max_retries": 2,
        "auto_send_results": True,
        "timeout_script": 60,
        "timeout_deepseek": 180,
        "create_new_chat": False,
        "delay_between_questions": 0,
        "description": "Генерация и выполнение Python-кода"
    },
    "text": {
        "prompt_template": (
            "Ответь на вопрос подробно и структурированно в формате markdown "
        ),
        "response_mode": "full",
        "extractor_type": None,
        "max_retries": 1,
        "auto_send_results": False,
        "timeout_script": 30,
        "timeout_deepseek": 180,
        "input_file": "questions.txt",
        "output_file": "answers.md",
        "create_new_chat": False,
        "delay_between_questions": 5,
        "description": "Обработка вопросов из текстового файла"
    }
}

SCENARIO = "text"


# ---------- КЛАСС КОНФИГУРАЦИИ ДЛЯ SELENIUM ----------
class SeleniumConfig:
    """
    Конфигурация для Selenium-клиента.
    """
    def __init__(self,
                 debug_port=DEBUG_PORT,
                 edge_user_data_dir=EDGE_USER_DATA_DIR,
                 deepseek_url=DEEPSEEK_URL,
                 selenium_timeout=120,          # таймаут ожидания появления новой кнопки
                 stable_timeout=60,             # таймаут стабилизации
                 stable_duration=2,             # длительность стабильности
                 check_interval=1,            # интервал проверки
                 response_strategy="combined",  # стратегия определения готовности
                 selectors=None):
        self.debug_port = debug_port
        self.edge_user_data_dir = edge_user_data_dir
        self.deepseek_url = deepseek_url
        self.selenium_timeout = selenium_timeout
        self.stable_timeout = stable_timeout
        self.stable_duration = stable_duration
        self.check_interval = check_interval
        self.response_strategy = response_strategy
        self.selectors = selectors if selectors is not None else SELECTORS


# Создаём экземпляр конфигурации для использования по умолчанию
SELENIUM_CONFIG = SeleniumConfig()