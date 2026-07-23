import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    sys.stdout.reconfigure(encoding="utf-8")
except:
    pass

import config
from agent.DeepSeekClient import DeepSeekClient
from Logger import Logger
from scenarios import ScenarioFactory


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
    logger.log(f"Макс. итераций: {scenario_cfg.get('max_iterations', 1)}")

    timeout = scenario_cfg.get("timeout_deepseek", 180)
    client = DeepSeekClient(
        logger,
        timeout=timeout,
        email=scenario_cfg.get("email", ""),
        password=scenario_cfg.get("password", "")
    )

    scenario = ScenarioFactory.get_scenario(scenario_name, logger)
    scenario.set_client(client)
    scenario.set_config(scenario_cfg)

    success = scenario.run()
    logger.close()
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
