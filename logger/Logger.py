# logger/Logger.py
import sys
from loguru import logger
from datetime import datetime
import os

# Настройка форматирования для консоли (цветной вывод)
CONSOLE_FORMAT = (
    "<green>{time:HH:mm:ss}</green> | "
    "<level>{level: <8}</level> | "
    "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - "
    "<level>{message}</level>"
)

class Logger:
    """
    Обёртка над loguru для обратной совместимости с существующим кодом.
    Использует loguru для консольного и файлового вывода.
    """
    def __init__(self, log_to_html=False, log_to_file=True, save_responses=False,
                 log_file="assistant.log", html_file="log.html",
                 console_level='INFO', file_level='DEBUG', auto_clear=True):
        self.save_responses = save_responses
        self.log_to_html = log_to_html
        self.html_file = html_file

        # Удаляем все стандартные обработчики
        logger.remove()

        # Консольный вывод с цветами
        logger.add(
            sys.stdout,
            format=CONSOLE_FORMAT,
            level=console_level.upper(),
            colorize=True,
            backtrace=False,
            diagnose=False
        )

        # Файловый вывод (без цветов)
        if log_to_file:
            mode = 'w' if auto_clear else 'a'
            logger.add(
                log_file,
                format="{time:HH:mm:ss} | {level: <8} | {message}",
                level=file_level.upper(),
                rotation="10 MB",
                retention="7 days",
                mode=mode,
                encoding='utf-8'
            )

        # HTML-логирование (сохраняем старую функциональность)
        if log_to_html:
            # Очищаем старый HTML-файл
            if auto_clear:
                with open(html_file, 'w', encoding='utf-8') as f:
                    f.write("<html><head><meta charset='utf-8'></head><body>\n")
            self._html_file = html_file

        # Запоминаем уровень консоли для метода log()
        self._console_level = console_level.upper()

    def _log(self, message, level="INFO", color=None):
        """
        Универсальный метод логирования с уровнем.
        """
        level = level.upper()
        # Преобразуем SUCCESS в INFO для loguru, т.к. SUCCESS есть
        if level == "SUCCESS":
            logger.success(message)
        else:
            getattr(logger, level.lower(), logger.info)(message)

        # Дополнительно сохраняем в HTML, если включено
        if self.log_to_html:
            color_map = {"INFO": "blue", "WARNING": "orange", "ERROR": "red",
                         "SUCCESS": "green", "DEBUG": "gray"}
            color = color_map.get(level, "black")
            timestamp = datetime.now().strftime("%H:%M:%S")
            text = f"[{timestamp}] [{level}] {message}"
            with open(self.html_file, 'a', encoding='utf-8') as f:
                f.write(f'<div style="color:{color}; font-family:monospace;">{text}</div>\n')

    def debug(self, msg): self._log(msg, "DEBUG")
    def info(self, msg): self._log(msg, "INFO")
    def success(self, msg): self._log(msg, "SUCCESS")
    def warning(self, msg): self._log(msg, "WARNING")
    def error(self, msg): self._log(msg, "ERROR")

    def log(self, message, level="INFO"):
        self._log(message, level)

    def log_response(self, full_text, code_text=None):
        if not self.save_responses:
            return
        with open("last_response.txt", "w", encoding='utf-8') as f:
            f.write(full_text)
        if code_text:
            with open("last_code.txt", "w", encoding='utf-8') as f:
                f.write(code_text)

    def close(self):
        if self.log_to_html:
            with open(self.html_file, 'a', encoding='utf-8') as f:
                f.write("</body></html>\n")
        # loguru не требует явного закрытия