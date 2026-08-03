# Mission: Qwen.ai drag-and-drop task flow + HTML stage monitoring + tests

## M1: Qwen package (html monitor + dnd uploader + client) | status: completed
### T1.1: qwen/html_monitor.py | agent:Worker | status: completed
- [x] S1.1.1: HtmlSnapshot + HtmlChangeMonitor (fingerprint, wait_for_change, wait_for_stable, stage log) | size:L | verified
### T1.2: qwen/dnd_uploader.py | agent:Worker | status: completed
- [x] S1.2.1: DragAndDropUploader (base64 File + DragEvent dispatch, fallback input) | size:M | verified
### T1.3: qwen/selectors.py | agent:Worker | status: completed
- [x] S1.3.1: QWEN_SELECTORS (textarea, send, copy button, thinking, file chip markers) | size:S | verified
### T1.4: qwen/client.py | agent:Worker | status: completed
- [x] S1.4.1: QwenClient flow: open → dnd file → fixate received → prompt → fixate thinking → fixate ready → copy answer | size:L | verified
- [x] S1.4.2: qwen/__init__.py | size:S | verified
### T1.5: scripts/qwen_task.py | agent:Worker | status: completed
- [x] S1.5.1: CLI runner (--file --prompt --output --port --url) | size:M | verified

## M2: Tests | status: completed
### T2.1: tests/test_qwen_html_monitor.py | agent:Worker | status: completed
- [x] S2.1.1: fingerprint/change/stable/stage-log tests (FakeDriver) | size:M | verified
### T2.2: tests/test_qwen_dnd_uploader.py | agent:Worker | status: completed
- [x] S2.2.1: base64+File+DragEvent script, upload_file path | size:M | verified
### T2.3: tests/test_qwen_client.py | agent:Worker | status: completed
- [x] S2.3.1: full flow with mocked driver → answer file written | size:M | verified

## M3: Verification | status: completed
### T3.1: Full pytest suite + Reviewer | agent:Reviewer | depends:M1,M2 | status: completed
- [x] S3.1.1: python -m pytest tests -q green | size:M | verified
- [x] S3.1.2: AGENTS.md updated with qwen commands | size:S | verified
