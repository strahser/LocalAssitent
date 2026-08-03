# Project Context

## Environment
- Language: Python 3.10+ (local: 3.13)
- Package Manager: pip (requirements.txt)
- Test: pytest + pytest-mock (also standalone unittest-style runners)
- Entry: main.py (--scenario code|text|merge)

## Project Type
- Application (CLI, local AI assistant)
- Automates DeepSeek Chat via Selenium + Edge CDP browser

## Structure
- agent/       - Selenium DeepSeek client (BrowserManager, handlers)
- detection/   - DOM element finders, selectors
- tools/       - merge_docs, search, read/write/execute, safety
- scripts/     - utility scripts
- tests/       - pytest unit tests
- docs/        - CHANGELOG, IMPLEMENTATION_REPORT, IMPROVEMENT_PLAN
- prompts/     - AI prompt files

## Conventions
- Modules import-safe (guard network/browser deps so import works offline)
- tests/ use `sys.path.insert` to repo root, then `from tools... import ...`
- Two test styles: pytest (test_merge_docs) and unittest (test_safety)
- Russian docstrings/comments common; code identifiers English
- merge_docs.py already excludes `.opencode`
- Typos in codebase ("assitent", "merge_docs") — do not silently rename public APIs

## Notes
- Commit + push to branch `v1` (origin: https://github.com/strahser/LocalAssitent)
- Local Ollama can be reached at http://localhost:11434 (optional dep; keep tests offline-safe)

## Current Status (2026-08-03, qwen mission)
Mission: автономный приём для chat.qwen.ai — drag-and-drop файла-задания, мониторинг HTML (fingerprint sha256) для фиксации этапов (файл получен → думание → ответ + кнопка «Копировать»), сохранение ответа.
- M1 DONE: пакет `qwen/` создан (html_monitor.py, dnd_uploader.py, selectors.py, client.py, __init__.py) + `scripts/qwen_task.py`. `imports OK`, `--help` работает.
- M2: написаны 3 тест-файла: tests/test_qwen_html_monitor.py, tests/test_qwen_dnd_uploader.py, tests/test_qwen_client.py (FakeDriver/FakeElement/FakeLogger — офлайн, без selenium).
- Последний прогон: 34 passed, 5 failed. 2 уже исправлены (HtmlSnapshot("fp",0,{}) + assert '"#main"' in script). Осталось исправить 3 в test_qwen_client.py.

## Pending Tasks
1. Fix 3 failures in tests/test_qwen_client.py:
   - FakeDriver.execute_script: обработать nativeSetter (setattr(args[0],"_value",args[1])) и "arguments[0].value" (return getattr(args[0],"_value","")) — иначе send_prompt падает "текст не вставлен" (падает test_send_prompt_inserts_and_sends и test_run_task_full_flow).
   - test_extract_answer_copy_button_clipboard: client.py делает `from agent.clipboard import ClipboardManager` ВНУТРИ extract_answer → патчить надо agent.clipboard.ClipboardManager.get_text (staticmethod), а не qwen.client.ClipboardManager.
2. Прогнать: python -m pytest tests/test_qwen_*.py -q → потом полный suite python -m pytest tests -q (ожидается зелёный: старые 51 + новые).
3. M3: обновить AGENTS.md (добавить команды qwen: `python scripts/qwen_task.py --file ... --prompt ...`, тесты test_qwen_*.py).
4. Отметить [x] в .opencode/todo.md (только Reviewer), закоммитить + запушить на origin/v1.

## Known Pitfalls (этой сессии)
- Длинные delegate_task промпты обрезаются (JSON parse error) → писать файлы напрямую (write) или короткие промпты.
- Фоновые Worker-задачи возвращают "(No output)" при финише, хотя файлы создаются → всегда проверять фактическое состояние файлов.
- Temp-файл C:\Users\Strakhov\AppData\Local\Temp\opencode\qwen_smoke.py с LSP-ошибками импортов — временный артефакт Worker, не трогать.