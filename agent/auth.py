"""
Authorization module for DeepSeek Chat login.
Handles auto-login and manual login fallback with persistent session.
"""
import time
from typing import Optional
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.remote.webelement import WebElement
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException

LOGIN_URL = "https://chat.deepseek.com/sign_in"
CHAT_URL = "https://chat.deepseek.com"

SELECTORS = {
    "email_input": [
        "input[placeholder*='телефон']",
        "input.ds-input__input[type='text']",
        "input[name='email']",
    ],
    "password_input": [
        "input[placeholder='Пароль']",
        "input.ds-input__input[type='password']",
    ],
    "login_button_text": "//span[text()='Войти']/ancestor::div[contains(@class, 'ds-button')]",
    "hcaptcha_iframe": "iframe[src*='hcaptcha']",
    "error_message": [
        "//div[contains(@class, 'error') or contains(@class, 'Error')]",
        "[role='alert']",
    ],
    "logged_in_indicator": [
        "textarea",
        "div.md-code-block",
        ".ds-markdown",
        "[data-testid='chat-input']",
    ],
}


class DeepSeekAuth:
    def __init__(self, driver, logger):
        self.driver = driver
        self.logger = logger

    def is_logged_in(self) -> bool:
        try:
            url = (self.driver.current_url or "").lower()
            if "sign_in" in url or "login" in url:
                return False
            if url == "https://chat.deepseek.com/" or url == "https://chat.deepseek.com":
                return False
            if "a/chat" in url:
                return True
            for selector in SELECTORS["logged_in_indicator"]:
                if self.driver.find_elements(By.CSS_SELECTOR, selector):
                    return True
        except:
            pass
        return False

    def is_login_page(self) -> bool:
        try:
            url = (self.driver.current_url or "").lower()
            if "sign_in" in url or "login" in url:
                return True
            if self.driver.find_elements(By.CSS_SELECTOR, "input[placeholder*='телефон']"):
                return True
        except:
            pass
        return False

    def ensure_logged_in(self, email: str = "", password: str = "", timeout: int = 120) -> bool:
        """
        Ensures user is logged in. Tries auto-login first, then falls back to manual.
        Returns True when logged in.
        """
        if self.is_logged_in():
            self.logger.log("Already logged in")
            return True

        if not self.is_login_page():
            self.logger.log("Navigating to login page...")
            self.driver.get(LOGIN_URL)
            time.sleep(3)

        # Try auto-login if credentials provided
        if email and password:
            self.logger.log(f"Attempting auto-login for {email}...")
            if self._auto_login(email, password):
                self.logger.log("Auto-login successful")
                return True
            self.logger.log("Auto-login failed", "WARNING")

        # Fallback: manual login
        return self._wait_manual_login(timeout)

    def _auto_login(self, email: str, password: str) -> bool:
        try:
            email_input = WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "input[placeholder*='телефон']"))
            )
            pass_input = self.driver.find_element(By.CSS_SELECTOR, "input[placeholder='Пароль']")
        except:
            self.logger.log("Login form fields not found", "ERROR")
            return False

        email_input.clear()
        email_input.send_keys(email)
        time.sleep(0.3)
        pass_input.clear()
        pass_input.send_keys(password)
        time.sleep(0.3)

        self.logger.log("Submitting login form via Enter...")
        pass_input.send_keys(Keys.RETURN)
        time.sleep(3)

        # Check for hCaptcha
        if self._is_hcaptcha_present():
            self.logger.log("hCaptcha detected. Please solve it in the browser window.", "WARNING")
            self.logger.log("Waiting up to 60s for captcha to be solved...")
            for _ in range(30):
                time.sleep(2)
                if not self.is_login_page():
                    return True
                if not self._is_hcaptcha_present():
                    break

        # Wait for redirect
        for _ in range(15):
            time.sleep(2)
            if not self.is_login_page():
                return True
            if self._has_error():
                err = self._get_error_text()
                self.logger.log(f"Login error: {err}", "ERROR")
                return False

        return not self.is_login_page()

    def _wait_manual_login(self, timeout: int = 120) -> bool:
        self.logger.log("=" * 50)
        self.logger.log("MANUAL LOGIN REQUIRED")
        self.logger.log("Please log in to DeepSeek in the browser window that is open.")
        self.logger.log(f"Waiting up to {timeout}s for manual login...")
        self.logger.log("=" * 50)

        start = time.time()
        last_log = 0
        while time.time() - start < timeout:
            time.sleep(2)
            if self.is_logged_in():
                elapsed = time.time() - start
                self.logger.log(f"Login detected after {elapsed:.0f}s")
                try:
                    self.logger.log(f"URL: {self.driver.current_url}")
                except:
                    pass
                time.sleep(2)
                return True
            remaining = int(timeout - (time.time() - start))
            if time.time() - last_log >= 10:
                self.logger.log(f"Still waiting for login... ({remaining}s remaining)")
                last_log = time.time()

        self.logger.log("Manual login timed out", "ERROR")
        return False

    def _is_hcaptcha_present(self) -> bool:
        try:
            iframes = self.driver.find_elements(By.CSS_SELECTOR, SELECTORS["hcaptcha_iframe"])
            return len(iframes) > 0
        except:
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
            except:
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
            except:
                continue
        return ""
