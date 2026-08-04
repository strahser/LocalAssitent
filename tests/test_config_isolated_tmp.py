"""
Isolated test for T1.1 (M-4): multi-provider config in config.py.
Temp file — executed by Worker, deleted after Green. NOT part of the suite.
Runs standalone:  py tests/test_config_isolated_tmp.py
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import config


def _ns(**overrides):
    base = dict(
        list_scenarios=False, scenario=None, prompt=None, input=None, output=None,
        max_iterations=None, no_auto_send=False, files=None, paste_clipboard=False,
        new_chat=False, debug_port=9222, email=None, password=None,
        provider="deepseek", model=None, merge_dir=".", ext=None,
    )
    base.update(overrides)
    return argparse.Namespace(**base)


def test_providers_dict():
    assert "deepseek" in config.PROVIDERS
    assert "qwen" in config.PROVIDERS
    assert config.PROVIDERS["deepseek"]["url"] == "https://chat.deepseek.com"
    assert config.PROVIDERS["qwen"]["url"] == "https://chat.qwen.ai"


def test_qwen_models_default_first():
    assert config.QWEN_MODELS[0] == "Qwen3.8-Max-Preview"
    assert len(config.QWEN_MODELS) >= 3


def test_default_model_constant():
    assert config.DEFAULT_MODEL == "Qwen3.8-Max-Preview"


def test_deepseek_url_kept_working():
    assert config.DEEPSEEK_URL == "https://chat.deepseek.com"
    assert config.DEEPSEEK_URL == config.PROVIDERS["deepseek"]["url"]


def test_build_config_qwen_default_model():
    scenario, cfg, args = config.build_config(_ns(provider="qwen"))
    assert cfg["provider"] == "qwen"
    assert cfg["model"] == "Qwen3.8-Max-Preview"


def test_build_config_qwen_custom_model():
    scenario, cfg, args = config.build_config(_ns(provider="qwen", model="Qwen3-Max"))
    assert cfg["model"] == "Qwen3-Max"


def test_build_config_deepseek_defaults_unchanged():
    scenario, cfg, args = config.build_config(_ns())
    assert cfg["provider"] == "deepseek"
    assert cfg["model"] == "Qwen3.8-Max-Preview"
    assert cfg["email"] == os.environ.get("DEEPSEEK_EMAIL", "")


def test_qwen_env_fallback_precedence():
    old = {k: os.environ.get(k) for k in ("QWEN_EMAIL", "DEEPSEEK_EMAIL")}
    os.environ["QWEN_EMAIL"] = "q@test.com"
    os.environ["DEEPSEEK_EMAIL"] = "d@test.com"
    try:
        scenario, cfg, args = config.build_config(_ns(provider="qwen"))
        assert cfg["email"] == "q@test.com"
    finally:
        for k, v in old.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v


def test_deepseek_env_still_wins_without_qwen():
    old = {k: os.environ.get(k) for k in ("QWEN_EMAIL", "DEEPSEEK_EMAIL")}
    os.environ.pop("QWEN_EMAIL", None)
    os.environ["DEEPSEEK_EMAIL"] = "d@test.com"
    try:
        scenario, cfg, args = config.build_config(_ns(provider="deepseek"))
        assert cfg["email"] == "d@test.com"
    finally:
        for k, v in old.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v


def test_cli_parser_has_provider_model():
    old_argv = sys.argv
    sys.argv = ["config.py", "--provider", "qwen", "--model", "Qwen3-Max"]
    try:
        args = config.parse_args()
        assert args.provider == "qwen"
        assert args.model == "Qwen3-Max"
    finally:
        sys.argv = old_argv


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    failures = 0
    for fn in fns:
        try:
            fn()
            print(f"PASS {fn.__name__}")
        except Exception as e:
            failures += 1
            print(f"FAIL {fn.__name__}: {e}")
    print(f"\n{len(fns) - failures}/{len(fns)} passed")
    sys.exit(1 if failures else 0)
