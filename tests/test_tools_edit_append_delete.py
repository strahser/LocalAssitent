"""Тесты новых инструментов edit_file / append_file / delete_file (офлайн)."""
from __future__ import annotations

import pytest

import tools.safety as safety
from tools.append_file import append_file
from tools.delete_file import delete_file
from tools.edit_file import edit_file


@pytest.fixture
def sandbox(tmp_path, monkeypatch):
    """Переносит корень проекта во временный каталог."""
    patched = False
    for attr in list(vars(safety)):
        upper = attr.upper()
        if "ROOT" in upper or upper in ("BASE_DIR", "BASEDIR"):
            monkeypatch.setattr(safety, attr, str(tmp_path))
            patched = True
    if not patched:
        monkeypatch.setattr(safety, "PROJECT_ROOT", str(tmp_path), raising=False)
    return tmp_path


# === edit_file ===


def test_edit_file_replaces_first_occurrence(sandbox):
    (sandbox / "a.txt").write_text("hello hello\n", encoding="utf-8")
    result = edit_file("a.txt", "hello", "bye")
    assert result.startswith("OK")
    assert (sandbox / "a.txt").read_text(encoding="utf-8") == "bye hello\n"


def test_edit_file_creates_with_force(sandbox):
    result = edit_file("new.txt", "", "content\n", force=True)
    assert result.startswith("OK")
    assert (sandbox / "new.txt").read_text(encoding="utf-8") == "content\n"


def test_edit_file_missing_file_without_force(sandbox):
    result = edit_file("nope.txt", "a", "b")
    assert result.startswith("Ошибка")


def test_edit_file_old_text_not_found(sandbox):
    (sandbox / "a.txt").write_text("abc\n", encoding="utf-8")
    result = edit_file("a.txt", "zzz", "b")
    assert result.startswith("Ошибка")
    assert (sandbox / "a.txt").read_text(encoding="utf-8") == "abc\n"


def test_edit_file_appends_when_old_text_empty(sandbox):
    (sandbox / "a.txt").write_text("head\n", encoding="utf-8")
    result = edit_file("a.txt", "", "tail\n")
    assert result.startswith("OK")
    assert (sandbox / "a.txt").read_text(encoding="utf-8") == "head\ntail\n"


# === append_file ===


def test_append_file_appends_to_existing(sandbox):
    (sandbox / "b.txt").write_text("hello\n", encoding="utf-8")
    result = append_file("b.txt", "world\n")
    assert result.startswith("OK")
    assert (sandbox / "b.txt").read_text(encoding="utf-8") == "hello\nworld\n"


def test_append_file_creates_when_missing(sandbox):
    result = append_file("newdir/note.txt", "data\n")
    assert result.startswith("OK")
    assert (sandbox / "newdir" / "note.txt").read_text(encoding="utf-8") == "data\n"


def test_append_file_no_create_when_missing(sandbox):
    result = append_file("missing.txt", "data\n", create=False)
    assert result.startswith("Ошибка")
    assert not (sandbox / "missing.txt").exists()


# === delete_file ===


def test_delete_file_removes_file(sandbox):
    f = sandbox / "del.txt"
    f.write_text("x\n", encoding="utf-8")
    result = delete_file("del.txt")
    assert result.startswith("OK")
    assert not f.exists()


def test_delete_file_missing_returns_error(sandbox):
    result = delete_file("absent.txt")
    assert result.startswith("Ошибка")


def test_delete_file_refuses_directory(sandbox):
    (sandbox / "adir").mkdir()
    result = delete_file("adir")
    assert result.startswith("Ошибка")
    assert (sandbox / "adir").is_dir()


# === безопасность ===


def test_real_safe_join_rejects_escape():
    with pytest.raises(ValueError):
        safety.safe_join("../escape_from_root.txt")


def test_tool_path_escape_rejected(sandbox):
    with pytest.raises(ValueError):
        append_file("../escape.txt", "x\n")