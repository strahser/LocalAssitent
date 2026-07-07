from typing import Dict, Type
from core.interfaces import BrowserDriver, ResponseParser, CodeExecutor, PromptLoader, OutputWriter
from core.usecases.send_message import SendMessageUseCase
from core.usecases.new_chat import NewChatUseCase
from core.usecases.extract_code import ExtractCodeUseCase
from core.usecases.execute_code import ExecuteCodeUseCase
from core.usecases.load_prompts import LoadPromptsUseCase
from core.usecases.save_output import SaveOutputUseCase

class UseCaseFactory:
    @staticmethod
    def create_send_message(driver: BrowserDriver) -> SendMessageUseCase:
        return SendMessageUseCase(driver)

    @staticmethod
    def create_new_chat(driver: BrowserDriver) -> NewChatUseCase:
        return NewChatUseCase(driver)

    @staticmethod
    def create_extract_code(parser: ResponseParser) -> ExtractCodeUseCase:
        return ExtractCodeUseCase(parser)

    @staticmethod
    def create_execute_code(executor: CodeExecutor) -> ExecuteCodeUseCase:
        return ExecuteCodeUseCase(executor)

    @staticmethod
    def create_load_prompts(loader: PromptLoader) -> LoadPromptsUseCase:
        return LoadPromptsUseCase(loader)

    @staticmethod
    def create_save_output(writer: OutputWriter) -> SaveOutputUseCase:
        return SaveOutputUseCase(writer)
