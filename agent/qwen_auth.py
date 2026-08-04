"""
qwen_auth.py – авторизация в Qwen Chat (chat.qwen.ai).

Повторяет паттерн agent/auth.py (DeepSeekAuth): auto-login + ручной фолбэк.
Селекторы формы входа Qwen частично совпадают с DeepSeek (телефон/email + пароль),
поэтому используются общие фолбэки. hCaptcha — общий случай.
"""
import time
from typing import Optional
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

LOGIN_URL = "https://chat.qwen.ai/"
CHAT_URL = "https://chat.qwen.ai/"

SELECTORS = {
    "email_input": [
        "input[placeholder*='телефон']",
        "input[placeholder*='phone']",
        "input[name='email']",
        "input[type='text']",
    ],
    "password_input": [
        "input[placeholder='Пароль']",
        "input[placeholder='Password']",
        "input[type='password']",
    ],
    "login_button_text": "//button[contains(@class, 'ant-btn-primary')]",
    "hcaptcha_iframe": "iframe[src*='hcaptcha']",
    "error_message": [
        "//div[contains(@class, 'error') or contains(@class, 'Error')]",
        "[role='alert']",
    ],
    "logged_in_indicator": [
        "textarea",
        "div[contenteditable='true']",
        "div[class*='model-selector']",
    ],
}


class QwenAuth:
    def __init__(self, driver, logger):
        self.driver = driver
        self.logger = logger

    def is_logged_in(self) -> bool:
        try:
            url = (self.driver.current_url or "").lower()
            if "sign_in" in url or "login" in url:
                return False
            for selector in SELECTORS["logged_in_indicator"]:
                if self.driver.find_elements(By.CSS_SELECTOR, selector):
                    return True
        except Exception:
            pass
        return False

    def is_login_page(self) -> bool:
        try:
            url = (self.driver.current_url or "").lower()
            if "sign_in" in url or "login" in url:
                return True
            if self.driver.find_elements(By.CSS_SELECTOR, "input[placeholder*='телефон']"):
                return True
            if self.driver.find_elements(By.CSS_SELECTOR, "input[placeholder*='phone']"):
                return True
        except Exception:
            pass
        return False

    def ensure_logged_in(self, email: str = "", password: str = "", timeout: int = 120) -> bool:
        if self.is_logged_in():
            self.logger.log("Qwen: already logged in")
            return True

        # Edge может восстановить последнюю вкладку (напр. chat.deepseek.com),
        # поэтому всегда явно открываем страницу входа Qwen, если URL — не Qwen.
        try:
            url = (self.driver.current_url or "").lower()
            if "chat.qwen.ai" not in url:
                self.logger.log("Qwen: navigating to login page...")
                self.driver.get(LOGIN_URL)
                time.sleep(3)
        except Exception:
            self.driver.get(LOGIN_URL)
            time.sleep(3)

        if email and password:
            self.logger.log(f"Qwen: attempting auto-login for {email}...")
            if self._auto_login(email, password):
                self.logger.log("Qwen: auto-login successful")
                return True
            self.logger.log("Qwen: auto-login failed", "WARNING")

        return self._wait_manual_login(timeout)

    def _auto_login(self, email: str, password: str) -> bool:
        try:
            email_input = WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "input[placeholder*='телефон'], input[placeholder*='phone'], input[type='text']"))
            )
            pass_input = self.driver.find_element(By.CSS_SELECTOR, "input[type='password']")
        except Exception:
            self.logger.log("Qwen: login form fields not found", "ERROR")
            return False

        email_input.clear()
        email_input.send_keys(email)
        time.sleep(0.3)
        pass_input.clear()
        pass_input.send_keys(password)
        time.sleep(0.3)

        self.logger.log("Qwen: submitting login form via Enter...")
        pass_input.send_keys(Keys.RETURN)
        time.sleep(3)

        if self._is_hcaptcha_present():
            self.logger.log("Qwen: hCaptcha detected. Please solve it in the browser window.", "WARNING")
            for _ in range(30):
                time.sleep(2)
                if not self.is_login_page():
                    return True
                if not self._is_hcaptcha_present():
                    break

        for _ in range(15):
            time.sleep(2)
            if not self.is_login_page():
                return True
            if self._has_error():
                self.logger.log(f"Qwen: login error: {self._get_error_text()}", "ERROR")
                return False

        return not self.is_login_page()

    def _wait_manual_login(self, timeout: int = 120) -> bool:
        self.logger.log("=" * 50)
        self.logger.log("QWEN: MANUAL LOGIN REQUIRED")
        self.logger.log("Please log in to Qwen (chat.qwen.ai) in the browser window that is open.")
        self.logger.log(f"Waiting up to {timeout}s for manual login...")
        self.logger.log("=" * 50)

        start = time.time()
        last_log = 0
        while time.time() - start < timeout:
            time.sleep(2)
            if self.is_logged_in():
                self.logger.log(f"Qwen: login detected after {time.time() - start:.0f}s")
                time.sleep(2)
                return True
            remaining = int(timeout - (time.time() - start))
            if time.time() - last_log >= 10:
                self.logger.log(f"Qwen: still waiting for login... ({remaining}s remaining)")
                last_log = time.time()

        self.logger.log("Qwen: manual login timed out", "ERROR")
        return False

    def _is_hcaptcha_present(self) -> bool:
        try:
            return len(self.driver.find_elements(By.CSS_SELECTOR, SELECTORS["hcaptcha_iframe"])) > 0
        except Exception:
            return False

    def _has_error(self) -> bool:
        for selector in SELECTORS["error_message"]:
            try:
                if selector.startswith("//"):
                    elements = self.driver.find_elements(By.XPATH, selector)
                else:
                    elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                for e in elements:
                    if e.is_displayed() and e.text.strip():
                        return True
            except Exception:
                continue
        return False

    def _get_error_text(self) -> str:
        for selector in SELECTORS["error_message"]:
            try:
                if selector.startswith("//"):
                    elements = self.driver.find_elements(By.XPATH, selector)
                else:
                    elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                for e in elements:
                    if e.is_displayed() and e.text.strip():
                        return e.text.strip()[:300]
            except Exception:
                continue
        return ""
