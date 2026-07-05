import os

# ---------- ОБЩИЕ НАСТРОЙКИ ----------
USER_NAME = os.getlogin()
DEEPSEEK_URL = "https://chat.deepseek.com/a/chat/s/b4c4c8b6-3288-4279-b6d6-345fd18d2e67"
DEBUG_PORT = 9222
EDGE_USER_DATA_DIR = f"C:\\Users\\{USER_NAME}\\AppData\\Local\\Temp\\EdgeDebugProfile"

SEND_MESSAGE_SCRIPT = "send_message.py"

STREAM_STABLE_TIMEOUT = 30
STREAM_STABLE_DURATION = 2.0
STREAM_CHECK_INTERVAL = 0.5

# ---------- НАСТРОЙКИ ЛОГИРОВАНИЯ (теперь только здесь) ----------
LOG_TO_HTML = False          # Включить HTML-логи
LOG_TO_FILE = True          # Включить текстовый лог-файл
SAVE_RESPONSES = True       # Сохранять последний ответ и код в отдельные файлы
LOG_FILE = "assistant.log"   # Имя файла для текстового лога
HTML_LOG_FILE = "log.html"   # Имя файла для HTML-лога

# ---------- КОНФИГУРАЦИЯ СЦЕНАРИЕВ ----------
# В будущем эти настройки можно загружать из JSON-файла
SCENARIO_CONFIGS = {
    "code": {
        "prompt_template": (
            "Напиши Python-скрипт, который создаёт резервную копию папки logs. "
            "ОТВЕТЬ ТОЛЬКО КОДОМ В БЛОКЕ ```python ... ```, БЕЗ ПОЯСНЕНИЙ И ЛИШНЕГО ТЕКСТА. "
            "Начинай ответ сразу с ```python. "
            "Если добавляешь пояснения – помещай их в комментарии внутри кода."
        ),
        "response_mode": "code",          # извлекать только код
        "extractor_type": "regex",
        "max_retries": 2,
        "auto_send_results": True,
        "timeout_script": 60,
        "timeout_deepseek": 180,
        "create_new_chat": False,         # не используется в code
        "delay_between_questions": 0,
        "description": "Генерация и выполнение Python-кода"
    },
    "text": {
        "prompt_template": (
            "Ответь на вопрос максимально кратко в формате markdown "

        ),
        "response_mode": "full",
        "extractor_type": None,
        "max_retries": 1,
        "auto_send_results": False,
        "timeout_script": 30,
        "timeout_deepseek": 180,
        "input_file": "questions.txt",
        "output_file": "answers.txt",
        "create_new_chat": False,  # оставляем False для одного чата
        "delay_between_questions": 5,  # пауза между отправками
        "description": "Обработка вопросов из текстового файла"
    }
}

# Выбор сценария по умолчанию
SCENARIO = "text"   # или "code"