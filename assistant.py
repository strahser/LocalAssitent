import sys
from config import config
from config.constants import ScenarioType
from config.pipeline_configs import PIPELINE_DEFINITIONS
from core.browser.deepseek_driver import DeepSeekBrowserDriver
from core.pipeline.factory import PipelineFactory
from core.utils.file_io import FilePromptLoader, FileOutputWriter
from logger.Logger import Logger

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
    driver = DeepSeekBrowserDriver(logger, selenium_config)

    # Определяем сценарий: аргумент командной строки или значение из config
    scenario_name = sys.argv[1] if len(sys.argv) > 1 else config.SCENARIO
    # Проверяем, что сценарий допустим
    if scenario_name not in [item.value for item in ScenarioType]:
        logger.error(f"Неизвестный сценарий: {scenario_name}. Допустимые: {[item.value for item in ScenarioType]}")
        sys.exit(1)

    logger.info(f"Запуск сценария: {scenario_name}")

    pipeline_config = PIPELINE_DEFINITIONS.get(scenario_name)
    if not pipeline_config:
        logger.error(f"Конфигурация для сценария '{scenario_name}' не найдена.")
        sys.exit(1)

    loader = FilePromptLoader()
    writer = FileOutputWriter()

    pipeline = PipelineFactory.create_from_config(
        pipeline_config,
        driver=driver,
        loader=loader,
        writer=writer
    )

    context = pipeline.run()
    success = not context.get("error")

    driver.close()
    logger.close()
    sys.exit(0 if success else 1)

if __name__ == "__main__":
    main()
