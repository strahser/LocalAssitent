# assistant.py
import sys
from config import config
from config.pipeline_configs import PIPELINE_DEFINITIONS
from core.browser.deepseek_driver import DeepSeekBrowserDriver
from core.processing.response_processor import ResponseProcessor
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

    scenario_config = config.SCENARIO_CONFIGS.get(config.SCENARIO)
    extractor_type = getattr(scenario_config, "extractor_type", "simple") if scenario_config else "simple"
    timeout_script = getattr(scenario_config, "timeout_script", 60) if scenario_config else 60
    processor = ResponseProcessor(extractor_type=extractor_type, script_timeout=timeout_script)

    scenario_name = config.SCENARIO
    pipeline_config = PIPELINE_DEFINITIONS.get(scenario_name)
    if not pipeline_config:
        logger.error(f"Неизвестный сценарий: {scenario_name}")
        sys.exit(1)

    loader = FilePromptLoader()
    writer = FileOutputWriter()

    pipeline = PipelineFactory.create_from_config(
        pipeline_config,
        driver=driver,
        parser=processor,
        executor=processor,
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
