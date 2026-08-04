"""
webui/app.py — FastAPI-бэкенд веб-интерфейса LocalAssitent.

Возможности:
  - подключение/отключение к браузеру (Edge debug-mode) и клиенту облачного чата;
  - выбор клиента: DeepSeek / Qwen (+ модель Qwen);
  - пайплайны: qa (вопрос—ответ), code (вопрос—код), merge (проект→контекст→облако),
    improve (один проход анализа проекта);
  - журнал ui.log через /api/logs.

Запуск (из корня проекта):
    py run_ui.py                # uvicorn 127.0.0.1:8000 + открытие браузера
    py -m webui.app             # то же без браузера
"""
import os
import sys
import time
import threading
from pathlib import Path
from typing import Optional

from fastapi import FastAPI
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from logger import Logger
from config import PROVIDERS, QWEN_MODELS, DEFAULT_MODEL, SCENARIO_CONFIGS

STATIC_DIR = Path(__file__).resolve().parent / "static"

app = FastAPI(title="LocalAssitent UI", version="1.0.0")

# ---------------------------------------------------------------------------
# Сессия клиента: один живой клиент = один браузер (Edge debug, порт 9222)
# ---------------------------------------------------------------------------


class ClientSession:
    """Глобальная сессия: один клиент (DeepSeek/Qwen) на всё приложение.

    Все операции с состоянием выполняются под session.lock — последовательно,
    т.к. Selenium-клиент не поддерживает параллельные запросы.
    """

    def __init__(self):
        self.lock = threading.Lock()
        self.client = None
        self.provider: Optional[str] = None
        self.model: Optional[str] = None
        self.logger: Optional[Logger] = None


session = ClientSession()


def get_logger() -> Logger:
    """Лениво создаёт логгер UI (ui.log в корне проекта)."""
    if session.logger is None:
        session.logger = Logger(
            log_to_html=False, log_to_file=True, save_responses=True,
            log_file=str(PROJECT_ROOT / "ui.log"),
            html_file=str(PROJECT_ROOT / "ui_log.html"),
        )
    return session.logger


def _env_credentials(provider: str):
    """Email/пароль из окружения (QWEN_* / DEEPSEEK_* с фолбэком)."""
    email = os.environ.get(f"{provider.upper()}_EMAIL", os.environ.get("DEEPSEEK_EMAIL", ""))
    password = os.environ.get(f"{provider.upper()}_PASSWORD", os.environ.get("DEEPSEEK_PASSWORD", ""))
    return email, password


def connect_client(provider: str, model: Optional[str] = None,
                   email: str = "", password: str = "") -> dict:
    """Создаёт/заменяет клиента: запускает/подключает Edge и логинится в чат.

    ВНИМАНИЕ: вызывать ТОЛЬКО под session.lock (долгая операция — браузер).
    """
    if provider not in PROVIDERS:
        raise RuntimeError(f"Неизвестный провайдер '{provider}'. Доступны: {', '.join(PROVIDERS)}")

    lg = get_logger()
    lg.log(f"🔌 Подключение: provider={provider}, model={model}")

    if provider == "qwen":
        from agent.QwenClient import QwenClient
        client = QwenClient(lg, email=email, password=password, model=model or DEFAULT_MODEL)
        if model:
            try:
                client.select_model(model)
                lg.log(f"🤖 Модель выбрана: {model}")
            except Exception as e:
                lg.log(f"⚠️ Не удалось выбрать модель {model}: {e}", "WARNING")
    else:
        from agent.deepseek_client import DeepSeekClient
        client = DeepSeekClient(lg, email=email, password=password)

    session.client = client
    session.provider = provider
    session.model = model or (DEFAULT_MODEL if provider == "qwen" else None)
    lg.log(f"✅ Подключено: {provider} / {session.model}")
    return {"connected": True, "provider": session.provider, "model": session.model}


def disconnect_client() -> dict:
    """Закрывает клиент (и браузер). Вызывать под session.lock."""
    if session.client is not None:
        try:
            session.client.close()
        except Exception as e:
            get_logger().log(f"⚠️ Ошибка закрытия клиента: {e}", "WARNING")
    session.client = None
    session.provider = None
    session.model = None
    return {"connected": False, "provider": None, "model": None}


def send_message(message: str, new_chat: bool = False) -> dict:
    """Отправляет промпт текущему клиенту (под session.lock)."""
    if session.client is None:
        raise RuntimeError("Не подключено к браузеру. Нажмите «Подключиться к браузеру».")
    lg = get_logger()
    if new_chat:
        try:
            session.client.new_chat()
        except Exception as e:
            lg.log(f"⚠️ new_chat: {e}", "WARNING")
        time.sleep(1.5)
    result = session.client.send_prompt_with_code(message)
    if result is None:
        raise RuntimeError("Ответ от облачного чата не получен (возможно, обрыв соединения).")
    full_text, code_text = result
    lg.log(f"✅ Ответ получен: {len(full_text or '')} символов")
    return {"response": full_text or "", "code": code_text}


# ---------------------------------------------------------------------------
# Пайплайны
# ---------------------------------------------------------------------------

PIPELINES = {
    "qa": {
        "label": "Чат: вопрос — ответ (Q&A)",
        "description": "Вопрос → подробный структурированный ответ (Markdown).",
    },
    "code": {
        "label": "Чат: вопрос — код",
        "description": "Задача → решение + извлечённый код (итоговый полный ответ).",
    },
    "merge": {
        "label": "Проект → контекст → облако",
        "description": "Собрать файлы директории (collect_context, с «общим заданием») и отправить облачному ИИ.",
    },
    "improve": {
        "label": "Improve: анализ проекта",
        "description": "Один проход цикла улучшения: контекст + prompts/improve_analyze.txt (без авто-применения).",
    },
}


def _pipeline_message(pipeline: str, message: str) -> str:
    if pipeline == "qa":
        tpl = SCENARIO_CONFIGS["text"]["prompt_template"]
        return f"{tpl}\n\n**Вопрос:** {message}"
    if pipeline == "code":
        tpl = SCENARIO_CONFIGS["code"]["prompt_template"]
        return f"{tpl}\n\n## Задача\n{message}\n\nКогда задача решена полностью — напиши в конце: TASK_COMPLETE: <описание>"
    return message


def _collect_context_to(directory: str, out_name: str) -> str:
    """Собирает контекст директории через tools.collect_context, возвращает содержимое."""
    from tools.collect_context import collect_context

    d = directory or str(PROJECT_ROOT)
    out = str(PROJECT_ROOT / "pipeline_output" / out_name)
    lg = get_logger()
    lg.log(f"📦 Сбор контекста из: {d}")
    res = collect_context([d], output_file=out, add_task=True, add_summary=True)
    lg.log(f"📦 {res}")
    content = Path(out).read_text(encoding="utf-8", errors="replace")
    lg.log(f"📦 Размер контекста: {len(content)} символов")
    return content, out


def _safe_filename(name: str) -> str:
    """Оставляет только имя файла (без путей), не допускает выхода из pipeline_output."""
    name = os.path.basename((name or "").replace("\\", "/").strip())
    if not name or name in (".", "..") or not name.lower().endswith((".txt", ".md", ".json")):
        return "cloud_context.txt"
    return name


def collect_to_file(directories, project_type: str = "auto",
                    filename: str = "cloud_context.txt") -> dict:
    """Собирает файлы нескольких директорий в один TXT (переиспользует tools.collect_context).

    project_type: auto | cs | py. Для auto тип определяется автоматически;
    для cs/py все указанные директории считаются этого типа.
    """
    dirs = [d for d in (directories or []) if isinstance(d, str) and d.strip()]
    out_name = _safe_filename(filename)
    out = str(PROJECT_ROOT / "pipeline_output" / out_name)
    lg = get_logger()

    if not dirs:
        raise ValueError("Укажите хотя бы одну директорию.")

    for d in dirs:
        p = Path(d)
        if not p.is_dir():
            raise ValueError(f"Директория не найдена: {d}")

    project_types = None
    if project_type in ("cs", "py", "mixed"):
        project_types = {str(Path(d).resolve()): project_type for d in dirs}

    lg.log(f"🖨️ Копирование в один файл: {len(dirs)} директорий, тип={project_type} → {out_name}")
    from tools.collect_context import collect_context
    res = collect_context(
        dirs,
        output_file=out,
        project_types=project_types,
        add_task=True,
        add_summary=True,
    )
    size = Path(out).stat().st_size
    lg.log(f"🖨️ {res}")
    return {
        "message": res,
        "file": out_name,
        "path": out,
        "size": size,
        "download_url": f"/api/file?name={out_name}",
    }


def run_pipeline(pipeline: str, message: str,
                 directory: Optional[str] = None, new_chat: bool = False) -> dict:
    """Выполняет выбранный пайплайн (под session.lock)."""
    if pipeline == "merge":
        content, out = _collect_context_to(directory or "", "ui_merged_context.txt")
        prompt = (
            "Проанализируй приведённый ниже код проекта и дай структурированные рекомендации "
            "(архитектура, ошибки, безопасность, производительность, тестируемость). "
            "Соблюдай формат ответа из инструкции в начале контекста."
        )
        result = send_message(f"{prompt}\n\n{content}", new_chat=new_chat)
        result["note"] = f"Контекст: {out} ({len(content)} символов)"
        return result

    if pipeline == "improve":
        content, out = _collect_context_to(directory or "", "ui_improve_context.txt")
        pf = PROJECT_ROOT / "prompts" / "improve_analyze.txt"
        prompt = pf.read_text(encoding="utf-8") if pf.exists() else (
            "Проанализируй код проекта и предложи улучшения."
        )
        result = send_message(f"{prompt}\n\n{content}", new_chat=new_chat)
        result["note"] = f"Контекст: {out} ({len(content)} символов). Один проход анализа, без авто-применения."
        return result

    prompt = _pipeline_message(pipeline, message)
    return send_message(prompt, new_chat=new_chat)


# ---------------------------------------------------------------------------
# HTTP API
# ---------------------------------------------------------------------------


def _ok(data: dict):
    return JSONResponse({"ok": True, **data})


def _fail(msg: str, status: int = 400):
    return JSONResponse({"ok": False, "error": msg}, status_code=status)


@app.get("/api/health")
def api_health():
    return _ok({
        "connected": session.client is not None,
        "provider": session.provider,
        "model": session.model,
        "pipelines": [{"id": pid, "label": p["label"], "description": p["description"]}
                      for pid, p in PIPELINES.items()],
    })


@app.get("/api/providers")
def api_providers():
    return _ok({
        "providers": [
            {"id": pid, "name": p["name"], "label": p["label"], "url": p["url"]}
            for pid, p in PROVIDERS.items()
        ],
        "qwen_models": QWEN_MODELS,
        "default_model": DEFAULT_MODEL,
    })


@app.post("/api/connect")
def api_connect(payload: dict):
    """Подключение к браузеру/клиенту. Долгая операция (Edge + логин)."""
    payload = payload or {}
    provider = payload.get("provider", "deepseek")
    model = payload.get("model") or None
    email = (payload.get("email") or "").strip()
    password = payload.get("password") or ""
    if not email:
        email, password = _env_credentials(provider)
    try:
        with session.lock:
            disconnect_client()
            return _ok(connect_client(provider, model=model, email=email, password=password))
    except Exception as e:
        return _fail(f"Ошибка подключения: {e}", status=500)


@app.post("/api/disconnect")
def api_disconnect():
    with session.lock:
        return _ok(disconnect_client())


@app.post("/api/chat")
def api_chat(payload: dict):
    """Простое сообщение текущему клиенту (вопрос—ответ)."""
    payload = payload or {}
    message = (payload.get("message") or "").strip()
    new_chat = bool(payload.get("new_chat", False))
    if not message:
        return _fail("Пустое сообщение.")
    try:
        with session.lock:
            return _ok(send_message(message, new_chat=new_chat))
    except RuntimeError as e:
        return _fail(str(e))
    except Exception as e:
        return _fail(f"Ошибка отправки: {e}", status=500)


@app.post("/api/run")
def api_run(payload: dict):
    """Запуск выбранного пайплайна."""
    payload = payload or {}
    pipeline = payload.get("pipeline", "qa")
    message = (payload.get("message") or "").strip()
    directory = payload.get("directory") or None
    new_chat = bool(payload.get("new_chat", False))
    if pipeline not in PIPELINES:
        return _fail(f"Неизвестный пайплайн '{pipeline}'. Доступны: {', '.join(PIPELINES)}")
    if not message:
        return _fail("Пустое сообщение/задача.")
    try:
        with session.lock:
            return _ok(run_pipeline(pipeline, message, directory=directory, new_chat=new_chat))
    except RuntimeError as e:
        return _fail(str(e))
    except Exception as e:
        return _fail(f"Ошибка пайплайна: {e}", status=500)


@app.get("/api/logs")
def api_logs(limit: int = 60):
    try:
        lines = Path(PROJECT_ROOT / "ui.log").read_text(encoding="utf-8", errors="replace").splitlines()
    except Exception:
        return _ok({"logs": []})
    return _ok({"logs": lines[-int(limit):]})


@app.post("/api/collect")
def api_collect(payload: dict):
    """Скопировать файлы нескольких директорий в один файл (без облачного чата)."""
    payload = payload or {}
    try:
        result = collect_to_file(
            payload.get("directories"),
            project_type=payload.get("project_type", "auto"),
            filename=payload.get("filename", "cloud_context.txt"),
        )
        return _ok(result)
    except ValueError as e:
        return _fail(str(e))
    except Exception as e:
        get_logger().log(f"🖨️ Ошибка: {e}", "WARNING")
        return _fail(f"Ошибка копирования: {e}", status=500)


@app.get("/api/file")
def api_file(name: str = "cloud_context.txt"):
    """Отдаёт собранный файл из pipeline_output (только скачивание, без браузера)."""
    out = Path(PROJECT_ROOT / "pipeline_output") / _safe_filename(name)
    if not out.exists():
        return _fail(f"Файл не найден: {name}", status=404)
    return FileResponse(out, media_type="text/plain; charset=utf-8",
                        filename=out.name)


# ---------------------------------------------------------------------------
# Статика
# ---------------------------------------------------------------------------


@app.get("/")
def index():
    return FileResponse(STATIC_DIR / "index.html")


app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


if __name__ == "__main__":
    import uvicorn

    print("🌐 LocalAssitent UI: http://127.0.0.1:8000/")
    uvicorn.run(app, host="127.0.0.1", port=8000, log_level="info")
