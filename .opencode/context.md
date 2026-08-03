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