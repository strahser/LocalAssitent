# start_browser.py – запускает Edge с отладкой через subprocess
import subprocess
import time
import sys
import os
import socket
from config import config

def is_port_in_use(port):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex(('127.0.0.1', port)) == 0

def main():
    if is_port_in_use(config.DEBUG_PORT):
        print(f"⚠️ Порт {config.DEBUG_PORT} уже используется. Возможно, браузер уже запущен.")
        print("   Попробуйте подключиться к существующему браузеру или закройте его и запустите заново.")
        sys.exit(0)

    profile_dir = config.EDGE_USER_DATA_DIR
    if not os.path.exists(profile_dir):
        os.makedirs(profile_dir, exist_ok=True)

    edge_path = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
    if not os.path.exists(edge_path):
        edge_path = r"C:\Program Files\Microsoft\Edge\Application\msedge.exe"
        if not os.path.exists(edge_path):
            print("ERROR: Не найден Edge. Проверьте путь.")
            sys.exit(1)

    cmd = [
        edge_path,
        f"--remote-debugging-port={config.DEBUG_PORT}",
        f"--user-data-dir={profile_dir}",
        "--start-maximized",
        "--no-sandbox",
        "--disable-dev-shm-usage",
        config.DEEPSEEK_URL
    ]

    print(f"🚀 Запуск Edge с портом {config.DEBUG_PORT}...")
    try:
        subprocess.Popen(cmd, shell=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        print("✅ Браузер запущен.")
        print("   Ожидаем инициализации...")
        time.sleep(5)
        if is_port_in_use(config.DEBUG_PORT):
            print("✅ Порт открыт, можно работать.")
        else:
            print("⚠️ Порт не открылся через 5 секунд. Возможно, браузер запустился без отладки.")
            print("   Проверьте вручную, что Edge открыт с флагом --remote-debugging-port.")
        print("   Теперь вы можете запускать ассистента: python assistant.py ...")
        print("   Нажмите Ctrl+C в этом окне, чтобы завершить (браузер закроется автоматически).")
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            print("🔄 Завершение работы...")
            sys.exit(0)
    except Exception as e:
        print(f"❌ Ошибка запуска Edge: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
