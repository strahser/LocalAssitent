import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

import config
from agent.deepseek_client import DeepSeekClient
from agent.QwenClient import QwenClient
from logger import Logger
from scenarios import ScenarioFactory

# Загружаем .env (QWEN_EMAIL/QWEN_PASSWORD и др.), если он есть
try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env"))
except Exception:
    pass


def build_client(logger, scenario_cfg):
    """Фабрика клиентов по провайдеру (--provider: deepseek | qwen)."""
    provider = scenario_cfg.get("provider", "deepseek")
    timeout = scenario_cfg.get("timeout_deepseek", 180)
    email = scenario_cfg.get("email", "")
    password = scenario_cfg.get("password", "")

    if provider == "qwen":
        model = scenario_cfg.get("model", config.DEFAULT_QWEN_MODEL)
        return QwenClient(
            logger,
            timeout=timeout,
            email=email,
            password=password,
            model=model,
        )

    return DeepSeekClient(
        logger,
        timeout=timeout,
        email=email,
        password=password,
    )


def main():
    scenario_name, scenario_cfg, cli_args = config.build_config()

    logger = Logger(
        log_to_html=config.LOG_TO_HTML,
        log_to_file=config.LOG_TO_FILE,
        save_responses=config.SAVE_RESPONSES,
        log_file=config.LOG_FILE,
        html_file=config.HTML_LOG_FILE
    )

    logger.log(f"Сценарий: {scenario_name}")
    logger.log(f"Описание: {scenario_cfg.get('description', '')}")
    provider = scenario_cfg.get("provider", "deepseek")
    logger.log(f"Провайдер: {provider}")
    if scenario_cfg.get("model"):
        logger.log(f"Модель: {scenario_cfg.get('model')}")

    scenario = ScenarioFactory.get_scenario(scenario_name, logger)
    scenario.set_config(scenario_cfg)

    if scenario_name != "merge":
        logger.log(f"Макс. итераций: {scenario_cfg.get('max_iterations', 1)}")
        client = build_client(logger, scenario_cfg)
        scenario.set_client(client)

    success = scenario.run()
    logger.close()
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
