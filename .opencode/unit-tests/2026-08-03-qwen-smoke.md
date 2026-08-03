# Unit Test Record: qwen/ package smoke (ses_3)

- Date: 2026-08-03T12:49Z
- File: qwen_smoke_test.py (temporary, deleted after run)
- Driver: FakeDriver (no selenium, no network, no real clipboard — agent.clipboard injected via sys.modules)
- Result: **52/52 passed**, exit=0

## What was verified

### qwen/html_monitor.py (HtmlSnapshot + HtmlChangeMonitor)
- fingerprint: deterministic, changes with html, sha256 hex (64 chars)
- snapshot: text_len / html_len / markers / ts / to_dict keys
- wait_for_change: detects fingerprint change; detects marker flip (chip appears); timeout returns baseline
- wait_for_stable: returns snapshot when fingerprint stable + marker present (copy button)
- marker / marker_text: True/False/empty handling
- log_stage: writes "🏁 STAGE: ... (t=..., text_len=...)"

### qwen/dnd_uploader.py (DragAndDropUploader)
- guess_mime: .py -> text/x-python, .docx -> ...wordprocessingml.document, unknown -> octet-stream
- build_drop_script: contains atob(, Uint8Array, new File(, filename, text/plain, DataTransfer,
  dt.items.add(file), dragenter/dragover/drop, document.querySelector, document.body, return true
- upload: drop path (execute_script truthy) -> True; fallback path (falsy -> input[type=file] send_keys) -> True;
  missing file -> False

### qwen/client.py (QwenClient)
- run_task full flow with FakeDriver -> ok=True, answer non-empty, output file written with
  markdown header (# Ответ Qwen, дата, источник=filename), 3 stages logged, driver not quit (not owned)
- extract_answer fallback: assistant_message last element text
- save_answer: returns path

## Contract checks (permission from mission spec)
- `python -c "... from qwen.html_monitor import HtmlChangeMonitor; from qwen.dnd_uploader import DragAndDropUploader; from qwen.client import QwenClient; print('imports OK')"` -> imports OK
- `python scripts/qwen_task.py --help` -> exit=0

## Note on anomaly recovery
During the session an anomaly handler overwrote the qwen files with a non-contract
implementation (top-level selenium import in html_monitor, @staticmethod guess_mime,
missing selectors defaults, broken client with NameError: HtmlSnapshot). All files were
rewritten to the contract-compliant version and re-verified (imports OK, help exit=0, 52/52).
