"""
prompts_db.py — SQLite-хранилище промптов для пайплайнов LocalAssitent.

Нормализованная схема (3NF):
  pipelines     — пайплайны (qa, code, merge, improve);
  prompts       — промпты (FK -> pipelines), stage: first | subsequent | both;
  prompt_config — какой промпт используется для первого/последующих сообщений
                  (FK -> pipelines, FK -> prompts).

Два API (совместимы между собой):
  - модульные функции: init_db / reset_db / get_all_prompts(db_path=None) / ...;
  - класс PromptsDB(db_path) — тонкая обёртка над модульными функциями.

Модульные функции лениво инициализируют БД (создают схему + сидинг) при
первом обращении к выбранному пути. Путь: явный аргумент > активный
(init_db) > env LOCALASSISTANT_DB > data/localassistant.db.
"""
import os
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Optional

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DB_PATH = PROJECT_ROOT / "data" / "localassistant.db"

STAGES = ("first", "subsequent", "both")
PIPELINE_LABELS = {
    "qa": "Чат: вопрос — ответ (Q&A)",
    "code": "Чат: вопрос — код",
    "merge": "Проект → контекст → облако",
    "improve": "Improve: анализ проекта",
}

_SCHEMA = """
CREATE TABLE IF NOT EXISTS pipelines (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    key TEXT UNIQUE NOT NULL,
    label TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS prompts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    pipeline_id INTEGER NOT NULL REFERENCES pipelines(id),
    stage TEXT NOT NULL CHECK(stage IN ('first','subsequent','both')),
    name TEXT NOT NULL,
    content TEXT NOT NULL,
    is_active INTEGER DEFAULT 1,
    created_at TEXT,
    updated_at TEXT,
    UNIQUE(pipeline_id, stage, name)
);
CREATE TABLE IF NOT EXISTS prompt_config (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    pipeline_id INTEGER UNIQUE NOT NULL REFERENCES pipelines(id),
    first_prompt_id INTEGER REFERENCES prompts(id),
    subsequent_prompt_id INTEGER REFERENCES prompts(id)
);
"""

_ACTIVE_DB: Optional[Path] = None


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _resolve_path(db_path=None) -> Path:
    if db_path is not None:
        return Path(db_path)
    if _ACTIVE_DB is not None:
        return _ACTIVE_DB
    env = os.environ.get("LOCALASSISTANT_DB")
    if env:
        return Path(env)
    return DEFAULT_DB_PATH


def _connect(db_path=None) -> sqlite3.Connection:
    """Открывает соединение и лениво создаёт схему/сидинг, если их нет."""
    path = _resolve_path(db_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    _ensure_schema(conn)
    return conn


def _seed_defaults(conn):
    """Сидинг дефолтных промптов (qa/code first; improve analyze+review)."""
    from config import SCENARIO_CONFIGS

    def pipe_id(key):
        row = conn.execute("SELECT id FROM pipelines WHERE key=?", (key,)).fetchone()
        return row["id"] if row else None

    def add(key, stage, name, content):
        pid = pipe_id(key)
        if pid is None or not content:
            return None
        now = _now()
        cur = conn.execute(
            "INSERT OR IGNORE INTO prompts(pipeline_id, stage, name, content, is_active, created_at, updated_at)"
            " VALUES (?, ?, ?, ?, 1, ?, ?)",
            (pid, stage, name, content, now, now),
        )
        return cur.lastrowid or None

    seeds = []
    text_tpl = SCENARIO_CONFIGS.get("text", {}).get("prompt_template")
    code_tpl = SCENARIO_CONFIGS.get("code", {}).get("prompt_template")
    if text_tpl:
        seeds.append(("qa", "first", "default qa", text_tpl))
    if code_tpl:
        seeds.append(("code", "first", "default code", code_tpl))

    # merge: промпт для «общего файла» (контекст проектов → облако).
    # Раньше был захардкожен в webui/app.py, теперь живёт в БД.
    merge_tpl = (
        "Проанализируй приведённый ниже код проекта и дай структурированные рекомендации "
        "(архитектура, ошибки, безопасность, производительность, тестируемость). "
        "Соблюдай формат ответа из инструкции в начале контекста."
    )
    seeds.append(("merge", "first", "default merge", merge_tpl))

    improve_analyze = PROJECT_ROOT / "prompts" / "improve_analyze.txt"
    improve_review = PROJECT_ROOT / "prompts" / "improve_review.txt"
    if improve_analyze.exists():
        seeds.append(("improve", "first", "default improve analyze",
                      improve_analyze.read_text(encoding="utf-8", errors="replace")))
    if improve_review.exists():
        seeds.append(("improve", "subsequent", "default improve review",
                      improve_review.read_text(encoding="utf-8", errors="replace")))

    ids = {}
    for key, stage, name, content in seeds:
        pid = add(key, stage, name, content)
        if pid:
            ids.setdefault(key, {})[stage] = pid

    # prompt_config: qa/code/merge -> first; improve -> first + subsequent
    for key, stages in (("qa", ("first",)), ("code", ("first",)),
                        ("merge", ("first",)),
                        ("improve", ("first", "subsequent"))):
        pid = pipe_id(key)
        if pid is None:
            continue
        pids = ids.get(key, {})
        first = pids.get("first")
        sub = pids.get("subsequent", first)
        if first is not None:
            conn.execute(
                "UPDATE prompt_config SET first_prompt_id=?, subsequent_prompt_id=?"
                " WHERE pipeline_id=?",
                (first, sub, pid),
            )


def _ensure_schema(conn):
    """Создаёт таблицы (если нет), сидит pipelines/prompt_config и промпты."""
    conn.executescript(_SCHEMA)
    for key, label in PIPELINE_LABELS.items():
        conn.execute("INSERT OR IGNORE INTO pipelines(key, label) VALUES (?, ?)", (key, label))
    for key in PIPELINE_LABELS:
        pid = conn.execute("SELECT id FROM pipelines WHERE key=?", (key,)).fetchone()["id"]
        conn.execute("INSERT OR IGNORE INTO prompt_config(pipeline_id) VALUES (?)", (pid,))
    conn.commit()
    if conn.execute("SELECT COUNT(*) FROM prompts").fetchone()[0] == 0:
        _seed_defaults(conn)
        conn.commit()


# ---------------------------------------------------------------------------
# Инициализация
# ---------------------------------------------------------------------------


def init_db(db_path=None) -> "PromptsDB":
    """Инициализирует БД по выбранному пути, возвращает PromptsDB."""
    global _ACTIVE_DB
    path = _resolve_path(db_path)
    _ACTIVE_DB = path
    return PromptsDB(path)


def reset_db():
    """Сбрасывает активный путь БД к env/дефолту (для тестов)."""
    global _ACTIVE_DB
    _ACTIVE_DB = None


def ensure_initialized():
    init_db()


class PromptsDB:
    """SQLite-хранилище промптов. Обёртка над модульными функциями."""

    def __init__(self, db_path):
        self.db_path = str(Path(db_path))
        conn = _connect(self.db_path)
        conn.close()

    def get_all_prompts(self):
        return get_all_prompts(db_path=self.db_path)

    def create_prompt(self, pipeline, stage, name, content, is_active=1):
        return create_prompt(pipeline, stage, name, content, is_active=is_active,
                             db_path=self.db_path)

    def update_prompt(self, prompt_id, **fields):
        return update_prompt(prompt_id, db_path=self.db_path, **fields)

    def delete_prompt(self, prompt_id):
        return delete_prompt(prompt_id, db_path=self.db_path)

    def get_prompt_for(self, pipeline, stage):
        return get_prompt_for(pipeline, stage, db_path=self.db_path)

    def get_prompt_config(self):
        return get_prompt_config(db_path=self.db_path)

    def set_prompt_config(self, pipeline, stage, prompt_id):
        return set_prompt_config(pipeline, stage, prompt_id, db_path=self.db_path)


# ---------------------------------------------------------------------------
# Валидация / хелперы
# ---------------------------------------------------------------------------


def _validate_stage(stage, allow_both: bool = True) -> str:
    if stage not in STAGES:
        raise ValueError(f"Недопустимый stage '{stage}'. Ожидается: {', '.join(STAGES)}")
    if not allow_both and stage == "both":
        raise ValueError("Для конфигурации допустимы stage: first или subsequent.")
    return stage


def _pipeline_id(conn, pipeline: str) -> Optional[int]:
    row = conn.execute("SELECT id FROM pipelines WHERE key=?", (pipeline,)).fetchone()
    return row["id"] if row else None


def _require_pipeline(conn, pipeline: str) -> int:
    pid = _pipeline_id(conn, pipeline)
    if pid is None:
        raise ValueError(
            f"Неизвестный пайплайн '{pipeline}'. Доступны: {', '.join(PIPELINE_LABELS)}"
        )
    return pid


# ---------------------------------------------------------------------------
# CRUD
# ---------------------------------------------------------------------------


def get_all_prompts(db_path=None) -> list:
    conn = _connect(db_path)
    try:
        rows = conn.execute(
            """
            SELECT p.id, p.pipeline_id, pl.key AS pipeline, p.stage, p.name,
                   p.content, p.is_active, p.created_at, p.updated_at
            FROM prompts p
            JOIN pipelines pl ON pl.id = p.pipeline_id
            ORDER BY pl.key, p.stage, p.id
            """
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def get_prompt_by_id(prompt_id: int, db_path=None) -> Optional[dict]:
    conn = _connect(db_path)
    try:
        row = conn.execute(
            """
            SELECT p.id, p.pipeline_id, pl.key AS pipeline, p.stage, p.name,
                   p.content, p.is_active, p.created_at, p.updated_at
            FROM prompts p
            JOIN pipelines pl ON pl.id = p.pipeline_id
            WHERE p.id=?
            """,
            (prompt_id,),
        ).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def create_prompt(pipeline: str, stage: str, name: str, content: str,
                  is_active: int = 1, db_path=None) -> dict:
    _validate_stage(stage)
    if not name or not name.strip() or not content:
        raise ValueError("name и content обязательны")
    conn = _connect(db_path)
    try:
        pid = _require_pipeline(conn, pipeline)
        now = _now()
        try:
            cur = conn.execute(
                "INSERT INTO prompts(pipeline_id, stage, name, content, is_active, created_at, updated_at)"
                " VALUES (?, ?, ?, ?, ?, ?, ?)",
                (pid, stage, name.strip(), content, 1 if is_active else 0, now, now),
            )
        except sqlite3.IntegrityError:
            raise ValueError(f"Промпт '{name}' для пайплайна '{pipeline}' (stage={stage}) уже существует")
        conn.commit()
        return get_prompt_by_id(cur.lastrowid, db_path=db_path)
    finally:
        conn.close()


def update_prompt(prompt_id: int, db_path=None, **fields) -> Optional[dict]:
    allowed = {"name", "content", "is_active", "stage"}
    unknown = set(fields) - allowed
    if unknown:
        raise ValueError(f"Неизвестные поля для обновления: {', '.join(sorted(unknown))}")
    updates = {k: v for k, v in fields.items() if k in allowed and v is not None}
    conn = _connect(db_path)
    try:
        if updates:
            if "stage" in updates:
                _validate_stage(updates["stage"])
            if "name" in updates and (not updates["name"] or not updates["name"].strip()):
                raise ValueError("name не может быть пустым")
            sets = ", ".join(f"{k}=?" for k in updates)
            params = list(updates.values()) + [_now(), prompt_id]
            conn.execute(f"UPDATE prompts SET {sets}, updated_at=? WHERE id=?", params)
            conn.commit()
        return get_prompt_by_id(prompt_id, db_path=db_path)
    finally:
        conn.close()


def delete_prompt(prompt_id: int, db_path=None) -> bool:
    conn = _connect(db_path)
    try:
        conn.execute(
            "UPDATE prompt_config SET first_prompt_id=NULL WHERE first_prompt_id=?",
            (prompt_id,),
        )
        conn.execute(
            "UPDATE prompt_config SET subsequent_prompt_id=NULL WHERE subsequent_prompt_id=?",
            (prompt_id,),
        )
        cur = conn.execute("DELETE FROM prompts WHERE id=?", (prompt_id,))
        conn.commit()
        return cur.rowcount > 0
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Конфигурация: какой промпт для первого/последующих сообщений
# ---------------------------------------------------------------------------


def get_prompt_config(db_path=None) -> dict:
    conn = _connect(db_path)
    try:
        rows = conn.execute(
            """
            SELECT pl.key AS pipeline, pc.first_prompt_id, pc.subsequent_prompt_id
            FROM prompt_config pc
            JOIN pipelines pl ON pl.id = pc.pipeline_id
            """
        ).fetchall()
        result = {}
        for r in rows:
            result[r["pipeline"]] = {
                "first": r["first_prompt_id"],
                "subsequent": r["subsequent_prompt_id"],
            }
        return result
    finally:
        conn.close()


def set_prompt_config(pipeline: str, stage: str, prompt_id, db_path=None) -> dict:
    _validate_stage(stage, allow_both=False)
    conn = _connect(db_path)
    try:
        pid = _require_pipeline(conn, pipeline)
        if prompt_id is not None:
            row = conn.execute(
                "SELECT id FROM prompts WHERE id=? AND pipeline_id=?",
                (prompt_id, pid),
            ).fetchone()
            if row is None:
                raise ValueError(f"Промпт {prompt_id} не принадлежит пайплайну '{pipeline}'")
        conn.execute(
            f"""
            INSERT INTO prompt_config(pipeline_id, {stage}_prompt_id)
            VALUES (?, ?)
            ON CONFLICT(pipeline_id) DO UPDATE SET {stage}_prompt_id=excluded.{stage}_prompt_id
            """,
            (pid, prompt_id),
        )
        conn.commit()
        return get_prompt_config(db_path=db_path)
    finally:
        conn.close()


def get_prompt_for(pipeline: str, stage: str, db_path=None) -> Optional[str]:
    """Возвращает content активного промпта для (pipeline, stage).

    Порядок: prompt_config[stage] -> активный промпт со stage='both' ->
    активный промпт со stage=stage. Неизвестный пайплайн -> None.
    """
    conn = _connect(db_path)
    try:
        pid = _pipeline_id(conn, pipeline)
        if pid is None or stage not in STAGES:
            return None

        if stage in ("first", "subsequent"):
            col = f"{stage}_prompt_id"
            row = conn.execute(
                f"SELECT {col} FROM prompt_config WHERE pipeline_id=?", (pid,)
            ).fetchone()
            if row and row[col] is not None:
                pr = conn.execute(
                    "SELECT content FROM prompts WHERE id=? AND is_active=1",
                    (row[col],),
                ).fetchone()
                if pr:
                    return pr["content"]

        row = conn.execute(
            "SELECT content FROM prompts WHERE pipeline_id=? AND stage='both' AND is_active=1"
            " ORDER BY id LIMIT 1",
            (pid,),
        ).fetchone()
        if row:
            return row["content"]

        row = conn.execute(
            "SELECT content FROM prompts WHERE pipeline_id=? AND stage=? AND is_active=1"
            " ORDER BY id LIMIT 1",
            (pid, stage),
        ).fetchone()
        return row["content"] if row else None
    finally:
        conn.close()
