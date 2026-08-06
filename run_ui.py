"""
run_ui.py — запуск веб-интерфейса LocalAssitent (FastAPI + статика).

Открывает порт и браузер с UI:
    py run_ui.py                 # http://127.0.0.1:8080/ (браузер откроется сам)
    py run_ui.py --port 8000     # другой порт
    py run_ui.py --no-browser    # не открывать браузер
"""
import argparse
import threading
import webbrowser

import uvicorn


def main():
    ap = argparse.ArgumentParser(description="LocalAssitent Web UI (FastAPI)")
    ap.add_argument("--host", default="127.0.0.1", help="Хост (по умолчанию 127.0.0.1)")
    ap.add_argument("--port", type=int, default=8080, help="Порт (по умолчанию 8080)")
    ap.add_argument("--no-browser", action="store_true", help="Не открывать браузер автоматически")
    args = ap.parse_args()

    url = f"http://{args.host}:{args.port}/"

    if not args.no_browser:
        # браузер открывается с небольшой задержкой — после старта сервера
        threading.Timer(1.5, lambda: webbrowser.open(url)).start()

    from webui.app import app

    print("=" * 56)
    print("  LocalAssitent Web UI")
    print(f"  Открой в браузере: {url}")
    print("  Ctrl+C — остановить сервер")
    print("=" * 56)

    uvicorn.run(app, host=args.host, port=args.port, log_level="info")


if __name__ == "__main__":
    main()
