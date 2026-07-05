import os

USER_NAME = os.getlogin()
DEEPSEEK_URL = "https://chat.deepseek.com/a/chat/s/b4c4c8b6-3288-4279-b6d6-345fd18d2e67"
DEBUG_PORT = 9222
EDGE_USER_DATA_DIR = f"C:\\Users\\{USER_NAME}\\AppData\\Local\\Temp\\EdgeDebugProfile"

TIMEOUT_DEEPSEEK = 180
TIMEOUT_SCRIPT = 60
SEND_MESSAGE_SCRIPT = "send_message.py"

CHAT_MODE = False
AUTO_SEND_RESULTS = True

MAX_RETRIES = 2
RETRY_ON_TRUNCATION = True

STREAM_STABLE_TIMEOUT = 30
STREAM_STABLE_DURATION = 2.0
STREAM_CHECK_INTERVAL = 0.5

# ---------- НАСТРОЙКИ ПРОМПТА ----------
USER_PROMPT = "Напиши Python-скрипт, который создаёт резервную копию папки logs "
BASE_PROMPT = (
    USER_PROMPT+"ОТВЕТЬ ТОЛЬКО КОДОМ В БЛОКЕ ```python ... ```, БЕЗ ПОЯСНЕНИЙ И ЛИШНЕГО ТЕКСТА. "
    "Начинай ответ сразу с ```python. "
    "Если добавляешь пояснения – помещай их в комментарии внутри кода."
)


# ---------- ОПЦИИ ЛОГИРОВАНИЯ ----------
LOG_TO_HTML = False
LOG_TO_FILE = False
SAVE_RESPONSES = False