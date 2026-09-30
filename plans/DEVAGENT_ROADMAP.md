# DevAgent — Complete Roadmap

> AI coding agent harness. Chat-session based. GitHub-native. Offline-first.
> Powered by CodePrism for token-efficient context. Open source.
>
> Current version: 1.5.0
> Status: Full agentic coding harness — shipped through Phase 43

---

## Vision

A developer opens a terminal, types `devagent`, and is in a persistent chat session
linked to their current repo. They say "implement issue #142" and the agent:

1. Reads the issue from GitHub
2. Queries CodePrism for the impact radius of the change — **no file searching**
3. Reads only the 4–6 files that matter
4. Makes targeted edits, with the Security Gate checking each write
5. Runs the relevant tests (found via CodePrism's `tests` edges)
6. Fixes failures iteratively until tests pass
7. Creates a branch, commits, opens a PR linked to the issue
8. Shows the user a diff and asks "ship it?"

All of this runs locally on Ollama if the user wants. Zero cloud required.

---

## Architecture (Target State)

```
┌─────────────────────────────────────────────────────────────────┐
│                    DevAgent CLI  (Typer + Rich)                 │
│           `devagent` → session REPL → streaming output          │
└──────────────────────────────┬──────────────────────────────────┘
                               │
┌──────────────────────────────▼──────────────────────────────────┐
│                    Session Manager                              │
│  Persistent sessions (SQLite) │ Session graph overlay           │
│  Action journal (undo/rollback) │ Token budget tracker          │
└────────┬─────────────────────────────────────┬──────────────────┘
         │                                     │
┌────────▼──────────────┐           ┌──────────▼──────────────────┐
│   Agent Loop          │           │   CodePrism (MCP)           │
│   ReAct pattern       │◄─tools───►│   Knowledge graph           │
│   Tool calling loop   │           │   Security Gate             │
│   LLM provider        │           │   Impact analysis           │
│   Multi-model router  │           │   Session overlay           │
└────────┬──────────────┘           └─────────────────────────────┘
         │
┌────────▼─────────────────────────────────────────────────────────┐
│                        Tool Registry                             │
│  file_read │ file_write │ shell_exec │ github_* │ test_runner   │
│  web_search │ codeprism_* │ git_* │ (extensible via plugins)    │
└─────────────────────────────────────────────────────────────────┘
```

---

## What to Keep from v0.3.0

| Component | Keep? | Notes |
|---|---|---|
| `core/config.py` | Yes | Add new config sections for agent loop, router |
| `core/llm.py` | Yes | Extend with multi-model router |
| `core/storage.py` | Yes | Add session storage path |
| `core/project.py` | Yes | Unchanged |
| `core/url_parser.py` | Yes | Unchanged |
| `core/models.py` | Partial | Keep GapReport, add Agent/Session models |
| `cli.py` | Refactor | New primary command: `devagent` (session REPL) |
| `mcp/manager.py` | Refactor | Drop custom Python MCP servers, add CodePrism |
| `mcp/clients/github_client.py` | Extend | Add PR, branch, commit operations |
| `agents/pipeline.py` | Archive | Replaced by ReAct loop; keep as `analyze` subcommand |
| `chat/session.py` | Refactor | Becomes core of the new agent loop |
| `chat/context.py` | Replace | Context now comes from CodePrism, not GapReport |
| `chat/history.py` | Keep | Extend with structured session memory |
| `output/terminal.py` | Keep | Extend with streaming output |
| `watcher/` | Keep | Extend with agent-loop integration |
| `mcp/servers/code_search/` | Deprecate | CodePrism replaces this entirely |
| `mcp/servers/spec_analysis/` | Archive | Keep as optional `analyze` subcommand |

---

## Phase 0 — Cleanup & Foundation (Week 1)

**Goal:** Clean repo, establish new conventions, prepare for the agent loop.

### Tasks

- [ ] Add `codeprism` as a dependency in `pyproject.toml`
- [ ] Remove `mcp/servers/code_search/` (replaced by CodePrism)
- [ ] Archive `agents/pipeline.py` as `agents/legacy_pipeline.py` (keep `analyze` command working)
- [ ] Add new config sections to `core/config.py`:
  - `AgentConfig` (max_iterations, confirmation_required, stream_thoughts)
  - `RouterConfig` (provider per task type: planning, coding, review, cheap)
  - `SessionConfig` (auto_resume, max_sessions, session_storage_path)
  - `SecurityConfig` (gate_enabled, block_on_secrets, warn_on_weak_crypto)
  - `TokenBudgetConfig` (session_cap_usd, warn_at_percent, track_by_model)
- [ ] Add session storage table to SQLite schema
- [ ] Add new Pydantic models: `AgentSession`, `SessionEvent`, `ToolCall`, `ToolResult`
- [ ] Restructure CLI: `devagent` (REPL, primary), `devagent analyze` (legacy one-shot)
- [ ] Update README to reflect new direction

### Deliverable
Clean codebase with new config schema. All existing tests still pass.
`devagent analyze` still works identically to v0.3.0.

---

## Phase 1 — Core Agent Loop (Weeks 2–3)

**Goal:** A working ReAct tool-calling loop. The agent can read files, execute
commands, and have a real conversation about them.

### The Loop

```
while iteration < max_iterations:
    response = llm.call(system_prompt, history, tools=tool_registry)
    
    if response.is_text_only:
        stream_to_terminal(response.text)
        user_input = wait_for_input()
        history.append(user_input)
        
    elif response.is_tool_call:
        stream_to_terminal(f"→ {tool.name}({tool.args})")  # show thought
        result = await tool_registry.execute(tool.name, tool.args)
        history.append(tool_result)
        
    elif response.is_done:
        break
```

### Tools to Implement (Phase 1)

```python
# File operations
file_read(path: str, start_line: int = None, end_line: int = None) -> str
file_write(path: str, content: str) -> WriteResult   # goes through Security Gate
file_edit(path: str, old_str: str, new_str: str) -> EditResult  # precise diff edit
file_list(path: str, pattern: str = None) -> list[str]
file_delete(path: str) -> bool

# Shell execution
shell_exec(command: str, cwd: str = None, timeout: int = 30) -> ShellResult
  # Returns: stdout, stderr, exit_code, duration_ms
  # Has a blocklist: rm -rf /, git push --force to main, DROP TABLE, etc.

# Search (non-CodePrism fallback)
text_search(pattern: str, path: str = ".", file_glob: str = None) -> list[Match]

# Git operations
git_status() -> str
git_diff(file: str = None) -> str
git_log(n: int = 10) -> list[Commit]
git_branch_create(name: str) -> bool
git_commit(message: str, files: list[str] = None) -> CommitResult
git_checkout(branch: str) -> bool
```

### Session Persistence

Every session is stored in SQLite:
```
sessions/
  <session_id>/
    metadata.json    (repo, branch, created_at, last_active_at, task_description)
    history.json     (full conversation history as LangChain messages)
    journal.json     (ordered list of all tool calls + results + undo snapshots)
    token_usage.json (per-model token counts and estimated cost)
```

`devagent` with no args: shows last 5 sessions, offers resume or new session.
`devagent --resume <id>`: resumes a session.
`devagent --new "implement issue #142"`: starts a new session with a task.

### Streaming Output

All LLM output streams character-by-character using Rich Live. Tool calls are
shown as they happen:

```
┌─ DevAgent ──────────────────────────────────────────────────────────────┐
│ Looking at the authentication module to understand the current flow...  │
│                                                                         │
│ → file_read("auth/middleware.py")                                       │
│   ✓ 142 lines read                                                      │
│                                                                         │
│ I can see the issue. The middleware is checking the token in the wrong  │
│ order. Let me fix that.                                                 │
│                                                                         │
│ → file_edit("auth/middleware.py", ...)                                  │
│   ⚠ Security Gate: WARN — new external call on line 47, review import  │
│   Proceed? [y/N]:                                                       │
└─────────────────────────────────────────────────────────────────────────┘
```

### Token Budget Tracker

Every LLM call records: model, input_tokens, output_tokens, cost_usd.
Shown in the session status bar:

```
[session: sess_abc] [tokens: 12.4k / 100k] [cost: $0.023 / $0.50] [iter: 8/50]
```

When budget is at 80%: warning shown. At 100%: agent finishes current thought
and stops, asks user what to do.

### Deliverable
`devagent` opens a session. User can say "read auth/middleware.py and explain it"
and the agent reads the file and explains it. Sessions persist across terminal restarts.
Token budget is tracked live.

---

## Phase 2 — CodePrism Integration (Weeks 4–5)

**Goal:** Replace all file searching with CodePrism graph queries. Token usage
drops dramatically.

### New CodePrism Tools (added to tool registry)

```python
# Context (replaces file_read for understanding)
cp_get_context(file: str, symbol: str, depth: int = 2) -> ContextResult
cp_get_module_summary(file: str) -> ModuleSummary
cp_get_file_map() -> FileMap           # whole-project map, ~500 tokens

# Impact (pre-edit analysis)
cp_get_impact(file: str, symbol: str) -> ImpactResult
cp_get_callers(file: str, function: str) -> list[Caller]
cp_get_callees(file: str, function: str) -> list[Callee]
cp_get_data_flow(file: str, symbol: str) -> DataFlowResult

# Symbol lookup
cp_search_symbol(query: str, kind: str = None) -> list[Symbol]
cp_get_dependencies(file: str) -> DependencyResult

# Session overlay
cp_record_write(file: str, before: str, after: str) -> SecurityReport
cp_get_session_context() -> str        # compact summary of this session
cp_undo(steps: int = 1) -> UndoResult
```

### Session Graph Overlay

At the start of every agent iteration, inject into the system prompt:
```
## What you know this session:
- Read: auth/middleware.py (focus: verify_token function)
- Wrote: auth/middleware.py (fixed token order check — tests passed)
- Read via graph: 6 symbols in auth/ module
- Session token budget: 23.1k used, 76.9k remaining
```

This replaces re-reading the full conversation history on every turn and reduces
context window usage significantly.

### Impact Scope Estimator (Pre-Edit)

Before any `file_edit` or `file_write`, the agent automatically calls
`cp_get_impact()` and shows the result:

```
┌─ Impact Analysis ───────────────────────────────────────────────────────┐
│ Changing: auth/middleware.py::verify_token                              │
│                                                                         │
│ Direct dependents (3):  api/routes.py, api/websocket.py, tests/auth    │
│ Transitive dependents (8):  ... 5 more files                           │
│ Severity: MEDIUM — public API affected                                  │
│ Test files to run: tests/test_auth.py, tests/test_api.py               │
└─────────────────────────────────────────────────────────────────────────┘
```

### Codebase Onboarding Mode

```bash
devagent onboard          # analyze current project and produce orientation
```

Uses CodePrism to generate:
- Architecture overview (entry points, key modules, data flow)
- "Most complex" files by CodePrism complexity score
- "Most depended-upon" symbols (highest in-degree in the graph)
- Suggested reading order for a new contributor
- Test coverage gaps

### Deliverable
`devagent` uses CodePrism for all context retrieval. Benchmark showing token
reduction vs v0.3.0 included in README. Onboarding mode works.

---

## Phase 3 — Security Gate Integration (Week 6)

**Goal:** Every file write is security-checked. No secrets can be committed
through the agent.

### Security Gate Flow

```python
# In file_write tool:
async def file_write(path: str, content: str) -> WriteResult:
    report = await security_gate.check(path, original_content, content)
    
    if report.status == "BLOCK":
        return WriteResult(
            success=False,
            blocked_by=report.issues,
            explanation=report.explanation
        )
    
    if report.status == "WARN":
        # Stream warning to terminal, wait for user confirmation
        confirmed = await ask_user(report.warning_message)
        if not confirmed:
            return WriteResult(success=False, user_rejected=True)
    
    # Write proceeds
    await actual_write(path, content)
    await prism.record_write(session_id, path, original_content, content)
    return WriteResult(success=True, security_report=report)
```

### What Gets Checked

**BLOCK (hard stop):**
- Hardcoded API keys, tokens, passwords (entropy analysis + patterns)
- `os.environ["SECRET"]` value assigned to a response/log
- SQL query built with f-string/format from user input
- `eval(user_input)` or `exec(user_input)`
- `subprocess.run(user_input, shell=True)`
- `pickle.loads(untrusted_data)`
- New dependency with CRITICAL or HIGH CVE (checked via OSV API)
- Writing to a `.env` file without it being in `.gitignore`

**WARN (requires confirmation):**
- MD5 or SHA1 used for password hashing
- `random` module used for token/nonce generation
- `except: pass` (bare exception suppression)
- `DEBUG = True` hardcoded in non-test file
- New external dependency added
- File path that matches `.gitignore` pattern but is being written anyway

### Security Report in Session

At end of session or on demand (`/security`), show a summary:
- Issues found and blocked: N
- Warnings reviewed and confirmed: N  
- Issues found and auto-fixed by agent: N (agent can propose fixes)

### Deliverable
No file write can proceed without Security Gate clearance. Test suite includes
fixtures with known security issues — all must be detected and blocked.

---

## Phase 4 — GitHub-Native Flows (Weeks 7–8)

**Goal:** Deep GitHub integration. The agent can implement issues end-to-end.

### New GitHub Tools

```python
# Issues
gh_get_issue(owner: str, repo: str, number: int) -> Issue
gh_list_issues(owner: str, repo: str, state: str, labels: list) -> list[Issue]
gh_comment_issue(owner: str, repo: str, number: int, body: str) -> Comment
gh_close_issue(owner: str, repo: str, number: int) -> bool
gh_assign_issue(owner: str, repo: str, number: int, assignees: list) -> bool
gh_add_labels(owner: str, repo: str, number: int, labels: list) -> bool

# Pull Requests
gh_create_pr(owner: str, repo: str, title: str, body: str,
             head: str, base: str, draft: bool = False) -> PR
gh_get_pr(owner: str, repo: str, number: int) -> PR
gh_list_pr_files(owner: str, repo: str, number: int) -> list[PRFile]
gh_review_pr(owner: str, repo: str, number: int, 
             body: str, event: str, comments: list) -> Review
gh_comment_pr(owner: str, repo: str, number: int, body: str,
              file: str = None, line: int = None) -> Comment

# Repo
gh_list_branches(owner: str, repo: str) -> list[Branch]
gh_get_file(owner: str, repo: str, path: str, ref: str) -> str
gh_search_code(query: str, owner: str, repo: str) -> list[Match]

# Actions / CI
gh_list_workflow_runs(owner: str, repo: str, workflow_id: str) -> list[Run]
gh_get_run_logs(owner: str, repo: str, run_id: int) -> str
```

### High-Level Flows (Built on Top of Tools)

```bash
# Implement a GitHub issue end-to-end
devagent implement github.com/owner/repo/issues/142
# 1. Fetch issue, understand requirement
# 2. Query CodePrism for impact and context
# 3. Create branch: feat/142-<slug>
# 4. Iterative edit-test loop
# 5. Create PR with linked issue, full description

# Review a PR
devagent review github.com/owner/repo/pull/58
# 1. Fetch PR diff
# 2. For each changed file: get CodePrism context around the changes
# 3. Run security scan on diff
# 4. Generate review with inline comments
# 5. Post to GitHub (or show locally)

# Triage open issues
devagent triage github.com/owner/repo
# 1. List open issues
# 2. For each: estimate effort, check for duplicates, suggest labels
# 3. Output triage table or post labels to GitHub

# Explain a failed CI run
devagent fix-ci github.com/owner/repo/actions/runs/12345
# 1. Fetch run logs
# 2. Identify failure reason
# 3. Locate relevant code via CodePrism
# 4. Propose and apply fix
```

### Deliverable
`devagent implement <issue-url>` works end-to-end on a Python project.
PR is created with proper title, description, and issue link.

---

## Phase 5 — Advanced Agent Features (Weeks 9–10)

**Goal:** Multi-model routing, test-driven loop, structured session memory,
offline-first polish.

### Multi-Model Router

Config:
```toml
[devagent.router]
planning   = { provider = "anthropic", model = "claude-opus-4-8" }
coding     = { provider = "anthropic", model = "claude-sonnet-4-6" }
reviewing  = { provider = "ollama",    model = "qwen2.5-coder:14b" }
cheap      = { provider = "ollama",    model = "qwen2.5-coder:3b" }
fallback   = { provider = "ollama",    model = "qwen2.5-coder:7b" }
```

Router logic:
| Task Type | Detection | Model |
|---|---|---|
| Task planning, architecture | First turn, `devagent implement` | planning |
| Writing/editing code | `file_write`, `file_edit` tool calls | coding |
| Reading files, grep | Exploratory tool calls | cheap |
| PR review, security analysis | `devagent review` command | reviewing |
| Summarizing tool results | Internal steps | cheap |

Token budget is tracked per-model and per-session. Cost breakdown shown at end.

### Test-Driven Agent Loop

After every `file_write` or `file_edit`:

1. Agent calls `cp_get_impact(file, symbol)` to find test files
2. If test files found: `shell_exec(pytest path/to/test_file.py -x -q)`
3. If tests fail: agent reads the failure, patches the code, re-runs
4. Loop exits when: all tests pass OR agent hits max_repair_iterations (default 3)
5. If max iterations hit: agent surfaces the failure to user and asks for guidance

This is NOT a separate mode — it's automatic on every edit.

### Structured Session Memory

Beyond conversation history, the agent maintains a structured knowledge store
within the session:

```python
@dataclass
class SessionMemory:
    # Set once, rarely changes
    project_purpose: str
    language: str
    framework: str
    test_framework: str
    
    # Grows during session
    learned_facts: list[str]          # "auth uses JWT, not sessions"
    decisions_made: list[Decision]    # "chose approach X over Y because..."
    files_understood: dict[str, str]  # file → one-line summary
    
    # Compact injection into every LLM call
    def to_prompt(self) -> str:
        # Returns ~200-token structured summary
        # Replaces re-reading conversation history
```

Command `/memory` shows current structured memory. Agent updates it explicitly
when it learns something architectural.

### Offline-First Polish

- All features work with `provider = "ollama"` and no internet
- `devagent doctor` explicitly reports "offline capable: yes/no"
- Startup banner shows if running fully local
- GitHub features gracefully degrade if no token provided
- Security pattern library is fully local (no API calls for CVE checks unless opted in)

### Deliverable
Full end-to-end session: implement a GitHub issue, with multi-model routing,
test-driven repair loop, and structured memory — all on Ollama with no internet
except GitHub API calls.

---

## Phase 6 — Polish, Open Source, Future-Prep (Week 11–12)

**Goal:** Ship a quality open source release. Prepare hooks for future features.

### Open Source Preparation

- [ ] MIT License
- [ ] CONTRIBUTING.md with architecture overview
- [ ] Full README with quickstart, feature list, benchmarks
- [ ] GitHub Actions CI (lint, test, build)
- [ ] PyPI publish workflow
- [ ] Issue templates: bug report, feature request, security issue
- [ ] Changelog maintained (keep-a-changelog format)

### Plugin System Foundations (Pluggable Tool Registry)

Don't build the full plugin system — build the interface so it can be added:

```python
# Tool registry accepts callables with a standard signature
tool_registry.register(
    name="my_custom_tool",
    description="Does X",
    parameters={"param1": "str", "param2": "int"},
    handler=my_async_handler_function
)
```

Document the interface. First-party plugins will come as separate packages
(`devagent-docker`, `devagent-aws`, etc.) after v1.0.

### UI Visualisation Hook (Future-Prep)

Add `devagent serve --ui` stub that starts an HTTP server on port 7331.
The server is empty in v1.0 but all CodePrism graph queries are available
as REST endpoints. Future: a web UI can connect to this and render the
knowledge graph visually (D3.js / Cytoscape.js — CodePrism already exports
D3-compatible JSON).

### Benchmarks for README

Run on 3 public Python repos (small/medium/large):
- Token usage: DevAgent v1.0 vs naive "read all files" baseline
- Task completion: `implement` flow success rate
- Security detection: known-vulnerable fixtures, detection rate

---

## Feature Summary Table

| Feature | Phase | Priority |
|---|---|---|
| ReAct agent loop | 1 | Critical |
| File read/write/edit tools | 1 | Critical |
| Shell execution | 1 | Critical |
| Session persistence (resume) | 1 | Critical |
| Streaming output | 1 | Critical |
| Token budget tracker | 1 | High |
| CodePrism integration | 2 | Critical |
| Impact Scope Estimator | 2 | High |
| Codebase Onboarding Mode | 2 | Medium |
| Session graph overlay | 2 | High |
| Security Gate | 3 | Critical |
| Secret detection | 3 | Critical |
| CVE dependency checking | 3 | Medium |
| GitHub implement flow | 4 | High |
| GitHub review flow | 4 | High |
| GitHub triage flow | 4 | Medium |
| Fix-CI flow | 4 | Medium |
| Multi-model routing | 5 | High |
| Test-driven repair loop | 5 | High |
| Structured session memory | 5 | High |
| Offline-first polish | 5 | Medium |
| Plugin system interface | 6 | Medium |
| UI hook (REST server) | 6 | Low |
| Open source release | 6 | Critical |

---

## New Project Structure (Target)

```
devagent/
├── __init__.py
├── cli.py                        # Typer app — devagent REPL + subcommands
│
├── core/
│   ├── config.py                 # Extended config (agent, router, session, security)
│   ├── llm.py                    # LLM factory
│   ├── router.py                 # Multi-model router
│   ├── models.py                 # All Pydantic models (agent + legacy GapReport)
│   ├── project.py                # Project detection
│   ├── storage.py                # Path resolution
│   └── url_parser.py             # GitHub URL parser
│
├── session/
│   ├── manager.py                # SessionManager: create, resume, list, delete
│   ├── store.py                  # SQLite persistence for sessions + journal
│   ├── memory.py                 # StructuredSessionMemory
│   ├── history.py                # ConversationHistory with compression
│   └── budget.py                 # TokenBudgetTracker
│
├── agent/
│   ├── loop.py                   # ReAct tool-calling loop (core of DevAgent)
│   ├── system_prompt.py          # System prompt builder (uses session memory)
│   └── flows/
│       ├── implement.py          # devagent implement <issue>
│       ├── review.py             # devagent review <pr>
│       ├── triage.py             # devagent triage <repo>
│       ├── onboard.py            # devagent onboard
│       └── fix_ci.py             # devagent fix-ci <run>
│
├── tools/
│   ├── registry.py               # ToolRegistry: register, lookup, execute
│   ├── file_tools.py             # file_read, file_write, file_edit, file_list
│   ├── shell_tool.py             # shell_exec (with blocklist)
│   ├── git_tools.py              # git_status, git_diff, git_commit, git_branch
│   ├── search_tools.py           # text_search
│   ├── github_tools.py           # All gh_* tools
│   ├── codeprism_tools.py        # cp_* wrappers over CodePrism MCP client
│   └── test_runner.py            # run_tests (pytest/jest/go test detection)
│
├── security/
│   └── gate.py                   # SecurityGate (thin wrapper over CodePrism)
│
├── output/
│   ├── terminal.py               # Rich streaming renderer
│   ├── status_bar.py             # Live status: session, tokens, cost, iteration
│   ├── diff_renderer.py          # Before/after diff display
│   ├── markdown.py               # Report saving (legacy analyze command)
│   └── chat_renderer.py          # Chat-specific formatting
│
├── mcp/
│   ├── manager.py                # Manages CodePrism + GitHub MCP servers
│   └── clients/
│       ├── codeprism_client.py   # CodePrism MCP client
│       └── github_client.py      # GitHub MCP client (extended)
│
└── legacy/                       # Preserved from v0.3.0
    ├── agents/                   # Original LangGraph pipeline
    ├── chat/                     # Original chat session
    └── watcher/                  # Repo health monitor (will be upgraded in future)

tests/
├── conftest.py
├── fixtures/
│   ├── sample_projects/
│   └── security_fixtures/
├── unit/
│   ├── test_router.py
│   ├── test_session_manager.py
│   ├── test_token_budget.py
│   ├── test_tool_registry.py
│   ├── test_file_tools.py
│   ├── test_shell_tool.py
│   ├── test_security_gate.py
│   └── test_structured_memory.py
└── integration/
    ├── test_agent_loop.py
    ├── test_implement_flow.py
    ├── test_review_flow.py
    └── test_github_tools.py
```

---

## Key Decisions

**Why ReAct over LangGraph pipeline?**
The current LangGraph pipeline is a fixed graph — nodes run in a predetermined
order. ReAct (Reason + Act) lets the LLM decide what to do next based on what
it just learned. This is required for open-ended coding tasks where the agent
can't know in advance which files it needs to read.

**Why CodePrism as a dependency, not embedded?**
CodePrism is a separate package so it can be used by other agents. DevAgent
is the flagship consumer, not the only consumer. The separation also keeps
the graph engine independently testable and evolvable.

**Why SQLite for sessions?**
Single-file, zero-infrastructure. Sessions can be moved, backed up, or shared
by copying one file. No Docker, no Postgres. Fits the offline-first ethos.

**Why Ollama as the default?**
Privacy, cost, and offline use. Enterprise teams and security-conscious
developers shouldn't have to send their code to a third-party API. Ollama
is the default; paid APIs are opt-in.

---

## Timeline Summary

| Phase | Description | Duration |
|---|---|---|
| 0 | Cleanup + new config + foundation | Week 1 |
| 1 | ReAct loop + file/shell tools + sessions | Weeks 2–3 |
| 2 | CodePrism integration + impact estimator | Weeks 4–5 |
| 3 | Security Gate | Week 6 |
| 4 | GitHub-native flows | Weeks 7–8 |
| 5 | Multi-model router + TDD loop + session memory | Weeks 9–10 |
| 6 | Open source polish + UI hook + plugin interface | Weeks 11–12 |

**Total: ~12 weeks to v1.0**

---

## Phase 7 — Power Features (Current Sprint)

**Goal:** Close the capability gaps identified against Claude Code. All six items
are additive — none require changing the core loop architecture. Target: v0.5.0.

---

### 7.1 Quick Action Mode

A single-shot, non-interactive command. The agent runs, streams output, and exits.
No REPL. Designed for scripting, CI pipelines, and cron jobs.

```bash
devagent do "fix the failing test in tests/test_auth.py"
devagent do "add type hints to all public functions in src/api/"
devagent do "write a changelog entry for the commits since last tag"
```

**What's needed:**

- New `do` command in `cli.py` (Typer `@app.command()`)
- Accepts task as a positional string argument
- Creates a session, calls `AgentLoop.run(task)` once, streams events to stdout
  via the existing `output/streaming.py` renderer
- Session still persisted to SQLite — inspectable with `devagent session show`
- `--no-session` flag to skip persistence (true one-shot, no DB write)
- Exit code: `0` on `FinalAnswerEvent`, `1` on `ErrorEvent`

**Design notes:**

Quick action mode is the foundation for scripting DevAgent. Once this exists,
CI jobs can call `devagent do "fix lint errors"` and pipe the output. It also
unblocks scheduled watcher analyses that currently require a foreground process.

---

### 7.2 Configurable Iteration Cap + Loop Detection

`MAX_ITERATIONS = 30` is a hardcoded constant. Make it configurable and add a
smarter early-exit when the agent is spinning its wheels.

**Config addition:**

```toml
[agent]
max_iterations  = 30    # 0 = unlimited (requires --no-limit flag to activate)
loop_detection  = true  # detect repeated identical tool calls and bail early
```

**What's needed:**

- Read `max_iterations` from `DevAgentConfig.agent` (add `AgentConfig` dataclass
  if not present, or extend the existing config section)
- Add `--no-limit` flag to `devagent run` and `devagent do` — required to activate
  `max_iterations = 0`; prevents silent infinite loops via config alone
- Loop detection: track the last 6 `(tool_name, args_hash)` pairs; if the same
  pair appears 3 times in the last 6 calls, yield `ErrorEvent("loop detected")`
  and stop — this catches the agent calling `read_file` on the same file repeatedly
  without making progress

**Priority:** Trivial implementation, high practical value.

---

### 7.3 Explicit Plan Mode

Two-phase execution: the agent generates a structured plan and shows it before
doing anything. User reviews, optionally edits, then approves. Execution then
follows the plan step by step.

```bash
devagent run --plan                          # plan mode for interactive session
devagent implement <url> --plan              # plan mode for GitHub flows
devagent do "refactor auth module" --plan    # plan mode for quick action
```

**Plan display:**

```
┌─ Plan ──────────────────────────────────────────────────────────────────┐
│ Task: Refactor auth module                                              │
│                                                                         │
│  Step 1  Read auth/middleware.py and auth/models.py                     │
│  Step 2  Identify functions to extract into auth/validators.py          │
│  Step 3  Create auth/validators.py with extracted logic                 │
│  Step 4  Update imports in auth/middleware.py                           │
│  Step 5  Run tests/test_auth.py — fix any failures                      │
│  Step 6  Update auth/__init__.py exports                                │
│                                                                         │
│  Estimated tool calls: ~12    Estimated tokens: ~8,000                  │
│                                                                         │
│  [A]pprove  [E]dit  [C]ancel                                            │
└─────────────────────────────────────────────────────────────────────────┘
```

**What's needed:**

- `Plan` dataclass: `steps: list[PlanStep]`, each step has `description`,
  `tool_hints: list[str]`, `estimated_tokens: int`
- Planning-only LLM call: system prompt instructs the LLM to output a structured
  plan as JSON before taking any action — uses the `planning` router model
- `output/plan_renderer.py`: Rich display of the plan with step numbering
- Inline edit mode: user can type `edit 3: also update the test file` and the
  plan is amended before approval
- During execution: step completion tracked in real time — completed steps shown
  with a checkmark in the live status bar
- `session/store.py` addition: store the plan as a `plan_json` column on the
  session row so it can be displayed on resume

**Design notes:**

The key difference from just prompting "make a plan first": the plan has an
explicit approval gate. The LLM cannot proceed to execution until the user hits
`A`. This mirrors Claude Code's plan mode and is the most-requested UX feature
from the comparison.

---

### 7.4 Skills / Slash Commands System

Extend the existing REPL slash handling into a proper skills system. Skills are
named, pre-configured agent behaviours that the user invokes with `/skill-name`.

**Built-in skills:**

```
/explain [path]          — explain what a file or function does (cheap model, no writes)
/test [path]             — run tests for a file and show coverage gaps
/review                  — review staged git changes before committing
/commit [message]        — stage, write a commit message, and commit
/summarize               — summarize what the session has done so far
/security                — show the security gate log for this session
/memory                  — show and edit the session memory block
/plan                    — generate and show a plan for the next task
/tokens                  — show detailed token usage breakdown by model
```

**User-defined skills (files in `~/.config/devagent/skills/`):**

```toml
# ~/.config/devagent/skills/deploy.toml
name        = "deploy"
description = "Run the deployment checklist before pushing"
prompt      = """
Review the current git diff and run the following checklist:
1. No debug flags left in code
2. All tests pass
3. CHANGELOG.md updated
4. Version bumped in pyproject.toml
Report each item as pass/fail.
"""
tools_only  = ["run_shell", "read_file", "git_diff"]   # restrict tool access
model       = "cheap"                                   # force model tier
max_iter    = 5                                         # cap iterations
```

**What's needed:**

- `skills/loader.py`: scan `~/.config/devagent/skills/*.toml` and built-in skills
  on startup; register each as a `Skill` object
- REPL modification: detect `/word` prefix, look up skill, run with overridden
  system prompt + tool restrictions + iteration cap
- `devagent skills list` command: show all available skills with descriptions
- `devagent skills new` command: interactive wizard to create a new skill TOML

---

### 7.5 Full Bash Shell

Replace the current blunt 8KB cap in `run_shell` with a streaming, stateful shell
that handles long-running commands and large outputs gracefully.

**What's needed:**

- `tools/shell_tool.py` refactor: subprocess streams stdout to a temp file while
  also capturing a live tail of the last 50 lines
- On command completion: return the last 50 lines inline + total line count + path
  to the full output file
- New `read_shell_output` tool: reads the full temp file in paginated chunks —
  the LLM can call this to page through large outputs
- Shell session state: maintain a `ShellSession` object per agent session with
  persistent `cwd` and env vars — `cd /some/path` in one tool call persists to
  the next; `export FOO=bar` is visible in subsequent calls
- Long-running command support: `run_shell` with `background=True` starts the
  command in a subprocess and returns immediately with a process ID; a second
  tool `poll_shell(pid)` checks if it's done and returns current output

**Config:**

```toml
[agent]
shell_output_cap_kb = 0      # 0 = unlimited (full output to temp file)
shell_timeout_sec   = 300    # per command; 0 = no timeout
```

---

### 7.6 DevAgent as an MCP Server

Flip DevAgent from MCP client to also being an MCP server. Any AI editor with
MCP support — Claude Desktop, Claude Code, Cursor, Windsurf — can connect and
use DevAgent's tools and CodePrism graph directly.

```bash
devagent mcp                  # start stdio MCP server (for claude_desktop_config)
devagent mcp --transport sse  # SSE transport for Cursor/Windsurf
```

**Tools exposed as MCP tools:**

All tools in the ToolRegistry get exposed as MCP tool definitions. The MCP server
is a thin adapter that maps incoming MCP `tools/call` requests to `registry.call()`.

**Resources exposed:**

```
devagent://graph/stats        → CodePrism graph statistics
devagent://graph/files        → file map
devagent://sessions           → recent session list
devagent://sessions/{id}      → session detail
```

**Claude Desktop config (`claude_desktop_config.json`):**

```json
{
  "mcpServers": {
    "devagent": {
      "command": "devagent",
      "args": ["mcp"]
    }
  }
}
```

**What's needed:**

- `mcp/server.py`: new module implementing the MCP server protocol
- Uses `mcp` package (already a dependency) in server mode — `Server` class with
  `@server.list_tools()` and `@server.call_tool()` handlers
- `server.list_tools()` returns `registry.get_definitions()` translated to MCP
  `Tool` objects (schemas are already JSON Schema — direct mapping)
- `server.call_tool()` calls `registry.call(name, args)` and wraps the string
  result in an MCP `TextContent` response
- `devagent mcp` CLI command: starts the server using stdio transport
- `devagent mcp --transport sse --port 7332` for SSE transport
- Security: MCP server respects the SecurityGate — writes are still gated

**Distribution impact:**

Once this exists, DevAgent's CodePrism tools (`cp_get_callers`, `cp_get_impact`,
etc.) are accessible from Claude Desktop, Claude Code, and any MCP-enabled editor
without those editors knowing anything about DevAgent internals.

---

### Phase 7 Deliverables

- `devagent do "task"` works end-to-end and exits cleanly
- `devagent run --plan` shows a reviewable plan before execution
- `/explain`, `/review`, `/commit` skills work in the REPL
- `run_shell` handles outputs over 8KB via streaming + temp file
- `devagent mcp` starts a working MCP server that Claude Desktop can connect to
- Iteration cap is configurable; loop detection catches spinning agents

---

## Phase 8 — Context Auto-Compression

**Goal:** Handle very long sessions without hitting the context window. Sessions
that currently degrade after 50+ turns work smoothly at 200+ turns. Target: v0.6.0.

---

### The problem

`build_messages()` replays the full event history every turn. A session with 150
events might have 40K tokens of history, leaving little room for new context.
Most of those tokens are from early turns that are no longer relevant.

### Compression strategy

```mermaid
flowchart LR
    EVENTS[Full event history\nN events]
    THRESHOLD{total history tokens\n> compression_threshold?}
    WINDOW[Keep last K events verbatim\n"hot window"]
    COMPRESS[Summarise events 0..N-K\ninto a single SummaryEvent]
    FACTS[Golden facts from MemoryBlock\nalways survive]
    BUILD[build_messages\nsystem + summary_event + hot_window + user]

    EVENTS --> THRESHOLD
    THRESHOLD -->|yes| COMPRESS
    COMPRESS --> WINDOW
    WINDOW --> BUILD
    FACTS --> BUILD
    THRESHOLD -->|no| BUILD
```

**What's needed:**

- `session/compressor.py`: takes a list of events, a model (for summarisation),
  and a `keep_last_n` window size; calls the LLM to summarise old events; returns
  a `SummaryEvent` row
- `session/store.py` addition: `compressed_summary` column on `sessions` table;
  `is_compressed` flag on `session_events` rows that have been summarised
- `build_messages()` modification: if a compressed summary exists, inject it as a
  `system`-role block before the hot window instead of replaying old events
- Trigger: auto-compress when `total_history_tokens > config.session.compression_threshold`
  (default: 60% of model context window)
- `devagent session compress <id>` manual command for explicit compression
- Compression preserves: all `MemoryBlock` facts, all tool results from the hot
  window, all file paths and line numbers mentioned in old turns

**Config:**

```toml
[session]
auto_compress           = true
compression_threshold   = 0.6      # fraction of context window
compression_window_size = 20       # keep last N events verbatim
compression_model       = "cheap"  # model tier for summarisation
```

**MemoryPrism note:**

Context auto-compression is the internal DevAgent implementation. The broader
`MemoryPrism` library (see Additional Ideas) extracts this into a standalone
tool usable by any AI editor — but that is a separate product and is not built here.

---

## Phase 9 — Multi-Agent Orchestration

**Goal:** Break large tasks into parallel subtasks handled by independent agent
instances. The first step toward enterprise-scale task execution. Target: v0.7.0.

---

### Architecture

```
Coordinator Agent
├── reads task + codebase graph
├── decomposes into N subtasks
├── assigns each to a Worker Agent
│   ├── Worker 1: implement module A
│   ├── Worker 2: implement module B
│   └── Worker 3: write tests for both
├── tracks progress via shared task graph
├── resolves conflicts (same file edited by two workers)
└── synthesises final result

Each Worker is a full AgentLoop instance running in a thread-pool executor.
```

### What's needed

**Async refactor of `AgentLoop`:**

The current loop is a sync generator. Workers need to run concurrently, which
requires either threading (simplest) or a full async rewrite. The threading
approach: each worker runs in a `ThreadPoolExecutor` thread; the coordinator
collects results via a `queue.Queue`. This avoids an async rewrite of the
existing code while enabling true parallelism.

**Task graph:**

```python
@dataclass
class TaskNode:
    id: str
    description: str
    assigned_to: str | None          # worker ID
    depends_on: list[str]            # task IDs that must complete first
    status: Literal["pending", "running", "done", "failed"]
    result: str | None
    output_files: list[str]          # files written by this task
```

Stored in `session/store.py` as a new `task_graph` table.

**Write-lock mechanism:**

Before any worker calls `write_file` or `edit_file`, it checks a file-level
lock table. If another worker holds the lock, it waits or skips and reports
the conflict to the coordinator. The coordinator then serialises conflicting
writes.

**New CLI commands:**

```bash
devagent orchestrate "implement the full payments module from scratch"
devagent orchestrate --workers 4 "refactor the auth system"
devagent orchestrate --plan "build a REST API for the user service"
```

With `--plan`: coordinator shows the task decomposition for approval before
spawning workers.

**Agent types:**

```
coordinator   — decomposes task, assigns, monitors, synthesises
implementer   — writes code (restricted to coding tool set)
tester        — writes and runs tests only
reviewer      — reads and comments, no writes
```

Each type gets a different system prompt and tool restriction set.

---

## Additional Future Ideas

*These are logged for reference only. No implementation is planned yet.*

---

### MemoryPrism

A standalone Python library and MCP server for conversation history compression.
Solves the universal AI editor problem: long conversations hit context window
limits and degrade in quality.

**What it would be:**

- `pip install memoryprism-ai` — standalone, not coupled to DevAgent
- Takes a list of LLM messages and returns a compressed version with the same
  semantic meaning but fewer tokens
- Preserves exact facts (file paths, function names, decisions, error messages)
  verbatim — semantic loss on these is a correctness bug, not a quality trade-off
- Summarises narrative and reasoning sections — reducing them to dense statements
- Detects and deduplicates repeated tool results (three `read_file` calls on the
  same file → only the latest result kept)
- Exposes as an MCP server: `compress_history`, `extract_facts`, `summarize_session`
- Any MCP-enabled editor (Claude Desktop, Cursor, Windsurf) adds it and gets
  automatic context management

**Relationship to Phase 8:**

Phase 8 builds context compression directly inside DevAgent using its own
`session/compressor.py`. MemoryPrism is the generalised, extracted version of
that idea — a separate `codeprism-ai`-style package that stands alone and serves
the whole ecosystem. It is not built until DevAgent's internal compression is
proven and the API is stable enough to extract.

---

---

## Phase 10 — Hooks & Permission System (Target: v0.8.0)

**Goal:** Let users intercept, block, rewrite, or verify any tool call via declarative hooks.
Add a permission mode system so agent behaviour can be tightened or loosened per invocation.
This is the single biggest gap vs Claude Code and the foundation for safe automation.

---

### 10.1 Hooks Infrastructure

A hook is a declarative rule that fires on a lifecycle event and can:
- **Observe** (log, notify)
- **Block** (reject the tool call; stderr becomes feedback to the LLM)
- **Rewrite** (modify the tool input before it reaches the tool)

**Config location:** `.devagent/hooks.toml` (project) or `~/.config/devagent/hooks.toml` (global)

```toml
[[hooks]]
event   = "pre_tool_use"
tool    = "run_shell"          # optional — omit to match all tools
type    = "command"
command = "echo $DEVAGENT_TOOL_INPUT | python scripts/audit_shell.py"
# exit 0 = allow, exit 2 = block (stderr → LLM feedback)

[[hooks]]
event   = "pre_tool_use"
tool    = "write_file"
type    = "http"
url     = "http://localhost:9000/approve"
# POST body: {tool, args}; response: {ok: true} or {ok: false, reason: "..."}

[[hooks]]
event   = "session_end"
type    = "command"
command = "python scripts/session_summary.py"
```

**Hook types to implement:**
- `command` — shell command; env vars `DEVAGENT_TOOL_NAME`, `DEVAGENT_TOOL_INPUT` (JSON)
- `http` — POST to URL with JSON body; expects `{ok, reason}` response
- `prompt` — single-turn LLM call to evaluate the action (uses cheap model)

**Events (Phase 10 scope — start with the most impactful):**

| Event | When it fires |
|---|---|
| `pre_tool_use` | Before any tool call — can block or rewrite |
| `post_tool_use` | After tool completes — observe result |
| `session_start` | When a session begins |
| `session_end` | When a session ends (write audit log, notify) |
| `file_write` | Shorthand alias for `pre_tool_use` on `write_file`/`edit_file` |

**Exit code contract:**
- `0` = allow / no-op
- `2` = block; stderr content is injected as tool error message back to the LLM

**Rewrite support:** if `stdout` is valid JSON with an `updatedInput` key, the tool is called with those args instead of the original.

**What's needed:**
- `devagent/hooks/runner.py` — `HookRunner` class; loads config, matches event+tool, dispatches
- `devagent/hooks/config.py` — `HookDef` dataclass (event, tool, type, command/url/prompt)
- Wire `HookRunner.pre_tool_use(tool_name, args)` into `ToolRegistry.call()` before dispatch
- Wire `HookRunner.post_tool_use(tool_name, args, result)` after dispatch
- Wire `HookRunner.session_start(session_id)` and `session_end(session_id)` in session lifecycle
- `devagent hooks list` CLI command — show all active hooks from both config files
- `devagent hooks test <event> <tool>` — dry-run a hook without executing the tool

---

### 10.2 Permission Modes

A permission mode sets the default stance on tool confirmation for a session.

```bash
devagent run --permission-mode accept-edits   # auto-accept file edits; prompt for shell
devagent run --permission-mode read-only       # no writes at all
devagent run --permission-mode auto            # background approval; minimal prompts
devagent do "task" --permission-mode yolo      # auto-approve everything (CI use)
```

**Modes:**

| Mode | File writes | Shell | Confirmations |
|---|---|---|---|
| `default` | Prompt | Prompt | All tool calls |
| `accept-edits` | Auto | Prompt | Shell only |
| `read-only` | Blocked | Blocked | N/A |
| `auto` | Auto | Auto if low-risk | Minimal |
| `yolo` | Auto | Auto | None |

**Per-tool allow/deny in `settings.toml`:**

```toml
[permissions]
allow = ["read_file", "list_files", "grep", "git_status", "git_diff"]
deny  = ["delete_file", "git_branch_create"]
ask   = ["run_shell", "write_file"]
```

**What's needed:**
- `PermissionMode` enum in `core/config.py`
- `PermissionGate` class in `devagent/hooks/permissions.py` — evaluates mode + per-tool rules
- `--permission-mode` flag on `run`, `do`, `implement`, `orchestrate`
- `/permissions` REPL command — show current mode + per-tool rules, allow user to toggle
- Store `permission_mode` in session metadata

---

### Phase 10 Deliverables

- `devagent run --permission-mode read-only` prevents all writes
- A `[[hooks]]` entry in `.devagent/hooks.toml` fires on `pre_tool_use` and can block a shell command
- `devagent hooks list` shows all active hooks
- `devagent run --permission-mode yolo` suppresses all confirmations (CI use)
- 20+ tests covering hook dispatch, block/allow paths, rewrite, permission gate

---

## Phase 11 — Web Tools & Structured Output (Target: v0.9.0)

**Goal:** Give the agent access to live web information and give CI pipelines clean machine-readable output.

---

### 11.1 Web Search Tool

```python
web_search(query: str, num_results: int = 5) -> list[SearchResult]
# SearchResult: {title, url, snippet}
```

**Providers (configured in `settings.toml`):**
- `brave` — `BraveConfig.api_key` (already in config)
- `searchx` — `SearchXConfig.api_key` (already in config)
- `duckduckgo` — free, no key required (fallback)

**What's needed:**
- `devagent/tools/web_tools.py` — `web_search` + `web_fetch` implementations
- Register in `build_registry()` (always — no token required for DDG fallback)
- `devagent/search/brave.py`, `duckduckgo.py` (providers already partially exist)

---

### 11.2 Web Fetch Tool

```python
web_fetch(url: str, extract: str = "text") -> str
# extract: "text" | "markdown" | "links" | "raw"
# Returns: cleaned text / markdown / list of URLs / raw HTML (capped at 50k chars)
```

Uses `httpx` + `BeautifulSoup` for HTML → clean text extraction.

---

### 11.3 `/deep-research` Skill

Built on `web_search` + `web_fetch`:

```
/deep-research what is the best approach for distributed rate limiting
```

1. LLM generates 4–6 search queries
2. `web_search` each query → collect top results
3. `web_fetch` each URL → extract article text
4. LLM synthesises into a cited report (source URLs included)

Implemented as a built-in skill (TOML + multi-step prompt chain).

---

### 11.4 Structured Output & JSON Mode

**New CLI flags:**

```bash
devagent do "extract all function names" --output-format json
devagent do "list open issues summary" --output-format stream-json
devagent do "analyse this PR" --json-schema '{"type":"object","properties":{"risk":{"type":"string"}}}'
```

**Output formats:**
- `text` (default) — current behaviour
- `json` — `{"result": "...", "session_id": "...", "tokens": {...}}` on exit
- `stream-json` — newline-delimited JSON events as they arrive (for CI pipelines)

**What's needed:**
- `OutputFormat` enum in `core/config.py`
- `--output-format` flag on `do` and `run`
- `--json-schema` flag — validates `FinalAnswerEvent.text` against schema; retries once on mismatch
- Modify `output/streaming.py` renderer to write JSON lines when format is non-text

---

### 11.5 Stdin Pipe Support

```bash
git diff main | devagent do "review for security issues"
tail -200 app.log | devagent do "find anomalies and root cause"
```

When stdin is not a TTY, read it and prepend to the task as a `<stdin>` block.

**What's needed:**
- Check `sys.stdin.isatty()` in `do` command; if False, read stdin and inject into task string

---

### Phase 11 Deliverables

- `web_search("rate limiting algorithms")` returns results in-loop
- `web_fetch("https://example.com/article")` returns clean text
- `/deep-research` skill works end-to-end
- `devagent do "task" --output-format json` returns clean JSON to stdout
- `git diff | devagent do "review"` works
- 15+ tests

---

## Phase 12 — Project Memory & CLAUDE.md (Target: v1.0.0)

**Goal:** Persistent, version-controllable project knowledge that survives session boundaries —
the DevAgent equivalent of CLAUDE.md.

---

### 12.1 DEVAGENT.md — Per-Project Session Context

A markdown file at the project root (or in subdirectories) that is loaded into the system
prompt at the start of every session. Equivalent to Claude Code's `CLAUDE.md`.

```bash
devagent init          # generate DEVAGENT.md for the current project
```

`devagent init` uses the LLM to analyse the project structure and produce:
- Project purpose and architecture overview
- Key files and their roles
- Test framework and how to run tests
- Conventions and gotchas the agent should know
- Any project-specific rules (e.g. "never edit generated files in src/generated/")

**Loading rules:**
- `./DEVAGENT.md` — always loaded
- Subdirectory `DEVAGENT.md` files — loaded when agent reads files in that directory
- `~/.config/devagent/DEVAGENT.md` — global user-level context (always loaded)

**What's needed:**
- `devagent/session/project_memory.py` — `load_project_memory(project_root) -> str`
- Inject result into `build_system_prompt()` under `## Project Context`
- `devagent init` CLI command — runs analysis, writes `DEVAGENT.md`
- Support for subdirectory-scoped files (scan ancestors of each file read)

---

### 12.2 MEMORY.md — Persistent Auto Memory

A `MEMORY.md` file at project root (git-ignored by default) that the agent maintains across
sessions. Survives compression. Re-injected at start of every session.

```
## Persistent Memory
- Framework: FastAPI + SQLAlchemy
- Auth: JWT tokens, 24h expiry
- Tests: pytest; run with `pytest tests/ -q`
- Never touch: `src/generated/` — auto-generated by protoc
- DB migration tool: Alembic; always create migration before schema change
```

**Agent tools:**
- `remember_persistent(key, value)` — writes a fact to `MEMORY.md`
- `forget_persistent(key)` — removes a fact

**What's needed:**
- `devagent/session/persistent_memory.py` — read/write `MEMORY.md` in project root
- `/memory` REPL command extension — show both session MemoryBlock and persistent MEMORY.md
- Add to system prompt injection on every session start

---

### 12.3 `/init` Command

```bash
devagent init [--project <path>]
```

Generates both `DEVAGENT.md` and an initial `MEMORY.md` by analysing the project via:
1. `list_files` (project structure)
2. `cp_get_file_map` if CodePrism is indexed
3. LLM generates the context document

---

### 12.4 Four-Level Settings Hierarchy

Currently: single TOML file. Target:

| Level | File | Scope |
|---|---|---|
| 1 (highest) | `.devagent/settings.toml` | Project — committed to git |
| 2 | `.devagent/settings.local.toml` | Project — gitignored |
| 3 | `~/.config/devagent/settings.toml` | User — all projects |
| 4 (lowest) | Built-in defaults | Hardcoded in `core/config.py` |

Lower levels fill in missing keys from higher levels. Project settings override user settings.

**What's needed:**
- `devagent/core/config.py` — `load_merged_config(project_root) -> DevAgentConfig`
- Auto-add `.devagent/settings.local.toml` to `.gitignore`
- `devagent config --set key=value [--scope project|user]` — write to correct file

---

### Phase 12 Deliverables

- `devagent init` generates `DEVAGENT.md` for a Python project
- `DEVAGENT.md` content appears in system prompt on every session
- `MEMORY.md` facts survive compression and session boundaries
- `devagent config --set agent.max_iterations=50 --scope project` writes to `.devagent/settings.toml`
- 15+ tests

---

## Phase 13 — REPL Depth & UX (Target: v1.1.0)

**Goal:** Close the slash-command gap. Add the high-value REPL commands that Claude Code has
and DevAgent is missing.

---

### 13.1 Context & Conversation Management

| Command | Behaviour |
|---|---|
| `/context` | Show token breakdown: system prompt / memory / history / hot-window. Suggest `/compact` if >70% used |
| `/autocompact [<tokens>\|off]` | Set auto-compress threshold dynamically (e.g. `/autocompact 50000`) |
| `/compact [focus on <topic>]` | Compress now, optionally keeping a topic front-of-mind |
| `/clear` | Start a new session in the same project (keep persistent memory, wipe conversation) |
| `/rewind` | Roll back the last N turns (prompts for N, removes from DB) |
| `/status` | Show: session ID, project, model, tokens used, iteration count, compression count |

---

### 13.2 Goal Mode

```
/goal all tests pass and no ruff errors
```

Agent keeps iterating — running tests, fixing failures, running ruff — until the goal condition
is true (evaluated by a cheap LLM call) or `max_iterations` is hit.

**What's needed:**
- `GoalMode` dataclass: `condition: str`, `check_every_n_iterations: int = 2`
- After each iteration, if goal mode active: call LLM with `(goal, last_tool_results)` → `{met: bool}`
- Exit loop when `met: True`

---

### 13.3 Diff Viewer

Before any `write_file` or `edit_file`, show a coloured unified diff and prompt
`[A]pply / [S]kip / [C]ancel` (unless in `auto` or `yolo` permission mode).

```
/diff         # show pending diff from last edit tool call
```

Uses `difflib.unified_diff` + Rich syntax highlighting.

**What's needed:**
- `devagent/output/diff_renderer.py` — `render_diff(old, new, path) -> Panel`
- Hook into `ToolRegistry.call()` for `write_file`/`edit_file` when not in auto mode
- `/diff` command — re-show the last rendered diff

---

### 13.4 Utility Commands

| Command | Behaviour |
|---|---|
| `/btw <question>` | Ask side question; response shown but NOT added to conversation history |
| `/theme [dark\|light\|minimal]` | Switch Rich color theme |
| `/keybindings` | Show/edit keyboard shortcut config |

---

### Phase 13 Deliverables

- `/context` shows live token breakdown
- `/goal "all tests pass"` loops until pytest exits 0
- Diff viewer prompts before every write (in default mode)
- `/clear` resets conversation; `/rewind 2` removes last 2 turns
- `/status` shows full session summary
- 15+ tests

---

## Phase 14 — Advanced Agent Architecture (Target: v1.2.0)

**Goal:** Agent definition files, background agents, worktree isolation, and loop-based automation.
Brings DevAgent's multi-agent system to parity with Claude Code's agent frontmatter system.

---

### 14.1 Agent Definition Files

```
.devagent/agents/code-reviewer.toml
.devagent/agents/security-auditor.toml
~/.config/devagent/agents/deploy-checker.toml
```

```toml
name         = "code-reviewer"
description  = "Reviews code for correctness, security, and style"
worker_type  = "reviewer"
model        = "reviewing"        # router tier
max_iter     = 10
tools        = ["read_file", "grep", "git_diff", "git_status"]
permission   = "read-only"
memory       = "project"          # project-scoped persistent memory
prompt       = """
You are a senior code reviewer. Focus on:
1. Correctness bugs
2. Security issues (injection, auth bypass, secrets)
3. Missing error handling
4. Style and clarity
Output a structured review in markdown.
"""
```

**Invocation:**
```bash
devagent agent run code-reviewer            # from CLI
# or in REPL:
/code-reviewer                              # auto-detected as agent by name
@code-reviewer please review the auth changes
```

**What's needed:**
- `devagent/agents/loader.py` — scan `.devagent/agents/*.toml` + `~/.config/devagent/agents/*.toml`
- `AgentDef` dataclass
- Wire into REPL: if `/word` matches an agent name, invoke it
- `devagent agent list` — show available agents
- `devagent agent new` — interactive wizard to create `.devagent/agents/<name>.toml`

---

### 14.2 Worktree Isolation

When an agent definition has `isolation = "worktree"`, create a fresh `git worktree` before
running and remove it after:

```toml
isolation = "worktree"   # agent gets its own branch + working directory
```

**What's needed:**
- `devagent/agent/worktree.py` — `create_worktree(branch_name) -> path`, `remove_worktree(path)`
- Wrap `Worker.run()` in worktree context when isolation is enabled
- Commit changes back to the worktree branch on success; discard on failure

---

### 14.3 Persistent Agent Memory

Agents with `memory = "project"` maintain a `MEMORY.md` file scoped to that agent:

```
.devagent/agent-memory/code-reviewer/MEMORY.md
```

Loaded into the agent's system prompt at start; updated by the agent via `remember_persistent`.

---

### 14.4 Background Agents & Task Management

```bash
devagent agent run code-reviewer --background    # runs detached, notifies on completion
devagent tasks                                   # list running/completed background tasks
devagent tasks show <task-id>                    # show output of a background task
```

**REPL equivalents:**
```
/fork run the code-reviewer on the auth module    # detach current task
/tasks                                            # list background tasks
```

**What's needed:**
- Background task tracking table in SQLite (`background_tasks`)
- Notification via terminal bell + status line update on completion

---

### 14.5 `/loop` Recurring Prompt

```
/loop 5m run the security gate on any new commits
/loop off
```

Runs a prompt on a schedule (using a background thread). Stops when session ends.

---

### 14.6 `/autofix-pr` Watch Mode

```bash
devagent autofix-pr <pr-url>    # watch PR, auto-fix CI failures and review comments
```

1. Polls GitHub for new CI failures or review comments every 2 minutes
2. For each failure: runs `fix-ci` flow
3. For each review comment: runs fix loop on the commented file
4. Pushes updated commits to the PR branch

---

### Phase 14 Deliverables

- `devagent agent run code-reviewer` works against a project
- `--background` runs detached; `devagent tasks` shows it
- `/fork`, `/tasks` work in REPL
- `/loop 10m /security` runs security check every 10 minutes
- `isolation = "worktree"` gives agent its own git worktree
- 20+ tests

---

## Phase 15 — Effort, Thinking & CI Polish (Target: v1.3.0)

**Goal:** Expose model thinking depth as a first-class control. Harden CI output.

---

### 15.1 Effort Levels

```bash
devagent run --effort high          # default
devagent run --effort max           # extended thinking, slower, deeper
devagent do "task" --effort low     # fast, cheap — simple tasks
```

**Levels:** `low` → `medium` → `high` (default) → `xhigh` → `max`

**What's mapped:**
- `low` / `medium` → temperature 0.2, cheap model tier, no thinking
- `high` (default) → current behaviour
- `xhigh` / `max` → enable extended thinking (`thinking: {type: "enabled", budget_tokens: N}`)
  for Anthropic models; higher `temperature` for others

**In REPL:** `/effort max` switches for the next turn only.

---

### 15.2 Extended Thinking Toggle

For Anthropic models that support it (`claude-opus-4-8`, `claude-sonnet-4-6`):

```toml
[agent]
extended_thinking = false         # default off
thinking_budget_tokens = 10000
```

Toggle in REPL: `/think [on|off]`

**What's needed:**
- Pass `thinking` parameter to `anthropic.messages.create()` in `core/llm.py`
- Show `<thinking>...</thinking>` blocks in streaming output (dim style)

---

### 15.3 `--bare` Mode

```bash
devagent do "task" --bare
```

Skip: hooks, skills, DEVAGENT.md, MEMORY.md, CodePrism overlay, permission gate.
Pure agent loop with minimal context injection. Useful for benchmarking and debugging.

---

### 15.4 CLI Hardening for CI

```bash
# Auto-approve specific tools (no prompts for those)
devagent do "fix lint" --allow-tools "run_shell,write_file,read_file"

# Grant access to an additional directory
devagent do "update docs" --add-dir "../docs-repo"

# Stream JSON for machine parsing
devagent do "list TODOs" --output-format stream-json | jq '.result'
```

---

### Phase 15 Deliverables

- `--effort low/high/max` works; max enables extended thinking on Anthropic
- `/think on` visible thinking blocks in REPL output
- `--bare` produces minimal, reproducible runs
- `--allow-tools` restricts auto-approve to listed tools
- CI pipeline can `devagent do "task" --output-format json` and parse result

---

## Phase 16 — Vision & Notebooks (Target: v1.4.0)

**Goal:** Add image understanding and Jupyter notebook editing.
Lower priority than earlier phases — implement last.

---

### 16.1 Vision / Screenshot Tool

```python
take_screenshot() -> ImageResult        # captures current screen
read_image(path: str) -> ImageResult    # reads image file
```

Passes the image to the LLM as a `image_url` content block (base64).

Use cases: debug UI layout issues, verify output visually, read diagrams.

**Providers:** Only Anthropic and OpenAI support vision. Gracefully skipped for Ollama.

---

### 16.2 Jupyter Notebook Tools

```python
notebook_read(path: str) -> NotebookContent     # all cells with outputs
notebook_edit(path: str, cell_index: int, source: str)  # edit a cell
notebook_run(path: str, cell_index: int = None)  # run cell(s) via nbconvert
```

**What's needed:**
- `devagent/tools/notebook_tools.py` using `nbformat` library
- Register when `nbformat` is importable

---

### 16.3 Todo Tools

```python
todo_write(tasks: list[dict])   # write structured task list to session
todo_read() -> list[dict]       # read current task list
```

Stored in session DB as a JSON blob. Shown in status bar as `[tasks: 3/7]`.

---

### Phase 16 Deliverables

- `read_image("screenshot.png")` passes image to LLM for analysis
- `notebook_read("analysis.ipynb")` returns all cells
- `notebook_edit(...)` modifies a cell cleanly
- Todo tools track in-session task list
- 10+ tests

---

## Updated Feature Summary Table

| Feature | Phase | Priority | Status |
|---|---|---|---|
| ReAct agent loop | 1 | Critical | Done |
| File read/write/edit tools | 1 | Critical | Done |
| Shell execution | 1 | Critical | Done |
| Session persistence (resume) | 1 | Critical | Done |
| Streaming output | 1 | Critical | Done |
| Token budget tracker | 1 | High | Done |
| CodePrism integration | 2 | Critical | Done |
| Impact Scope Estimator | 2 | High | Done |
| Codebase Onboarding Mode | 2 | Medium | Done |
| Session graph overlay | 2 | High | Done |
| Security Gate | 3 | Critical | Done |
| Secret detection | 3 | Critical | Done |
| GitHub implement flow | 4 | High | Done |
| GitHub review flow | 4 | High | Done |
| GitHub triage flow | 4 | Medium | Done |
| Fix-CI flow | 4 | Medium | Done |
| Multi-model routing | 5 | High | Done |
| Test-driven repair loop | 5 | High | Done |
| Structured session memory | 5 | High | Done |
| Offline-first polish | 5 | Medium | Done |
| Plugin system interface | 6 | Medium | Done |
| REST API server | 6 | Medium | Done |
| Open source release | 6 | Critical | Done |
| Quick action mode (`devagent do`) | 7 | High | Done |
| Configurable iteration cap + loop detection | 7 | High | Done |
| Explicit plan mode (`--plan`) | 7 | High | Done |
| Skills / slash commands | 7 | Medium | Done |
| Full bash shell (streaming + stateful) | 7 | Medium | Done |
| DevAgent as MCP server | 7 | High | Done |
| Context auto-compression | 8 | High | Done |
| Multi-agent orchestration | 9 | High | Done |
| Hooks infrastructure (pre/post tool use) | 10 | Critical | Done |
| Permission modes (read-only, accept-edits, yolo) | 10 | Critical | Done |
| Per-tool allow/deny rules | 10 | High | Done |
| `/permissions` REPL command | 10 | High | Done |
| Web search tool | 11 | High | Done |
| Web fetch tool | 11 | High | Done |
| `/deep-research` skill | 11 | Medium | Done |
| Structured JSON output (`--output-format`) | 11 | High | Done |
| JSON Schema output (`--json-schema`) | 11 | Medium | Done |
| Stdin pipe support | 11 | Medium | Done |
| DEVAGENT.md per-project memory | 12 | High | Done |
| MEMORY.md persistent auto-memory | 12 | High | Done |
| `devagent init` / `devagent init-project` commands | 12 | High | Done |
| Four-level settings hierarchy | 12 | Medium | Done |
| `/context` token visualization | 13 | High | Done |
| `/goal <condition>` mode | 13 | High | Done |
| Diff viewer before writes (`--diff-preview`) | 13 | High | Done |
| `/clear`, `/rewind`, `/status` | 13 | Medium | Done |
| `/autocompact` dynamic threshold | 13 | Medium | Done |
| `/btw` side question | 13 | Low | Done |
| Agent definition files (.devagent/agents/) | 14 | High | Done |
| Worktree isolation per agent | 14 | High | Done |
| Persistent agent memory (cross-session) | 14 | High | Done |
| Background agents + `/fork` + `/tasks` | 14 | Medium | Done |
| `/loop` recurring prompt | 14 | Medium | Done |
| `/autofix-pr` watch mode | 14 | Medium | Done |
| Effort levels (`--effort low/high/max`) | 15 | High | Done |
| Extended thinking toggle | 15 | Medium | Done |
| `--bare` mode | 15 | Medium | Done |
| `--allow-tools` / `--add-dir` CI flags | 15 | Medium | Done |
| Vision / screenshot tool | 16 | Low | Done |
| Jupyter notebook tools | 16 | Low | Done |
| Todo tools (in-session task list) | 16 | Low | Done |
| MCP WebSocket + SSE transports | 39 | High | Done |
| OAuth 2.0 PKCE auth for MCP servers | 40 | High | Done |
| Diff preview + `--add-dir` flag | 41 | Medium | Done |
| `/keybindings` REPL command | 42 | Low | Done |
| In-memory session graph UI (`GET /`) | 43 | Medium | Done |
| MemoryPrism standalone library | — | — | Idea |

---

## Updated Timeline Summary

| Phase | Description | Target |
|---|---|---|
| 0 | Cleanup + new config + foundation | Done |
| 1 | ReAct loop + file/shell tools + sessions | Done |
| 2 | CodePrism integration + impact estimator | Done |
| 3 | Security Gate | Done |
| 4 | GitHub-native flows | Done |
| 5 | Multi-model router + TDD loop + session memory | Done |
| 6 | Open source polish + REST API + plugin interface | Done |
| 7 | Quick action, plan mode, skills, full bash, MCP server | Done |
| 8 | Context auto-compression | Done |
| 9 | Multi-agent orchestration | Done |
| 10 | Hooks + permission modes | Done |
| 11 | Web tools (web_search + fetch_url) | Done |
| 12 | DEVAGENT.md + MEMORY.md + 4-level config | Done |
| 13 | REPL depth: /context, /goal, diff viewer, /rewind | Done |
| 14 | Agent definition files + worktree + background agents | Done |
| 15 | Effort levels + extended thinking + CI polish | Done |
| 16 | Vision + notebooks + todo tools | Done |
| 27–30 | Ollama Cloud auth + model picker, tab completion, auto-suggest | Done (v1.4.0) |
| 31–38 | REPL commands, fan-out agents, notebook hardening, MCP project config | Done (v1.5.0) |
| 39–41 | WebSocket+SSE MCP, OAuth PKCE, diff preview, --add-dir | Done (v1.5.0) |
| 42–43 | /keybindings, in-memory session graph UI | Done (unreleased) |

---

---

## Future Work — Speed & Latency

*Research-backed ideas for dramatically reducing wall-clock latency and token cost.
None are scheduled yet — add to the next planning cycle when the core is stable.*

---

### S1 — Prompt Caching

Anthropic supports `cache_control` markers on stable prompt sections. Marking the
system prompt prefix (which contains tool definitions and project context — the
largest stable block) as cacheable reduces latency by 13–85% and token cost by
41–90% on cache hits.

**What's needed:**
- In `core/llm.py`, detect Anthropic provider and inject `"cache_control": {"type": "ephemeral"}`
  on the last content block of the stable system prompt prefix before the first
  dynamic element (tool results, history).
- Track cache hit rate in the token budget tracker — surface it in `/tokens`.

**Key principle:** Move all dynamic content (tool results, conversation history) to
the end of the prompt so the stable prefix is as long as possible. ProjectDiscovery
raised their cache hit rate from 7% to 84% by restructuring prompt order.

---

### S2 — DAG-Parallel Tool Execution (LLMCompiler Pattern)

Currently, tool calls execute sequentially even when they are independent.
LLMCompiler (from Stanford, 2023) lets the LLM emit a DAG of tool calls and a
joiner step; independent branches run via `asyncio.gather`. Benchmark: **3.6×
wall-clock speedup** on tasks with parallelisable tool calls.

**What's needed:**
- New optional execution mode: `agent.parallel_tools = true` in config.
- When the LLM response contains multiple tool calls with no declared dependency,
  gather them with `asyncio.gather` instead of running sequentially.
- Add `$depends_on` hint support in tool call args so the LLM can explicitly
  declare ordering for the cases that need it.
- Requires making all tool handlers truly async or wrapping sync handlers in
  `asyncio.to_thread`.

---

### S3 — Plan-then-Execute for Predictable Tasks

For well-scoped, predictable tasks (e.g. "implement this function", "fix this
failing test"), a plan-then-execute approach uses **3–5× fewer tokens** than
pure ReAct because the LLM doesn't re-reason about what to do next after every
tool call — it just follows the pre-computed plan.

**What's needed:**
- Extend the `--plan` mode (Phase 7) to also drive execution: after approval,
  the agent uses the plan as a strict execution script rather than re-running
  ReAct reasoning between each step.
- Detect "predictable" vs "exploratory" tasks heuristically (short clear task
  description with a clear output = predictable; open-ended = ReAct).
- Hybrid: start in plan-then-execute, fall back to ReAct if the plan step fails.

---

### S4 — Cache Boundary Optimisation

The Anthropic prompt cache uses the first `N` tokens as the cache key.
Any change before position `N` invalidates the cache for everything after it.
Moving dynamic content (dates, session IDs, conversation history) from the
front of the system prompt to the end maximises the stable prefix length.

**What's needed:**
- Audit `agent/system_prompt.py`: move any session-specific or turn-specific
  content (current date, session ID, tool results summary) below the stable
  tool definitions and project context.
- Add a `--debug-cache` flag that logs the cache boundary position and hit rate
  after each LLM call (Anthropic API returns `cache_read_input_tokens` in usage).

---

### S5 — Worktree-Parallel Execution

For tasks that decompose into non-overlapping file changes (e.g. "add type hints
to all public functions in the API layer"), workers can run in isolated git
worktrees simultaneously, coordinated through the existing `file_locks` SQLite
table. No merge conflicts because files don't overlap.

**What's needed:**
- Extend the Phase 9 multi-agent orchestrator with a `--parallel-worktrees N`
  flag that creates N git worktrees and assigns non-overlapping subtasks to each.
- Use CodePrism's impact graph to guarantee non-overlap before dispatch — if two
  subtasks touch the same file, serialise them.
- Merge worktree branches back to the working branch after all workers complete.
- Auto-detect when this mode is beneficial: only activate for tasks with ≥3
  non-overlapping subtasks identified in the planning phase.

---

### S6 — Streaming-First Output with Speculative Tool Calls

Currently the agent waits for the full LLM response before executing any tool
call. With streaming enabled, the tool call arguments are often complete well
before the response stream ends — especially for `file_read` and `grep` where
args are short.

**What's needed:**
- In `core/llm.py`, switch to the streaming API for all providers and parse
  tool call chunks as they arrive.
- When a tool call's arguments are fully received, dispatch it immediately in a
  background task without waiting for the rest of the stream.
- Particularly high-value for multi-tool responses: tools 2 and 3 start while
  the LLM is still generating tool 1's follow-up reasoning text.

---

## Benchmarking DevAgent

*B3, B4, and B5 are shipped as of v1.2.0 (Phase 17). B1 and B2 remain future work.*

---

### B1 — SWE-bench Evaluation (Industry Standard)

SWE-bench is the de facto standard for coding agent evaluation: 2,294 real
GitHub issues from popular Python repos, with PASS_TO_PASS + FAIL_TO_PASS tests
as the oracle. Newer variants address contamination and multi-language gaps.

**Recommended track:**
- **SWE-bench Verified** (500 human-validated, harder subset) — more meaningful
  than the full set; avoids the 19.78% false-positive rate from test coincidence.
- **SWE-bench Pro** — multi-file, contamination-resistant; closer to real work.
- **SWE-Compass** — 8-language variant if non-Python support matters.

**Known limitation:** A solution that passes all tests is not necessarily
semantically correct — 19.78% of "solved" cases pass by test coincidence.
Pair SWE-bench with human spot-checks on the top-ranking solutions.

**What's needed:**
- `devagent bench swe-bench [--split verified|full] [--subset N]`
- Runs the agent against a configurable number of SWE-bench instances
- Compares against published scores from Claude Code, Devin, Aider at the same date
- Report: `resolve_rate`, `avg_iterations`, `avg_cost_usd`, `avg_wall_time_sec`

---

### B2 — RIGORBENCH (Process Discipline)

RIGORBENCH measures 7 pillars of *process quality* rather than just end-state
correctness. A agent can solve a task correctly but with poor process — which
signals fragility on harder tasks.

| Pillar | What it measures |
|---|---|
| Planning Fidelity | Does the agent follow its stated plan? |
| Verification Coverage | Does it run tests / checks before declaring done? |
| Recovery Efficiency | How quickly does it recover from tool failures? |
| Abstention Quality | Does it correctly refuse tasks it cannot solve? |
| Atomic Transition Integrity | Are file edits minimal and correct? |
| Test Assertion Density | Are tests it writes meaningful (not just coverage)? |
| Exploration Efficiency | How many tool calls per token of useful context? |

**What's needed:**
- Implement as a set of evaluator hooks (Phase 10 hooks infrastructure) that
  observe agent execution without interfering with it.
- Each pillar is scored 0–1 per task run; aggregate across N runs for reliability.
- `devagent bench rigor --tasks tasks.json` — runs a curated task set with
  process logging enabled and produces a RIGOR scorecard.

---

### B3 — Real-World Task Set (DevAgent Native) ✓ Shipped (v1.2.0)

24 hand-curated tasks across Python, JavaScript, and Go fixture projects.
Each task runs the full agent loop with an oracle-verified pass/fail.

**Shipped:**
- `benchmarks/tasks/task_set.json` — 24 tasks (Python 20, JS 2, Go 2)
- `devagent bench native [--live] [--category] [--difficulty] [-t task-id]`
- Per-task breakdown: pass_rate, avg_iterations, avg_cost_usd, avg_duration_sec
- Latest score: gpt-oss:20b 21/24 (87.5%), llama3.2:3b 9/20 (45%)

---

### B4 — Cost-to-Correctness Curve ✓ Shipped (v1.1.0)

**Shipped:**
- `devagent bench sweep --params model,iterations` parameterised runner
- Results stored in `benchmarks/results/sweep_TIMESTAMP.json`
- First sweep: gpt-oss:20b vs glm-5.3-flash (PR #16)

---

### B5 — Regression Benchmark in CI ✓ Shipped (v1.2.0)

**Shipped:**
- `devagent bench canary [--threshold 0.8]` — fast canary with no LLM required
- Wired into `.github/workflows/canary.yml` on every PR to main
- `bench-persist.yml` saves results to `bench-results` branch and auto-updates `LEADERBOARD.md`
- `devagent bench leaderboard [--remote]` for ranked view across models

---

*End of DevAgent roadmap.*
