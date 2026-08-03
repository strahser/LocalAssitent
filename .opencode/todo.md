# Mission: Deploy additional local agents + AGENTS.md + tests + commit/push

## M1: Scaffold + Documentation
### T1.1: Create AGENTS.md | agent:Worker
- [ ] S1.1.1: Write concise AGENTS.md with build/test/run/architecture facts | size:S

## M2: Implement New Agents (per Task_Editiona_Agents.txt, max count)
### T2.1: Agent framework package `agents/` | agent:Worker
- [ ] S2.1.1: agents/base.py (BaseAgent + AgentResult + registry) | size:M
- [ ] S2.1.2: agents/registry.py (discover/run agents by name) | size:S
### T2.2: Individual feature agents | agent:Worker
- [ ] S2.2.1: agents/web_search_agent.py (DuckDuckGo HTML search) | size:M
- [ ] S2.2.2: agents/page_parser_agent.py (fetch page, extract text/table) | size:M
- [ ] S2.2.3: agents/local_data_agent.py (local file keyword/semantic search) | size:M
- [ ] S2.2.4: agents/qa_agent.py (Ollama Q&A wrapper, offline-safe) | size:M
- [ ] S2.2.5: agents/browser_agent.py (Selenium navigation wrapper) | size:M
- [ ] S2.2.6: agents/merge_agent.py (wrap tools.merge_docs into agent interface) | size:S
### T2.3: CLI runner (python -m agents ...) | agent:Worker
- [ ] S2.3.1: agents/cli.py (argparse dispatch over registry) | size:M

### T2.4: Tests for new agents | agent:Worker | depends:T2.1,T2.2
- [ ] S2.4.1: tests/test_agents_base.py | size:M
- [ ] S2.4.2: tests/test_web_search_agent.py (mock transport) | size:M
- [ ] S2.4.3: tests/test_page_parser_agent.py (offline fixture HTML) | size:M
- [ ] S2.4.4: tests/test_local_data_agent.py | size:M
- [ ] S2.4.5: tests/test_qa_agent.py (mock requests) | size:M
- [ ] S2.4.6: tests/test_cli_registry.py | size:S

## M3: Verification (Reviewer) | status: completed
### T3.1: Run full pytest suite | agent:Reviewer | depends:T1,T2 | status: completed
- [x] S3.1.1: `python -m pytest tests -q` passes (old + new) | verified | evidence: 51 passed in 0.51s, exit=0
- [x] S3.1.2: Mark all subs verified; report results | verified | evidence: full system verification green (see work-log Verification section)

## M4: Commit + Push
### T4.1: Commit and push to GitHub | agent:Worker | depends:M3
- [ ] S4.1.1: git add .opencode/new files, AGENTS.md, agents/, tests | size:S
- [ ] S4.1.2: git commit with message | size:S
- [ ] S4.1.3: git push origin v1 | size:S
- [ ] S4.1.4: Confirm push (git status / ls-remote) | size:S