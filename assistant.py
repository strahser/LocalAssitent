# assistant.py
import sys
from config import config
from core.client import DeepSeekClient
from logger.Logger import Logger
from scenarios.ScenarioFactory import ScenarioFactory

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

    selenium_config = config.SELENIUM_CONFIG
    client = DeepSeekClient(logger, selenium_config)

    scenario_name = config.SCENARIO
    scenario_config = config.SCENARIO_CONFIGS[scenario_name]
    scenario = ScenarioFactory.get_scenario(scenario_name, client, logger, scenario_config)

    # UI – прогресс‑бар для текстового сценария
    if scenario_name == "text":
        try:
            with open(scenario_config.input_file, 'r', encoding='utf-8') as f:
                questions = [line.strip() for line in f if line.strip()]
            total = len(questions)
        except (FileNotFoundError, TypeError):
            total = 0

        if total > 0:
            from tqdm import tqdm
            with tqdm(total=total, desc="📊 Общий прогресс", unit="вопрос",
                      position=0, leave=True, colour='green') as pbar:
                def progress_callback(current, total):
                    pbar.update(1)
                success = scenario.run(progress_callback=progress_callback)
        else:
            success = scenario.run()
    else:
        success = scenario.run()

    client.close()
    logger.close()
    sys.exit(0 if success else 1)

if __name__ == "__main__":
    main()
