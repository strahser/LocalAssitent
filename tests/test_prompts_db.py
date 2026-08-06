"""Tests for webui/prompts_db.py (SQLite: нормализация, CRUD, сидинг, выбор промпта).

Все тесты офлайн: tmp-БД через PromptsDB(tmp_path / "db.sqlite").
Запуск:  py -m pytest tests/test_prompts_db.py -q
"""
import os
import sqlite3
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest

import webui.prompts_db as pdb


@pytest.fixture()
def db(tmp_path):
    return pdb.PromptsDB(str(tmp_path / "db.sqlite"))


def _names(prompts):
    return {p["name"] for p in prompts}


def test_schema_and_seeding(db):
    config = db.get_prompt_config()
    assert set(config) == {"qa", "code", "merge", "improve"}
    prompts = db.get_all_prompts()
    names = _names(prompts)
    assert "default code" in names
    assert "default qa" in names
    assert "default merge" in names
    assert "default improve analyze" in names
    assert "default improve review" in names
    # prompt_config: first назначен для code/qa/merge/improve, subsequent — для improve
    assert config["code"]["first"] is not None
    assert config["qa"]["first"] is not None
    assert config["merge"]["first"] is not None
    assert config["improve"]["first"] is not None
    assert config["improve"]["subsequent"] is not None


def test_create_and_get_all(db):
    p = db.create_prompt("qa", "both", "qa context", "Отвечай кратко.")
    assert p["id"] > 0
    assert p["pipeline"] == "qa"
    assert p["stage"] == "both"
    assert p["is_active"] == 1
    ids = [x["id"] for x in db.get_all_prompts()]
    assert p["id"] in ids


def test_create_invalid_stage(db):
    with pytest.raises(ValueError):
        db.create_prompt("qa", "middle", "x", "y")


def test_create_unknown_pipeline(db):
    with pytest.raises(ValueError):
        db.create_prompt("bad", "first", "x", "y")


def test_create_empty_name(db):
    with pytest.raises(ValueError):
        db.create_prompt("qa", "first", "   ", "y")


def test_create_duplicate_unique(db):
    with pytest.raises(ValueError):
        db.create_prompt("qa", "first", "default qa", "other content")


def test_update_prompt(db):
    pid = db.create_prompt("qa", "subsequent", "qa follow-up", "old")["id"]
    updated = db.update_prompt(pid, name="qa follow-up v2", content="new", is_active=0)
    assert updated["name"] == "qa follow-up v2"
    assert updated["content"] == "new"
    assert updated["is_active"] == 0
    row = [p for p in db.get_all_prompts() if p["id"] == pid][0]
    assert row["content"] == "new"


def test_update_prompt_partial_keeps_other_fields(db):
    pid = db.create_prompt("qa", "both", "keep-me", "content A", is_active=1)["id"]
    updated = db.update_prompt(pid, name="renamed")  # только name — остальное не трогаем
    assert updated["name"] == "renamed"
    assert updated["content"] == "content A"
    assert updated["is_active"] == 1


def test_update_prompt_not_found(db):
    assert db.update_prompt(99999, name="x") is None


def test_update_unknown_field(db):
    with pytest.raises(ValueError):
        db.update_prompt(1, bogus_field="x")


def test_delete_prompt(db):
    pid = db.create_prompt("merge", "both", "merge ctx", "merge content")["id"]
    assert db.delete_prompt(pid) is True
    assert db.delete_prompt(pid) is False


def test_delete_clears_config_reference(db):
    cfg = db.get_prompt_config()
    pid = cfg["code"]["first"]
    assert db.delete_prompt(pid) is True
    cfg2 = db.get_prompt_config()
    assert cfg2["code"]["first"] is None


def test_get_prompt_for_first_from_config(db):
    content = db.get_prompt_for("code", "first")
    assert content and "Ты — агент для рефакторинга" in content


def test_get_prompt_for_unconfigured_returns_none(db):
    # merge сконфигурирован по умолчанию; сбросим конфиг и удалим промпты
    db.set_prompt_config("merge", "first", None)
    db.set_prompt_config("merge", "subsequent", None)
    for p in db.get_all_prompts():
        if p["pipeline"] == "merge":
            db.delete_prompt(p["id"])
    assert db.get_prompt_for("merge", "first") is None
    assert db.get_prompt_for("merge", "subsequent") is None


def test_get_prompt_for_both_fallback(db):
    # сбросим конфиг merge, создадим both-промпт → фолбэк на both
    db.set_prompt_config("merge", "first", None)
    db.set_prompt_config("merge", "subsequent", None)
    db.create_prompt("merge", "both", "merge default", "Контекст проекта.")
    assert db.get_prompt_for("merge", "first") == "Контекст проекта."
    assert db.get_prompt_for("merge", "subsequent") == "Контекст проекта."


def test_get_prompt_for_inactive_skipped(db):
    db.set_prompt_config("merge", "first", None)
    db.set_prompt_config("merge", "subsequent", None)
    for p in db.get_all_prompts():
        if p["pipeline"] == "merge":
            db.delete_prompt(p["id"])
    db.create_prompt("merge", "both", "merge default", "Контекст проекта.", is_active=0)
    assert db.get_prompt_for("merge", "first") is None


def test_get_prompt_for_unknown_pipeline(db):
    assert db.get_prompt_for("nope", "first") is None


def test_set_prompt_config(db):
    pid = db.create_prompt("qa", "subsequent", "qa follow-up", "Подробнее.")["id"]
    cfg = db.set_prompt_config("qa", "subsequent", pid)
    assert cfg["qa"]["subsequent"] == pid
    assert db.get_prompt_for("qa", "subsequent") == "Подробнее."


def test_set_prompt_config_clear(db):
    cfg = db.get_prompt_config()
    pid = cfg["qa"]["first"]
    db.set_prompt_config("qa", "first", None)
    assert db.get_prompt_config()["qa"]["first"] is None
    db.set_prompt_config("qa", "first", pid)  # вернуть обратно


def test_set_prompt_config_unknown_pipeline(db):
    with pytest.raises(ValueError):
        db.set_prompt_config("bad", "first", 1)


def test_set_prompt_config_wrong_pipeline_prompt(db):
    cfg = db.get_prompt_config()
    code_pid = cfg["code"]["first"]
    with pytest.raises(ValueError):
        db.set_prompt_config("qa", "first", code_pid)


def test_set_prompt_config_rejects_both(db):
    with pytest.raises(ValueError):
        db.set_prompt_config("qa", "both", 1)


def test_foreign_key_blocks_pipeline_delete(db):
    conn = sqlite3.connect(db.db_path)
    try:
        conn.execute("PRAGMA foreign_keys = ON")
        row = conn.execute("SELECT id FROM pipelines WHERE key='code'").fetchone()
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute("DELETE FROM pipelines WHERE id=?", (row[0],))
    finally:
        conn.close()


def test_init_db_and_env_override(tmp_path, monkeypatch):
    pdb.reset_db()
    monkeypatch.setenv("LOCALASSISTANT_DB", str(tmp_path / "env_db.sqlite"))
    d = pdb.init_db()
    assert d.db_path == str(tmp_path / "env_db.sqlite")
    assert os.path.exists(d.db_path)
    assert d.get_all_prompts()  # сидинг отработал
    pdb.reset_db()
    monkeypatch.delenv("LOCALASSISTANT_DB", raising=False)


def test_module_functions_use_initialized_db(tmp_path, monkeypatch):
    monkeypatch.setenv("LOCALASSISTANT_DB", str(tmp_path / "mod_db.sqlite"))
    pdb.reset_db()
    prompts = pdb.get_all_prompts()
    assert prompts, "сеяние через модульные функции"
    assert pdb.get_prompt_for("code", "first")
    pdb.reset_db()
    monkeypatch.delenv("LOCALASSISTANT_DB", raising=False)
