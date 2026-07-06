import sys
from config import config
from core.client import DeepSeekClient
from logger.Logger import Logger
from scenarios.scenarios import ScenarioFactory

def main():
    logger = Logger(
        log_to_html=config.LOG_TO_HTML,
        log_to_file=config.LOG_TO_FILE,
        save_responses=config.SAVE_RESPONSES,
        log_file=config.LOG_FILE,
        html_file=config.HTML_LOG_FILE,
        console_level=config.LOG_LEVEL_CONSOLE,
        file_level=config.LOG_LEVEL_FILE,
        auto_clear=config.LOG_AUTO_CLEAR
    )

    scenario_cfg = config.SCENARIO_CONFIGS.get(config.SCENARIO, {})
    client = DeepSeekClient(logger, config.SELENIUM_CONFIG)

    scenario = ScenarioFactory.get_scenario(config.SCENARIO, logger)
    scenario.set_client(client)

    success = scenario.run()
    client.close()
    logger.close()
    sys.exit(0 if success else 1)

if __name__ == "__main__":
    main()
