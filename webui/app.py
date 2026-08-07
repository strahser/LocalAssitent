"""
webui/app.py — FastAPI-бэкенд веб-интерфейса LocalAssitent.

Возможности:
  - подключение/отключение к браузеру (Edge debug-mode) и клиенту облачного чата;
  - выбор клиента: DeepSeek / Qwen (+ модель Qwen);
  - пайплайны: qa (вопрос—ответ), code (вопрос—код), merge (проект→контекст→облако),
    improve (один проход анализа проекта);
  - настройка промптов пайплайнов: SQLite (data/localassistant.db) + CRUD
    /api/prompts, /api/prompt-config; префилл кредов /api/credentials;
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
from config import PROVIDERS, QWEN_MODELS, DEFAULT_MODEL

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

# Счётчик сообщений текущей сессии: 0 = следующее сообщение первое.
# Используется для выбора промпта first/subsequent (см. webui.prompts_db).
session_message_count = 0


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
    """Отправляет промпт текущему клиенту (под session.lock).

    new_chat=True сбрасывает счётчик сообщений сессии — следующее сообщение
    будет считаться первым (используется промпт stage='first').
    """
    global session_message_count
    if session.client is None:
        raise RuntimeError("Не подключено к браузеру. Нажмите «Подключиться к браузеру».")
    lg = get_logger()
    if new_chat:
        session_message_count = 0
        try:
            session.client.new_chat()
        except Exception as e:
            lg.log(f"⚠️ new_chat: {e}", "WARNING")
        time.sleep(1.5)
    result = session.client.send_prompt_with_code(message)
    if result is None:
        raise RuntimeError("Ответ от облачного чата не получен (возможно, обрыв соединения).")
    full_text, code_text = result
    session_message_count += 1
    lg.log(f"✅ Ответ получен: {len(full_text or '')} символов")
    return {"response": full_text or "", "code": code_text}


# ---------------------------------------------------------------------------
# Пайплайны
# ---------------------------------------------------------------------------

PIPELINES = {
    "qa": {
        "label": "Вопрос — ответ (Q&A)",
        "description": "Вопрос → подробный структурированный ответ (Markdown).",
    },
    "merge": {
        "label": "Формирование сводного файла (контекст) + отправка",
        "description": "Собрать файлы директории в сводный файл (в начале — TDL-промпт), "
                       "локальный промпт пользователя, отправить облачному ИИ.",
    },
}


def _pipeline_message(pipeline: str, message: str, stage: str = "both") -> str:
    """Собирает промпт для пайплайна из БД (webui.prompts_db).

    stage: 'first' | 'subsequent' | 'both'. Промпты живут в SQLite
    (сидинг из SCENARIO_CONFIGS / prompts/*.txt / merge), здесь только
    обёртка-формат. Если промпта нет в БД — используем простое сообщение.
    """
    tpl = None
    try:
        from webui.prompts_db import get_prompt_for
        tpl = get_prompt_for(pipeline, stage) or get_prompt_for(pipeline, "both")
    except Exception:
        tpl = None
    if not tpl:
        tpl = "Ответь на вопрос."
    if pipeline == "qa":
        return f"{tpl}\n\n**Вопрос:** {message}"
    if pipeline == "code":
        return f"{tpl}\n\n## Задача\n{message}\n\nКогда задача решена полностью — напиши в конце: TASK_COMPLETE: <описание>"
    return message


def _collect_context_to(directory: str, out_name: str, local_prompt: str = "") -> str:
    """Собирает контекст директории через tools.collect_context, возвращает содержимое."""
    from tools.collect_context import collect_context

    d = directory or str(PROJECT_ROOT)
    out = str(PROJECT_ROOT / "pipeline_output" / out_name)
    lg = get_logger()
    lg.log(f"📦 Сбор контекста из: {d}")
    res = collect_context([d], output_file=out, add_task=True, add_summary=True,
                          local_prompt=local_prompt)
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
                    filename: str = "cloud_context.txt",
                    local_prompt: str = "") -> dict:
    """Собирает файлы нескольких директорий в один TXT (переиспользует tools.collect_context).

    project_type: auto | cs | py. Для auto тип определяется автоматически;
    для cs/py все указанные директории считаются этого типа.
    local_prompt: локальный промпт пользователя — вставляется в начало сводного файла
    (поверх общего TDL-задания из prompts/general_task.txt).
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
        local_prompt=local_prompt,
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
    global session_message_count
    if new_chat:
        # новый чат = новая сессия: первое сообщение получает промпт stage='first'
        session_message_count = 0
    stage = "first" if session_message_count == 0 else "subsequent"

    if pipeline == "merge":
        # message = локальный промпт пользователя (вставляется в начало сводного файла),
        # поверх общего TDL-задания из prompts/general_task.txt
        content, out = _collect_context_to(directory or "", "ui_merged_context.txt",
                                           local_prompt=message)
        from webui.prompts_db import get_prompt_for
        prompt = get_prompt_for("merge", stage) or get_prompt_for("merge", "both") or (
            "Выполни локальный промпт пользователя, соблюдая формат ответа из "
            "инструкции в начале контекста (TDL)."
        )
        result = send_message(f"{prompt}\n\n{content}", new_chat=new_chat)
        result["note"] = f"Сводный файл: {out} ({len(content)} символов)"
        return result

    prompt = _pipeline_message(pipeline, message, stage=stage)
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
        "session_messages": session_message_count,
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


@app.get("/api/credentials")
def api_credentials():
    """Возвращает email и признак наличия пароля из .env (без самих паролей).

    Используется фронтом для префилла формы логина: если поля пустые,
    бэкенд всё равно возьмёт креды из окружения.
    """
    return _ok({
        "deepseek": {
            "email": os.environ.get("DEEPSEEK_EMAIL", ""),
            "has_password": bool(os.environ.get("DEEPSEEK_PASSWORD")),
        },
        "qwen": {
            "email": os.environ.get("QWEN_EMAIL", ""),
            "has_password": bool(os.environ.get("QWEN_PASSWORD")),
        },
    })


# ---------------------------------------------------------------------------
# Промпты (SQLite CRUD, см. webui/prompts_db.py)
# ---------------------------------------------------------------------------


@app.get("/api/prompts")
def api_prompts_list():
    try:
        from webui.prompts_db import ensure_initialized, get_all_prompts
        ensure_initialized()
        return _ok({"prompts": get_all_prompts()})
    except Exception as e:
        return _fail(f"Ошибка чтения промптов: {e}", status=500)


@app.post("/api/prompts")
def api_prompts_create(payload: dict):
    payload = payload or {}
    try:
        from webui.prompts_db import ensure_initialized, create_prompt
        ensure_initialized()
        prompt = create_prompt(
            pipeline=payload.get("pipeline", ""),
            stage=payload.get("stage", "both"),
            name=payload.get("name", ""),
            content=payload.get("content", ""),
            is_active=int(payload.get("is_active", 1)),
        )
        return _ok({"prompt": prompt})
    except ValueError as e:
        return _fail(str(e))
    except Exception as e:
        return _fail(f"Ошибка создания промпта: {e}", status=500)


@app.put("/api/prompts/{prompt_id}")
def api_prompts_update(prompt_id: int, payload: dict):
    payload = payload or {}
    try:
        from webui.prompts_db import update_prompt
        prompt = update_prompt(
            prompt_id,
            name=payload.get("name"),
            content=payload.get("content"),
            is_active=payload.get("is_active"),
            stage=payload.get("stage"),
        )
        if prompt is None:
            return _fail(f"Промпт {prompt_id} не найден", status=404)
        return _ok({"prompt": prompt})
    except Exception as e:
        return _fail(f"Ошибка обновления промпта: {e}", status=500)


@app.delete("/api/prompts/{prompt_id}")
def api_prompts_delete(prompt_id: int):
    try:
        from webui.prompts_db import delete_prompt
        ok = delete_prompt(prompt_id)
        if not ok:
            return _fail(f"Промпт {prompt_id} не найден", status=404)
        return _ok({"deleted": prompt_id})
    except Exception as e:
        return _fail(f"Ошибка удаления промпта: {e}", status=500)


@app.get("/api/prompt-config")
def api_prompt_config_get():
    try:
        from webui.prompts_db import ensure_initialized, get_prompt_config
        ensure_initialized()
        return _ok({"config": get_prompt_config()})
    except Exception as e:
        return _fail(f"Ошибка чтения конфигурации промптов: {e}", status=500)


@app.post("/api/prompt-config")
def api_prompt_config_set(payload: dict):
    payload = payload or {}
    pipeline = payload.get("pipeline", "")
    stage = payload.get("stage", "")
    prompt_id = payload.get("prompt_id")
    try:
        from webui.prompts_db import set_prompt_config
        config = set_prompt_config(pipeline, stage, prompt_id)
        return _ok({"config": config})
    except ValueError as e:
        return _fail(str(e))
    except Exception as e:
        return _fail(f"Ошибка сохранения конфигурации промптов: {e}", status=500)


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


@app.post("/api/qa-file")
def api_qa_file(payload: dict):
    """Построчный конвейер «вопрос—ответ»:
    общий промпт + файл с вопросами (по одному на строку) →
    для каждой строки отправка в ИИ → ответы → запись в выходной файл.

    payload: { prompt, input_file, output_file, new_chat }
    Возвращает { ok, history: [{q, a}], output_file, total }
    """
    payload = payload or {}
    prompt = (payload.get("prompt") or "").strip()
    input_file = (payload.get("input_file") or "").strip()
    output_file = (payload.get("output_file") or "").strip()
    new_chat = bool(payload.get("new_chat", False))
    if session.client is None:
        return _fail("Не подключено к браузеру. Нажмите «Подключиться к браузеру».")
    if not prompt:
        prompt = "Ответь на вопросы в формате «Вопрос: ... / Ответ: ...». Отвечай подробно."
    if not input_file:
        return _fail("Укажите путь к файлу с вопросами (input_file).")
    in_path = Path(input_file)
    if not in_path.exists():
        return _fail(f"Файл с вопросами не найден: {input_file}")
    if not output_file:
        output_file = str(PROJECT_ROOT / "pipeline_output" / "qa_answers.md")
    out_path = Path(output_file)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with session.lock:
            # новый чат: первое сообщение = общий промпт (контекст)
            if new_chat:
                session_message_count = 0
                try:
                    session.client.new_chat()
                except Exception as e:
                    get_logger().log(f"⚠️ new_chat: {e}", "WARNING")
                time.sleep(1.5)
            # читаем вопросы построчно
            questions = [ln.strip() for ln in in_path.read_text(encoding="utf-8", errors="replace").splitlines() if ln.strip()]
            if not questions:
                return _fail("Файл с вопросами пуст.")
            lg = get_logger()
            lg.log(f"❓ Q&A-конвейер: {len(questions)} вопросов, промпт='{prompt[:60]}...'")
            history = []
            # если это первый запрос сессии — отправляем общий промпт как контекст
            if session_message_count == 0:
                ctx = session.client.send_prompt(prompt)
                session_message_count += 1
                lg.log(f"🧠 Контекст отправлен ({len(ctx or '')} символов)")
            # по одному вопросу
            for i, q in enumerate(questions, 1):
                msg = f"{prompt}\n\n**Вопрос {i}:** {q}"
                if i == 1 and session_message_count == 0:
                    result = session.client.send_prompt(msg)
                else:
                    result = session.client.send_prompt(msg)
                session_message_count += 1
                answer = (result or "(пустой ответ)") if result is not None else "(ответ не получен)"
                history.append({"q": q, "a": answer})
                lg.log(f"❓ Вопрос {i}/{len(questions)}: {q[:50]} → ответ {len(answer)} символов")
            # пишем в файл
            lines = []
            for it in history:
                lines.append(f"**Вопрос:** {it['q']}\n\n**Ответ:** {it['a']}\n\n---\n")
            out_path.write_text("\n".join(lines), encoding="utf-8")
            lg.log(f"💾 Ответы сохранены: {out_path} ({len(history)} шт.)")
            return _ok({"history": history, "output_file": str(out_path),
                        "total": len(history), "download_url": f"/api/qa-file-download?name={out_path.name}"})
    except RuntimeError as e:
        return _fail(str(e))
    except Exception as e:
        return _fail(f"Ошибка Q&A-конвейера: {e}", status=500)


@app.get("/api/qa-file-download")
def api_qa_file_download(name: str = "qa_answers.md"):
    """Скачать файл с ответами Q&A из pipeline_output."""
    out = Path(PROJECT_ROOT / "pipeline_output") / _safe_filename(name)
    if not out.exists():
        return _fail(f"Файл не найден: {name}", status=404)
    return FileResponse(out, media_type="text/plain; charset=utf-8", filename=out.name)


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
            local_prompt=payload.get("local_prompt", ""),
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
