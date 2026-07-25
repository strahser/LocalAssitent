import os
import win32clipboard
import win32con


CF_HDROP = 15


class ClipboardManager:
    @staticmethod
    def get_text() -> str:
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
        try:
            win32clipboard.OpenClipboard()
            win32clipboard.EmptyClipboard()
            win32clipboard.SetClipboardText(text, win32con.CF_UNICODETEXT)
            win32clipboard.CloseClipboard()
            return True
        except Exception as e:
            print(f"Ошибка записи в буфер обмена: {e}")
            return False

    @staticmethod
    def has_files() -> bool:
        try:
            win32clipboard.OpenClipboard()
            result = win32clipboard.IsClipboardFormatAvailable(CF_HDROP)
            win32clipboard.CloseClipboard()
            return result
        except Exception as e:
            print(f"Ошибка проверки буфера обмена: {e}")
            return False

    @staticmethod
    def get_files() -> list:
        try:
            win32clipboard.OpenClipboard()
            if not win32clipboard.IsClipboardFormatAvailable(CF_HDROP):
                win32clipboard.CloseClipboard()
                return []
            data = win32clipboard.GetClipboardData(CF_HDROP)
            win32clipboard.CloseClipboard()
            if data:
                files = [f for f in data if os.path.exists(f)]
                return files
            return []
        except Exception as e:
            print(f"Ошибка чтения файлов из буфера обмена: {e}")
            return []