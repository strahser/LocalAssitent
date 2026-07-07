from core.interfaces import BrowserDriver

class NewChatUseCase:
    def __init__(self, driver: BrowserDriver):
        self.driver = driver

    def execute(self) -> None:
        self.driver.new_chat()
