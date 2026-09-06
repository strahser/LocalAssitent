"""
Тесты чистых функций скрипта qwen_download_images (без selenium/браузера).
"""
import importlib.util
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

_SPEC = importlib.util.spec_from_file_location(
    "qwen_download_images",
    os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                 "scripts", "qwen_download_images.py"),
)
_mod = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_mod)


def test_make_filename_plain():
    assert _mod.make_filename(1788692438, 0, ".png") == "1788692438.png"


def test_make_filename_collision_suffix():
    assert _mod.make_filename(1788692438, 1, ".png") == "1788692438_1.png"
    assert _mod.make_filename(1788692438, 2, ".jpg") == "1788692438_2.jpg"


def test_guess_ext_by_content_type():
    assert _mod.guess_ext("image/png", "http://x/a.webp") == ".png"
    assert _mod.guess_ext("image/jpeg", "http://x/a") == ".jpg"
    assert _mod.guess_ext("image/webp", "http://x/a") == ".webp"


def test_guess_ext_by_url_fallback():
    assert _mod.guess_ext("", "http://x/a.JPG?x=1") == ".jpg"
    assert _mod.guess_ext("", "http://x/a") == ".png"


def test_is_skippable():
    assert _mod.is_skippable("", 800, 800, 256) is True
    assert _mod.is_skippable("data:image/svg+xml;base64,xx", 800, 800, 256) is True
    assert _mod.is_skippable("http://x/a.png", 64, 64, 256) is True
    assert _mod.is_skippable("http://x/a.png", 0, 900, 256) is False
    assert _mod.is_skippable("http://x/a.png", 1680, 900, 256) is False


def test_pick_source_prefers_fullsize_link():
    it = {"src": "http://x/thumb.png", "href": "http://x/full.png"}
    assert _mod.pick_source(it) == "http://x/full.png"
    it2 = {"src": "http://x/thumb.png", "href": "http://x/page.html"}
    assert _mod.pick_source(it2) == "http://x/thumb.png"
    it3 = {"src": "blob:http://x/1", "href": ""}
    assert _mod.pick_source(it3) == "blob:http://x/1"


def test_data_url_to_bytes():
    raw, header = _mod.data_url_to_bytes("data:image/png;base64,aGk=")
    assert raw == b"hi"
    assert "image/png" in header
