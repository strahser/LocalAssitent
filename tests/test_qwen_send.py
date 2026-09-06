"""Тесты парсера скрипта qwen_send (без selenium/браузера)."""
import importlib.util
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

_SPEC = importlib.util.spec_from_file_location(
    "qwen_send",
    os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                 "scripts", "qwen_send.py"),
)
_mod = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_mod)


def test_parser_requires_text_file():
    try:
        _mod.build_parser().parse_args([])
    except SystemExit as e:
        assert e.code == 2
    else:
        raise AssertionError("text-file должен быть обязательным")


def test_parser_defaults():
    a = _mod.build_parser().parse_args(["--text-file", "p.txt"])
    assert a.port == 9222
    assert a.tab == "chat.qwen.ai"
    assert a.timeout == 30
    assert a.no_verify is False
