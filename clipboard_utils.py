# clipboard_utils.py
import win32clipboard
import win32con

def get_clipboard_text() -> str:
    """
    Получает текст из буфера обмена Windows.
    Использует win32clipboard для надёжного чтения Unicode.
    Возвращает строку или пустую строку при ошибке.
    """
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


def set_clipboard_text(text: str) -> bool:
    """
    Устанавливает текст в буфер обмена Windows.
    Возвращает True при успехе.
    """
    try:
        win32clipboard.OpenClipboard()
        win32clipboard.EmptyClipboard()
        win32clipboard.SetClipboardText(text, win32con.CF_UNICODETEXT)
        win32clipboard.CloseClipboard()
        return True
    except Exception as e:
        print(f"Ошибка записи в буфер обмена: {e}")
        return False