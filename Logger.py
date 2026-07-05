import time
from datetime import datetime

# ------------------- Логгер -------------------
class Logger:
    def __init__(self, log_to_html=False, log_to_file=False, save_responses=False):
        self.log_to_html = log_to_html
        self.log_to_file = log_to_file
        self.save_responses = save_responses
        self.html_file = "log.html"
        self.log_file = "assistant.log"
        if self.log_to_html:
            # Очищаем старый HTML при запуске
            with open(self.html_file, "w", encoding="utf-8") as f:
                f.write("<html><body>\n")
        if self.log_to_file:
            with open(self.log_file, "a", encoding="utf-8") as f:
                f.write(f"\n--- {datetime.now().isoformat()} ---\n")

    def log(self, message, level="INFO"):
        timestamp = datetime.now().strftime("%H:%M:%S")
        text = f"[{timestamp}] [{level}] {message}"
        print(text)  # всегда в консоль

        if self.log_to_file:
            with open(self.log_file, "a", encoding="utf-8") as f:
                f.write(text + "\n")

        if self.log_to_html:
            color = {"INFO": "blue", "WARNING": "orange", "ERROR": "red", "SUCCESS": "green"}.get(level, "black")
            with open(self.html_file, "a", encoding="utf-8") as f:
                f.write(f'<div style="color:{color}; font-family:monospace;">{text}</div>\n')

    def log_response(self, full_text, code_text=None):
        if not self.save_responses:
            return
        with open("last_response.txt", "w", encoding="utf-8") as f:
            f.write(full_text)
        if code_text:
            with open("last_code.txt", "w", encoding="utf-8") as f:
                f.write(code_text)

    def close(self):
        if self.log_to_html:
            with open(self.html_file, "a", encoding="utf-8") as f:
                f.write("</body></html>\n")