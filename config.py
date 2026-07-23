import os
import argparse
from detection.selectors import SELECTORS

USER_NAME = os.getlogin()
DEEPSEEK_URL = "https://chat.deepseek.com"
DEBUG_PORT = 9222
EDGE_USER_DATA_DIR = os.path.expandvars(r"%LOCALAPPDATA%\EdgeDebugProfile")

LOG_TO_HTML = False
LOG_TO_FILE = True
SAVE_RESPONSES = True
LOG_FILE = "assistant.log"
HTML_LOG_FILE = "log.html"

SCENARIO_CONFIGS = {
    "code": {
        "prompt_template": (
            "Ты — агент для рефакторинга и разработки Python-проекта. "
            "Это итеративный цикл: ты решаешь задачу шаг за шагом, "
            "я выполняю твои команды и возвращаю результаты.\n\n"
            "## Доступные инструменты\n"
            "Вызывай их в блоках ```tool:<имя> ...```:\n"
            "  read <path> [offset] [limit] — прочитать файл\n"
            "  grep <pattern> [root] [include] — поиск по содержимому\n"
            "  glob <pattern> [root] — поиск файлов по маске\n"
            "  ls <path> [depth] — список директории\n"
            "  write <path> [--force] — записать файл (ты даёшь путь, я пишу содержимое из блока)\n"
            "  exec <code> — выполнить Python код\n\n"
            "## Протокол работы\n"
            "1. Анализируй задачу. Если нужно изучить код — используй read/grep/glob/ls.\n"
            "2. Предложи план. После утверждения приступай к изменениям.\n"
            "3. Для изменений используй write (создание/обновление файлов) или exec (временные скрипты).\n"
            "4. После каждого шага я пришлю результат выполнения. Анализируй и продолжай.\n"
            "5. Когда задача решена полностью — напиши в конце: TASK_COMPLETE: <описание>\n\n"
            "## Правила\n"
            "- Пиши код в ```python ... ```, если его нужно выполнить.\n"
            "- Используй ```tool:read ...``` для чтения существующих файлов.\n"
            "- Используй ```tool:write ...``` для создания новых файлов (содержимое после пути).\n"
            "- Используй ```tool:grep ...``` для поиска по проекту.\n"
            "- Используй ```tool:ls ...``` для навигации.\n"
            "- Каждый шаг делай маленьким и проверяемым.\n"
            "- Если что-то пошло не так — проанализируй ошибку и исправь.\n"
            "- После TASK_COMPLETE работа прекращается."
        ),
        "response_mode": "code",
        "extractor_type": "regex",
        "max_iterations": 10,
        "auto_send_results": True,
        "timeout_script": 60,
        "timeout_deepseek": 180,
        "create_new_chat": False,
        "delay_between_questions": 0,
        "description": "Итеративная генерация и выполнение Python-кода"
    },
    "text": {
        "prompt_template": (
            "Ответь на вопрос в формате:\n"
            "**Вопрос:** (повтори вопрос)\n"
            "**Ответ:** (твой подробный ответ)\n\n"
            "Оформи ответ структурированно, используя Markdown:\n"
            "- **Заголовки**: ## для основных разделов, ### для подразделов.\n"
            "- **Списки**: маркированные (-) и нумерованные (1., 2., ...).\n"
            "- **Код**: примеры кода в блоках ```python ... ```.\n"
            "- **Таблицы**: если уместно, через | и ---.\n"
            "- **Выделение**: **жирным**, *курсивом*.\n"
            "Не добавляй ничего лишнего — только вопрос и ответ."
        ),
        "response_mode": "full",
        "extractor_type": None,
        "max_iterations": 1,
        "auto_send_results": False,
        "timeout_script": 30,
        "timeout_deepseek": 180,
        "input_file": "questions.txt",
        "output_file": "answers.md",
        "create_new_chat": False,
        "delay_between_questions": 5,
        "description": "Ответы на вопросы (Q&A формат)"
    }
}


def parse_args():
    parser = argparse.ArgumentParser(
        description="Local Assistant — агент для работы с DeepSeek Chat",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Примеры:
  python assistant.py --scenario code --prompt "Напиши скрипт для бэкапа"
  python assistant.py --scenario text --input questions.txt --output answers.md
  python assistant.py --scenario code --max-iterations 5
        """
    )
    parser.add_argument(
        "--scenario", "-s",
        choices=list(SCENARIO_CONFIGS.keys()),
        default=None,
        help="Сценарий запуска (по умолчанию: code)"
    )
    parser.add_argument(
        "--prompt", "-p",
        help="Переопределить промпт для сценария code"
    )
    parser.add_argument(
        "--input", "-i",
        help="Входной файл для сценария text"
    )
    parser.add_argument(
        "--output", "-o",
        help="Выходной файл для сценария text"
    )
    parser.add_argument(
        "--max-iterations", "-n",
        type=int,
        default=None,
        help="Максимальное количество итераций для code-сценария"
    )
    parser.add_argument(
        "--no-auto-send",
        action="store_true",
        help="Отключить автоматическую отправку результатов обратно в чат"
    )
    parser.add_argument(
        "--debug-port",
        type=int,
        default=DEBUG_PORT,
        help=f"Порт отладки Edge (по умолчанию: {DEBUG_PORT})"
    )
    parser.add_argument(
        "--new-chat",
        action="store_true",
        help="Создать новый чат перед началом работы"
    )
    parser.add_argument(
        "--files",
        nargs="*",
        help="Файлы для прикрепления к сообщению"
    )
    parser.add_argument(
        "--email",
        default=None,
        help="Email для входа в DeepSeek (или DEEPSEEK_EMAIL env)"
    )
    parser.add_argument(
        "--password",
        default=None,
        help="Пароль для входа в DeepSeek (или DEEPSEEK_PASSWORD env)"
    )
    parser.add_argument(
        "--list-scenarios",
        action="store_true",
        help="Показать доступные сценарии и выйти"
    )
    return parser.parse_args()


def build_config(cli_args=None):
    args = cli_args if cli_args is not None else parse_args()

    if args.list_scenarios:
        print("Доступные сценарии:")
        for name, cfg in SCENARIO_CONFIGS.items():
            print(f"  {name}: {cfg.get('description', '')}")
        raise SystemExit(0)

    scenario_name = args.scenario or os.environ.get("SCENARIO", "code")
    if scenario_name not in SCENARIO_CONFIGS:
        print(f"Ошибка: неизвестный сценарий '{scenario_name}'")
        print(f"Доступны: {', '.join(SCENARIO_CONFIGS.keys())}")
        raise SystemExit(1)

    cfg = dict(SCENARIO_CONFIGS[scenario_name])
    if args.prompt:
        cfg["prompt_template"] = args.prompt
    if args.input:
        cfg["input_file"] = args.input
    if args.output:
        cfg["output_file"] = args.output
    if args.max_iterations is not None:
        cfg["max_iterations"] = args.max_iterations
    if args.no_auto_send:
        cfg["auto_send_results"] = False
    if args.files:
        cfg["files"] = args.files
    cfg["create_new_chat"] = cfg.get("create_new_chat", False) or args.new_chat
    cfg["debug_port"] = args.debug_port
    cfg["email"] = args.email or os.environ.get("DEEPSEEK_EMAIL", "")
    cfg["password"] = args.password or os.environ.get("DEEPSEEK_PASSWORD", "")

    return scenario_name, cfg, args


class SeleniumConfig:
    def __init__(self,
                 debug_port=DEBUG_PORT,
                 edge_user_data_dir=EDGE_USER_DATA_DIR,
                 deepseek_url=DEEPSEEK_URL,
                 selenium_timeout=300,
                 stable_timeout=180,
                 stable_duration=3,
                 check_interval=1,
                 response_strategy="combined",
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


SELENIUM_CONFIG = SeleniumConfig()
