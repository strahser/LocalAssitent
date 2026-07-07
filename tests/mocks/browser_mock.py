from typing import List, Dict, Optional
from core.interfaces import BrowserDriver

class MockBrowserDriver(BrowserDriver):
    """
    Мок для BrowserDriver, который возвращает заранее заданные ответы.
    """
    def __init__(self, response_map: Dict[str, str] = None, default_response: str = ""):
        self.response_map = response_map or {}
        self.default_response = default_response
        self.sent_messages: List[str] = []

    def send_message(self, prompt: str) -> Optional[str]:
        self.sent_messages.append(prompt)
        for key, response in self.response_map.items():
            if key in prompt:
                return response
        return self.default_response

    def new_chat(self) -> None:
        pass

    def attach_file(self, file_path: str) -> None:
        pass

    def close(self) -> None:
        pass
