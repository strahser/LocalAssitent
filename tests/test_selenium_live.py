"""Live Selenium-тест: отправка сообщений с разными промптами из БД.

Подключается к ОТКРЫТОМУ браузеру (Edge debug, порт 9222, вкладка DeepSeek/Qwen),
отправляет сообщения с промптами qa / code / merge / improve из SQLite-базы
(webui.prompts_db) и проверяет получение ответов через штатную детекцию
(ResponseReader + CombinedStrategy).

ВАЖНО:
  - браузер должен быть запущен в debug-режиме (порт 9222) и открыт чат;
  - файлы НЕ отправляются (это ручная задача пользователя);
  - живёт отдельно от offline-набора: запуск `python tests/test_selenium_live.py`.

Запуск:
    python tests/test_selenium_live.py            # все промпты
    python tests/test_selenium_live.py qa code    # выбранные пайплайны
"""
import os
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from logger import Logger


def _logger() -> Logger:
    lg = Logger(
        log_to_html=False, log_to_file=False, save_responses=False,
        log_file="", html_file="",
    )
    return lg


def _make_client(lg):
    """Создаёт Qwen-клиент (вкладка Qwen открыта) с селекторами QWEN_SELECTORS.

    BrowserManager подключится к уже работающему порту 9222.
    """
    from config import SeleniumConfig, QWEN_URL, EDGE_USER_DATA_DIR
    from detection.qwen_selectors import QWEN_SELECTORS
    from agent.client import SeleniumQwenClient

    cfg = SeleniumConfig(
        debug_port=9222,
        edge_user_data_dir=EDGE_USER_DATA_DIR,
        deepseek_url=QWEN_URL,
        selenium_timeout=120,
        stable_timeout=90,
        stable_duration=1.5,
        check_interval=0.5,
        response_strategy="combined",
        selectors=QWEN_SELECTORS,
    )
    return SeleniumQwenClient(lg, cfg)


def _prompts_from_db(pipelines):
    """Возвращает {pipeline: content} — промпт stage='first' из БД."""
    from webui.prompts_db import ensure_initialized, get_prompt_for
    ensure_initialized()
    result = {}
    for p in pipelines:
        content = get_prompt_for(p, "first") or get_prompt_for(p, "both")
        if content:
            result[p] = content
    return result


def _brief(prompt: str, limit: int = 120) -> str:
    p = prompt.replace("\n", " ").strip()
    return p[:limit] + ("…" if len(p) > limit else "")


def run_live(pipelines, per_pipeline_timeout=150):
    lg = _logger()
    lg.log("🔌 Подключение к открытому браузеру (порт 9222)...")
    client = _make_client(lg)

    prompts = _prompts_from_db(pipelines)
    if not prompts:
        lg.log("❌ В БД нет промптов для выбранных пайплайнов.", "ERROR")
        client.close()
        return 1

    lg.log(f"📚 Промпты из БД: {', '.join(prompts.keys())}")
    results = {}
    for pipeline, prompt in prompts.items():
        q = f"Тест пайплайна {pipeline}: ответь кратко, одним предложением."
        lg.log(f"\n{'='*60}\n🔄 Пайплайн: {pipeline}\n📝 Промпт: {_brief(prompt)}\n❓ Вопрос: {q}")
        t0 = time.time()
        try:
            full, code = client.send_message(f"{prompt}\n\n{q}")
            elapsed = time.time() - t0
            if full:
                results[pipeline] = {"ok": True, "len": len(full), "sec": round(elapsed, 1)}
                lg.log(f"✅ {pipeline}: ответ {len(full)} симв. за {elapsed:.1f}с")
            else:
                results[pipeline] = {"ok": False, "error": "пустой ответ"}
                lg.log(f"❌ {pipeline}: пустой ответ", "ERROR")
        except Exception as e:
            elapsed = time.time() - t0
            results[pipeline] = {"ok": False, "error": str(e)[:200]}
            lg.log(f"❌ {pipeline}: ошибка за {elapsed:.1f}с: {e}", "ERROR")
        # пауза между сообщениями, чтобы чат не зафлудить
        time.sleep(3)

    client.close()
    lg.log("\n" + "=" * 60)
    lg.log("📊 ИТОГОВЫЙ ОТЧЁТ")
    all_ok = True
    for pipeline, r in results.items():
        if r.get("ok"):
            lg.log(f"  ✅ {pipeline}: OK, {r['len']} симв., {r['sec']}с")
        else:
            all_ok = False
            lg.log(f"  ❌ {pipeline}: FAIL — {r.get('error', '?')}")
    lg.log(f"\nРезультат: {'ВСЕ ПРОЙДЕНЫ' if all_ok else 'ЕСТЬ ОШИБКИ'}")
    return 0 if all_ok else 2


if __name__ == "__main__":
    args = sys.argv[1:]
    pipes = args if args else ["qa", "code", "merge", "improve"]
    sys.exit(run_live(pipes))
