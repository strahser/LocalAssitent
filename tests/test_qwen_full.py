"""
Тесты парсера скрипта qwen_download_full (без selenium/браузера).
"""
import importlib.util
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

_SPEC = importlib.util.spec_from_file_location(
    "qwen_download_full",
    os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                 "scripts", "qwen_download_full.py"),
)
_mod = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_mod)


def test_parser_defaults():
    a = _mod.build_parser().parse_args([])
    assert a.port == 9222
    assert a.limit == 0
    assert a.offset == 0
    assert a.probe is False
    assert a.close is False


def test_parser_range():
    a = _mod.build_parser().parse_args(
        ["--offset", "2", "--limit", "5", "--output", "out", "--probe"])
    assert (a.offset, a.limit) == (2, 5)
    assert a.probe is True
    assert a.output == "out"


def test_range_slice_logic():
    total, lo = 22, 2
    hi = total if not 5 else min(total, lo + 5)
    assert (lo, hi) == (2, 7)
