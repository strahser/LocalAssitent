import sys
import config
from DeepSeekClient import DeepSeekClient
from Logger import Logger
from scenarios import ScenarioFactory

def main():
    # Настройки логирования берутся из config
    logger = Logger(
        log_to_html=config.LOG_TO_HTML,
        log_to_file=config.LOG_TO_FILE,
        save_responses=config.SAVE_RESPONSES,
        log_file=config.LOG_FILE,
        html_file=config.HTML_LOG_FILE
    )

    # Получаем параметры выбранного сценария
    scenario_cfg = config.SCENARIO_CONFIGS.get(config.SCENARIO, {})
    timeout = scenario_cfg.get("timeout_deepseek", 180)

    client = DeepSeekClient(logger, timeout=timeout)
    scenario = ScenarioFactory.get_scenario(config.SCENARIO, logger)
    scenario.set_client(client)

    success = scenario.run()
    logger.close()
    sys.exit(0 if success else 1)

if __name__ == "__main__":
    main()