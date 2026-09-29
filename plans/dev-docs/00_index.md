# DevAgent — Developer Documentation Index

Private reference notes. Not tracked in git (`dev-docs/` is gitignored).

Last updated: 2026-08-21

---

## Files

| File | What it covers |
|---|---|
| [01_architecture_overview.md](01_architecture_overview.md) | Package layout, component relationships, key design decisions, data stores |
| [02_data_flow.md](02_data_flow.md) | Request → loop → LLM → tools → response; token budget flow; persistence flow; CodePrism injection; auto-repair flow; REST API flow |
| [03_user_flow.md](03_user_flow.md) | First-time setup, indexing, interactive session, session resume, GitHub implement/review/triage, background watcher, doctor |
| [04_command_flow.md](04_command_flow.md) | Every CLI command: what it calls, what it returns, internal steps |
| [05_agent_loop.md](05_agent_loop.md) | ReAct iteration state machine, event types, auto-repair loop, router selection, message construction, error handling |
| [06_session_and_memory.md](06_session_and_memory.md) | SQLite schema, session lifecycle, event roles, build_messages(), MemoryBlock, TokenBudget, database locations |
| [07_tool_system.md](07_tool_system.md) | ToolRegistry, SecurityGate (BLOCK/WARN/PASS), all 29 built-in tools, plugin tool guide, output size conventions |
| [08_llm_and_config.md](08_llm_and_config.md) | LLMClient abstraction, provider normalisation, get_llm_for_task, config hierarchy, TOML format, token rates, fallback chain |
| [09_watcher_and_github.md](09_watcher_and_github.md) | Watcher architecture, scheduler loop, SQLite schema, conflict detector, GitHub API tool map, review flow, MCP manager, URL parser |
| [10_codeprism_integration.md](10_codeprism_integration.md) | CodePrismClient API, session overlay, get_module_summary, get_impact, graph index files, behaviour without CodePrism, token savings |

---

## Quick reference

### Constants to know

| Constant | File | Value |
|---|---|---|
| `MAX_ITERATIONS` | `agent/loop.py` | 30 |
| `MAX_REPAIR` | `agent/loop.py` | 3 |
| `_WRITE_TOOL_NAMES` | `agent/loop.py` | `{"write_file", "edit_file"}` |
| REST API port | `server/app.py` | 7331 |
| Session DB | `core/storage.py` | `<project>/.devagent/sessions.db` |
| Watcher DB | `watcher/storage.py` | `~/.devagent/watcher.db` |
| Config path | `core/storage.py` | platform-specific TOML |

### Task → model routing (default logic)

| Iteration / last tools | Task | Typical model assignment |
|---|---|---|
| Iteration 1 | `planning` | Strongest available (e.g. claude-sonnet-4-6) |
| write_file / edit_file used | `coding` | Precision model |
| cp_get_impact / git_diff used | `reviewing` | Review-capable model |
| read_file / grep / cp_* used | `cheap` | Small fast model (e.g. qwen2.5-coder:7b) |
| anything else | `fallback` | Default model |

### Tool categories

- **File:** read_file, write_file, edit_file, find_files, list_files
- **Shell:** run_shell
- **Git:** git_status, git_diff, git_log, git_show, git_commit
- **Search:** grep, web_search
- **GitHub:** github_get_issue, github_get_pr, github_list_issues, github_post_comment, github_post_review_comment, github_create_pr, github_create_branch, github_get_ci_log
- **CodePrism:** cp_get_context, cp_search_symbol, cp_get_module_summary, cp_get_callers, cp_get_callees, cp_get_file_map, cp_get_dependencies, cp_get_impact, cp_get_data_flow, cp_get_stats
- **Memory:** remember_fact, recall_facts, forget_fact

### Adding a new command

1. Add `@app.command()` function in `cli.py`
2. Import heavy dependencies inside the function body (not at top of file) to keep startup fast
3. Call `_handle_error(exc)` in the except block for user-friendly error display
4. Update `tests/test_phase6.py` if it's a public-facing command

### Adding a new tool

1. Write `handler(args: dict) -> str` function in the appropriate `tools/*.py` file
2. Call `registry.register(name, description, parameters, handler)` in `DevAgentSession.__init__` (or the relevant session builder)
3. Wrap with `security_gate.wrap(handler)` if the tool writes files
4. Add a test in `tests/test_tool_*.py`
