# clipboard_manager.py
import win32clipboard
import win32con

class ClipboardManager:
    """Управление буфером обмена Windows через win32clipboard."""

    @staticmethod
    def get_text() -> str:
        """Получает текст из буфера обмена в Unicode."""
        try:
            win32clipboard.OpenClipboard()
            if win32clipboard.IsClipboardFormatAvailable(win32con.CF_UNICODETEXT):
                data = win32clipboard.GetClipboardData(win32con.CF_UNICODETEXT)
                win32clipboard.CloseClipboard()
                return data
            win32clipboard.CloseClipboard()
            return ""
        except Exception as e:
            print(f"Ошибка чтения буфера обмена: {e}")
            return ""

    @staticmethod
    def set_text(text: str) -> bool:
        """Устанавливает текст в буфер обмена."""
        try:
            win32clipboard.OpenClipboard()
            win32clipboard.EmptyClipboard()
            win32clipboard.SetClipboardText(text, win32con.CF_UNICODETEXT)
            win32clipboard.CloseClipboard()
            return True
        except Exception as e:
            print(f"Ошибка записи в буфер обмена: {e}")
            return False