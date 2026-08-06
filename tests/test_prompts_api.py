"""Tests for webui/app.py — prompt API + credentials (offline, tmp DB).

Не трогаем /api/connect (запускает браузер).
Запуск:  py -m pytest tests/test_prompts_api.py -q
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from fastapi.testclient import TestClient

import webui.prompts_db as pdb
from webui.app import app, disconnect_client

client = TestClient(app)


@pytest.fixture()
def api_db(tmp_path):
    pdb.init_db(str(tmp_path / "api.sqlite"))
    disconnect_client()  # чистое состояние сессии
    yield
    pdb.reset_db()


def _first_prompt_id(pipeline):
    prompts = pdb.get_all_prompts()
    for p in prompts:
        if p["pipeline"] == pipeline and p["stage"] == "first":
            return p["id"]
    raise AssertionError(f"нет first-промпта для {pipeline}")


def test_prompts_list_seeded(api_db):
    r = client.get("/api/prompts")
    assert r.status_code == 200
    data = r.json()
    assert data["ok"] is True
    prompts = data["prompts"]
    assert len(prompts) >= 4
    p0 = prompts[0]
    for key in ("id", "pipeline", "stage", "name", "content", "is_active"):
        assert key in p0


def test_prompt_create(api_db):
    r = client.post("/api/prompts", json={
        "pipeline": "qa", "stage": "both", "name": "qa custom",
        "content": "Кратко.", "is_active": 1,
    })
    assert r.status_code == 200
    prompt = r.json()["prompt"]
    assert prompt["name"] == "qa custom"
    assert prompt["stage"] == "both"
    assert prompt["pipeline"] == "qa"


def test_prompt_create_unknown_pipeline(api_db):
    r = client.post("/api/prompts", json={
        "pipeline": "bad", "stage": "first", "name": "x", "content": "y",
    })
    assert r.status_code == 400
    assert r.json()["ok"] is False


def test_prompt_create_invalid_stage(api_db):
    r = client.post("/api/prompts", json={
        "pipeline": "qa", "stage": "middle", "name": "x", "content": "y",
    })
    assert r.status_code == 400
    assert r.json()["ok"] is False


def test_prompt_update(api_db):
    pid = _first_prompt_id("qa")
    r = client.put(f"/api/prompts/{pid}", json={"name": "renamed", "content": "Новый текст."})
    assert r.status_code == 200
    prompt = r.json()["prompt"]
    assert prompt["name"] == "renamed"
    assert prompt["content"] == "Новый текст."


def test_prompt_update_not_found(api_db):
    r = client.put("/api/prompts/99999", json={"name": "x"})
    assert r.status_code == 404


def test_prompt_delete(api_db):
    pid = _first_prompt_id("qa")
    r = client.delete(f"/api/prompts/{pid}")
    assert r.status_code == 200
    r2 = client.delete(f"/api/prompts/{pid}")
    assert r2.status_code == 404


def test_prompt_config_get(api_db):
    r = client.get("/api/prompt-config")
    assert r.status_code == 200
    config = r.json()["config"]
    assert set(config) == {"qa", "code", "merge", "improve"}
    assert config["code"]["first"] is not None


def test_prompt_config_set(api_db):
    pid = _first_prompt_id("qa")
    r = client.post("/api/prompt-config", json={
        "pipeline": "qa", "stage": "subsequent", "prompt_id": pid,
    })
    assert r.status_code == 200
    config = r.json()["config"]
    assert config["qa"]["subsequent"] == pid


def test_prompt_config_set_clear(api_db):
    r = client.post("/api/prompt-config", json={
        "pipeline": "code", "stage": "first", "prompt_id": None,
    })
    assert r.status_code == 200
    assert r.json()["config"]["code"]["first"] is None


def test_prompt_config_unknown_pipeline(api_db):
    r = client.post("/api/prompt-config", json={
        "pipeline": "bad", "stage": "first", "prompt_id": 1,
    })
    assert r.status_code == 400


def test_prompt_config_wrong_pipeline_prompt(api_db):
    code_pid = _first_prompt_id("code")
    r = client.post("/api/prompt-config", json={
        "pipeline": "qa", "stage": "first", "prompt_id": code_pid,
    })
    assert r.status_code == 400


def test_credentials_prefill(api_db, monkeypatch):
    monkeypatch.setenv("DEEPSEEK_EMAIL", "deep@example.com")
    monkeypatch.setenv("DEEPSEEK_PASSWORD", "secret123")
    monkeypatch.setenv("QWEN_EMAIL", "qwen@example.com")
    monkeypatch.delenv("QWEN_PASSWORD", raising=False)
    r = client.get("/api/credentials")
    assert r.status_code == 200
    data = r.json()
    assert data["deepseek"]["email"] == "deep@example.com"
    assert data["deepseek"]["has_password"] is True
    assert data["qwen"]["email"] == "qwen@example.com"
    assert data["qwen"]["has_password"] is False
    body = r.text
    assert "secret123" not in body  # пароль не утекает


def test_health_has_session_messages(api_db):
    r = client.get("/api/health")
    assert r.status_code == 200
    data = r.json()
    assert isinstance(data["session_messages"], int)
