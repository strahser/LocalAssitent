"""Tests for webui/app.py (FastAPI UI backend).

ВНИМАНИЕ: НЕ дёргаем /api/connect с валидным провайдером — он запускает Edge.
Только чистое состояние (health/providers/static) и пути ошибок.

Запуск:  py -m pytest tests/test_webui.py -q
"""
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi.testclient import TestClient

from webui.app import app, disconnect_client

client = TestClient(app)


def _reset():
    """Сбрасываем сессию клиента (клиент не создаётся — только очистка)."""
    disconnect_client()


def test_health_initial():
    _reset()
    r = client.get("/api/health")
    assert r.status_code == 200
    data = r.json()
    assert data["ok"] is True
    assert data["connected"] is False
    ids = [p["id"] for p in data["pipelines"]]
    assert {"qa", "code", "merge", "improve"}.issubset(set(ids))


def test_providers():
    r = client.get("/api/providers")
    assert r.status_code == 200
    data = r.json()
    pids = {p["id"] for p in data["providers"]}
    assert "deepseek" in pids and "qwen" in pids
    assert data["qwen_models"]
    assert data["default_model"]


def test_index_served():
    r = client.get("/")
    assert r.status_code == 200
    assert "LocalAssitent" in r.text
    assert "подключиться" in r.text.lower()


def test_static_js_served():
    r = client.get("/static/app.js")
    assert r.status_code == 200
    assert "fetch" in r.text


def test_static_css_served():
    r = client.get("/static/style.css")
    assert r.status_code == 200
    assert "body" in r.text


def test_chat_without_connect_clean_error():
    _reset()
    r = client.post("/api/chat", json={"message": "hi"})
    assert r.status_code == 400
    data = r.json()
    assert data["ok"] is False
    assert "Не подключено" in data["error"]


def test_run_unknown_pipeline_error():
    r = client.post("/api/run", json={"pipeline": "bad", "message": "x"})
    assert r.status_code == 400
    data = r.json()
    assert data["ok"] is False
    assert "Неизвестный пайплайн" in data["error"]


def test_run_empty_message_error():
    _reset()
    r = client.post("/api/run", json={"pipeline": "qa", "message": "  "})
    assert r.status_code == 400
    assert r.json()["ok"] is False


def test_connect_unknown_provider_error():
    # невалидный провайдер — без запуска браузера
    r = client.post("/api/connect", json={"provider": "nope"})
    assert r.status_code == 500
    data = r.json()
    assert data["ok"] is False
    assert "deepseek" in data["error"]


def test_disconnect_returns_ok():
    _reset()
    r = client.post("/api/disconnect", json={})
    assert r.status_code == 200
    data = r.json()
    assert data["ok"] is True
    assert data["connected"] is False


def test_logs_empty_or_json():
    r = client.get("/api/logs?limit=5")
    assert r.status_code == 200
    data = r.json()
    assert data["ok"] is True
    assert isinstance(data["logs"], list)


def test_run_merge_collects_then_gates_on_connect():
    """merge собирает контекст маленькой temp-папки, затем падает на «не подключено»."""
    _reset()
    with tempfile.TemporaryDirectory() as d:
        p = os.path.join(d, "a.cs")
        with open(p, "w", encoding="utf-8") as f:
            f.write("class A {}")
        os.makedirs(os.path.join(d, "obj"))
        with open(os.path.join(d, "obj", "x.cs"), "w", encoding="utf-8") as f:
            f.write("// temp")
        r = client.post("/api/run", json={
            "pipeline": "merge", "message": "анализ", "directory": d,
        })
    assert r.status_code == 400
    data = r.json()
    assert data["ok"] is False
    assert "Не подключено" in data["error"]