"""
qwen — пакет автоматизации chat.qwen.ai.

Поток: файл drag-and-drop → мониторинг стадий по HTML → промпт → ответ.

Импорт пакета безопасен офлайн: selenium и agent.clipboard подключаются
лениво внутри методов.
"""
from qwen.client import QwenClient
from qwen.dnd_uploader import DragAndDropUploader
from qwen.html_monitor import HtmlChangeMonitor, HtmlSnapshot

__all__ = [
    "QwenClient",
    "DragAndDropUploader",
    "HtmlChangeMonitor",
    "HtmlSnapshot",
]
