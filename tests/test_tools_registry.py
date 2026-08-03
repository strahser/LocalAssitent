"""Тесты реестра инструментов tools (офлайн, сеть не требуется)."""
from __future__ import annotations

import pytest

import tools  # noqa: F401 — импорт включает регистрацию всех инструментов
from tools.registry import get_tool, list_tools, register, run_tool


EXPECTED_TOOLS = (
    "append_file",
    "delete_file",
    "edit_file",
    "execute_code",
    "glob_search",
    "grep_search",
    "list_dir",
    "merge_documents",
    "read_file",
    "write_file",
)


@pytest.fixture
def sandbox(tmp_path, monkeypatch):
    """Временно объявляет корнем проекта временный каталог."""
    import tools.safety as safety

    patched = False
    for attr in list(vars(safety)):
        upper = attr.upper()
        if "ROOT" in upper or upper in ("BASE_DIR", "BASEDIR"):
            monkeypatch.setattr(safety, attr, str(tmp_path))
            patched = True
    if not patched:
        monkeypatch.setattr(safety, "PROJECT_ROOT", str(tmp_path), raising=False)
    return tmp_path


def test_list_tools_contains_all_expected():
    names = list_tools()
    assert isinstance(names, list)
    for expected in EXPECTED_TOOLS:
        assert expected in names


def test_get_tool_returns_callable():
    assert callable(get_tool("read_file"))
    assert callable(get_tool("grep_search"))


def test_get_tool_unknown_raises_keyerror():
    with pytest.raises(KeyError):
        get_tool("definitely_not_a_tool")


def test_run_tool_calls_registered_function(sandbox):
    result = run_tool("append_file", "hello.txt", "world\n")
    assert result.startswith("OK")
    assert (sandbox / "hello.txt").read_text(encoding="utf-8") == "world\n"


def test_run_tool_unknown_raises_keyerror():
    with pytest.raises(KeyError):
        run_tool("definitely_not_a_tool")


def test_register_decorator_registers_new_tool():
    @register("__test_tool")
    def __test_tool() -> str:
        return "ok"

    assert "__test_tool" in list_tools()
    assert run_tool("__test_tool") == "ok"


def test_existing_public_apis_still_importable():
    # старый API не должен пропасть из пакета tools
    assert callable(tools.read_file)
    assert callable(tools.write_file)
    assert callable(tools.grep_search)
    assert callable(tools.glob_search)
    assert callable(tools.list_dir)
    assert callable(tools.execute_code)
    assert callable(tools.merge_documents)
    assert callable(tools.safe_join)
    assert callable(tools.is_safe_path)


def test_new_tools_importable_from_package():
    assert callable(tools.edit_file)
    assert callable(tools.append_file)
    assert callable(tools.delete_file)
