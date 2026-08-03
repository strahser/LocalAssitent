# AGENTS.md

## Commands
- Install: `pip install -r requirements.txt`
- Run scenarios: `python main.py --scenario code|text|merge` (entry: main.py; config via config.py CLI)
- Merge docs tool: `python tools/merge_docs.py <dir> --ext .cs .py --output out.txt`
- Pipeline: `python pipeline.py` → writes `pipeline_output/deepseek_analysis.md`
- Tests: `python -m pytest tests -q` (pytest style)
- Standalone runners: `python tests/test_merge_docs.py`, `python tests/test_safety.py` (unittest-style self-runners, runnable directly)
- New agent tests: `python -m pytest tests/test_agents.py -v`

## Structure
- `agent/` — Selenium DeepSeek client (BrowserManager, handlers/, auth, clipboard)
- `detection/` — DOM element finders + selectors (element_finder.py, selectors.py, response_ready.py, action_panel.py)
- `tools/` — merge_docs, search (grep_search/glob_search), read_file, write_file, execute, safety, list_dir
- `agents/` — pluggable local agents (web_search, page_parser, local_data, qa, browser, merge); BaseAgent in agents/base.py
- `scripts/`, `tests/`, `docs/`, `prompts/`

## Agent CLI
- `python -m agents --list`
- `python -m agents <name> --query "..."`

## Conventions
- tests/ prepend repo root to sys.path, then `from tools.X import Y`
- Modules guard heavy imports (network/browser) at module level so import works offline
- Russian docstrings/comments common; English identifiers
- Do NOT rename public APIs despite typos ("LocalAssitent", "merge_docs")
- tools/merge_docs.py excludes `.opencode` and `__pycache__` dirs by default
- Local Ollama optional at http://localhost:11434 — agents must degrade gracefully offline

## Gotchas
- Browser automation requires Edge with remote debugging on port 9222 (config DEBUG_PORT, EDGE_USER_DATA_DIR)
- Auth via DEEPSEEK_EMAIL / DEEPSEEK_PASSWORD env vars (see .env.example)
- Windows: use `python -m pytest` (scripts may not be on PATH)
