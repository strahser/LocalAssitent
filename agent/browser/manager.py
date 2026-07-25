"""
BrowserManager - отвечает за запуск и управление жизненным циклом браузера.
"""
import os
import socket
import subprocess
import time
from typing import Optional

from selenium import webdriver
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.common.by import By
from selenium.webdriver.edge.options import Options
from selenium.webdriver.remote.webdriver import WebDriver
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait


class BrowserManager:
    def __init__(self, logger, config):
        self.logger = logger
        self.config = config
        self.driver: Optional[WebDriver] = None

    def start(self) -> WebDriver:
        self._start_edge_debug_mode()
        self._connect()
        return self.driver

    def _find_edge_exe(self) -> str:
        candidates = [
            "C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe",
            "C:\\Program Files\\Microsoft\\Edge\\Application\\msedge.exe",
        ]
        for p in candidates:
            if os.path.exists(p):
                return p
        return "msedge.exe"

    def _check_port(self, port: int) -> bool:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.connect(("127.0.0.1", port))
                return True
            except Exception:
                return False

    def _start_edge_debug_mode(self):
        port = self.config.debug_port

        if self._check_port(port):
            self.logger.log(f"Edge уже запущен на порту {port}.")
            return

        user_dir = self.config.edge_user_data_dir
        edge_exe = self._find_edge_exe()

        os.makedirs(user_dir, exist_ok=True)

        cmd = [
            edge_exe,
            f"--user-data-dir={user_dir}",
            f"--remote-debugging-port={port}",
            "--no-first-run",
            "--no-default-browser-check",
            "--disable-sync",
            "--disable-search-engine-choice-screen",
            self.config.deepseek_url,
        ]
        self.logger.log(f"🚀 Запуск Edge (порт {port})...")
        subprocess.Popen(cmd, shell=False)

        for _ in range(20):
            time.sleep(1)
            if self._check_port(port):
                self.logger.log(f"Edge запущен на порту {port}.")
                return

        self.logger.log("❌ Edge не запустился за 20 секунд.", "ERROR")
        raise RuntimeError("Edge не запустился за 20 секунд")

    def _connect(self):
        try:
            options = Options()
            options.add_experimental_option("debuggerAddress", f"127.0.0.1:{self.config.debug_port}")
            options.page_load_strategy = "eager"
            self.driver = webdriver.Edge(options=options)
        except Exception as e:
            self.logger.log(f"Не удалось подключиться к Edge: {e}", "ERROR")
            raise

        self.logger.log("Edge подключён (debug mode).")

        try:
            WebDriverWait(self.driver, 15).until(
                EC.presence_of_element_located((By.TAG_NAME, "body"))
            )
        except TimeoutException:
            self.logger.log("Страница не загрузилась за 15 секунд.", "ERROR")
            self.driver.quit()
            raise

        self.logger.log(f"Подключено к браузеру. URL: {self.driver.current_url}")

    def is_alive(self) -> bool:
        try:
            _ = self.driver.title
            return True
        except Exception:
            return False

    def reconnect(self):
        self.logger.log("🔄 Переподключение к Edge...")
        self._connect()

    def close(self):
        if self.driver:
            self.driver.quit()
