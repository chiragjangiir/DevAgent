# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.5.0] - 2026-09-30

### Added

**REPL command expansion (Phases 32, 34, 36)**
- `/fast` — toggles fast mode (streaming vs. single-shot) on the fly without restarting the session
- `/compact [focus]` — compresses session history to a summary; optional `focus` string biases what's kept
- `/recap` — prints a structured summary of the current session: files touched, tools called, decisions made
- `/branch` — shows the current git branch and lets you switch without leaving the REPL
- `/theme <name>` — switches the Rich colour theme live (dark, light, monokai, etc.)

**Fan-out and background agents (Phases 37, 38)**
- `/batch <glob>` — fans out a sub-agent per matched file in parallel; results are collected and rendered as a table; each sub-agent runs in its own worktree when `isolation = "worktree"` is set
- `/background <task>` — fires a task as a background daemon agent and returns immediately; status visible via `/tasks`

**Notebook tools hardened (Phase 33)**
- Suppressed the `nbformat` version warning that leaked into tool output on every call
- Added 14 new notebook-tool tests covering cell execution, output capture, and round-trip save

**`emit_json` output mode (Phase 34)**
- `devagent do "<task>" --emit-json` — prints a machine-readable JSON envelope (`{event, text, tool_calls, …}`) instead of Rich-formatted output; suitable for piping into jq or CI scripts

**`.mcp.json` project MCP server config (Phase 35)**
- Projects can drop a `.mcp.json` at their root to declare MCP servers; `MCPManager` loads and connects them automatically at session start
- Supports `stdio`, `websocket`, and `sse` transports in the same file
- `devagent mcp list` reads `.mcp.json` and shows connection status for each entry

**WebSocket + SSE MCP transport (Phase 39)**
- `connect_websocket(name, url)` and `connect_sse(name, url, headers)` async context managers in `devagent/mcp/transports/`
- `connect_entry()` dispatcher routes `transport = "websocket"` or `"sse"` entries from `.mcp.json` automatically
- `MCPManager._connect_remote_servers()` best-effort connects all non-stdio servers at startup; unreachable servers are skipped with a warning
- WebSocket import is lazy so older `mcp` builds that lack the module still work

**OAuth 2.0 PKCE auth for MCP servers (Phase 40)**
- Full authorization-code + PKCE flow (`pkce_authorize`): generates a code verifier, computes the SHA-256 challenge, opens the browser, starts a local redirect server, exchanges the code for tokens
- `refresh_token_flow()` — silently refreshes an expired access token
- Platform keyring token cache (`devagent/mcp/auth/token_cache.py`): tokens survive process restarts; 60-second expiry buffer prevents last-second failures; graceful no-op when keyring is unavailable
- `OAuthConfig` dataclass + `MCPServerEntry.auth` field — declare auth in `.mcp.json` under an `auth:` key

**Diff viewer before writes + `--add-dir` (Phase 41)**
- `--diff-preview` flag on `devagent run` — before each `write_file` or `edit_file`, shows a syntax-highlighted unified diff (Rich + monokai) and prompts the user to accept or reject; the file is not touched on rejection
- `--add-dir <path>` flag (repeatable) on `run` and `do` — grants the agent read/write access to directories outside `project_root`; path-traversal guard still applies across all allowed roots
- `diff_confirm_fn` callback is `None` in non-interactive / `--bare` mode so batch workflows are unaffected

---

## [1.4.0] - 2026-09-29

### Added

**Ollama Cloud auth (Phase 27)**
- `devagent init` now accepts an Ollama Cloud API key and `base_url`; auth is passed as `Authorization: Bearer <key>` header via `_ollama_client()` helper
- `_validate_ollama()` skips the local HTTP check for the cloud endpoint and returns a fast confirmation
- Cloud config fields (`base_url`, `api_key`) survive config save/reload

**Ollama Cloud model picker (Phase 28)**
- `list_ollama_models()` on `LLMClient` — fetches available models from the configured endpoint (local or cloud), returns `[]` on failure
- `devagent init` Cloud section shows a numbered list of available models; pick by number or type a name
- `/model` with no argument now shows a numbered list of available Ollama models; current model is marked with `←`
- `/model <N>` switches to the Nth model by index

**REPL tab completion and session naming (Phase 29)**
- `prompt_toolkit` word completer for all `/` commands — press Tab to complete
- `devagent run --name <name>` — start a named session
- `--resume <name>` — resume by human-readable name (falls back to ID prefix)
- `/rename <name>` in REPL — rename the current session
- Intro banner trimmed to one hint line; command list is discoverable via Tab

**Auto-suggest and /sessions (Phase 30)**
- `complete_while_typing=True` — suggestions appear as you type without pressing Tab
- `/sessions` REPL command — lists all sessions for the current project with name, short ID, last-updated time, and current-session marker
- `SessionManager.list_by_project()` — filters session store by project path

### Fixed
- `/sessions` crash when `updated_at` was a Unix float instead of a string
- Doubled API key in config when `devagent init` was run twice

### Changed
- `devagent chat` is now fully functional — loads the selected `.md` report into a DevAgentSession REPL so users can ask questions interactively without re-running `devagent analyze`

---

## [1.3.0] - 2026-09-25

### Added

**Agent definitions and worktree isolation (Phase 18–19)**
- `AgentDef.isolation = "worktree"` — `devagent agent run` creates a fresh git worktree for an agent and cleans it up when done; prevents concurrent agents from clobbering each other's edits
- `devagent init-project --generate` — LLM analyses `pyproject.toml`, `README.md`, and directory layout to write a project-specific `DEVAGENT.md`; falls back to a static template if the LLM is offline
- `load_devagent_md()` now walks ancestor directories (outermost first) so nested projects inherit parent-level instructions

**Per-agent persistent memory (Phase 20)**
- `AgentDef.memory = "project"` wires `.devagent/agent-memory/<name>/memory.md` — the agent reads it at start and writes to it via the `remember_persistent` tool; survives between invocations

**HTTP and prompt hook types (Phase 21)**
- New hook types: `http` (POST JSON to an external endpoint) and `prompt` (inject text into the next LLM call)
- Lifecycle events `session_start` and `session_end` now fire for all hook types, not just `shell`
- `devagent hooks test <event> <tool>` — dry-run any hook without starting a full session

**Structured output flag (Phase 22)**
- `devagent do "<task>" --json-schema '<schema>'` — validates `FinalAnswerEvent.text` against a JSON Schema; retries once with an augmented prompt on mismatch; exits with code 2 if the second attempt still fails
- Requires `jsonschema>=4.0.0` (added as a dependency)

**`/model` mid-session switch (Phase 23)**
- `/model <provider/model>` inside `devagent run` hot-swaps the active LLM for the rest of the session without restarting
- `/model <model>` (no slash) keeps the current provider and changes only the model name
- Validates provider names; supported: `ollama`, `anthropic`, `openai`, `gemini`, `groq`

**`autofix-pr` watch mode (Phase 24)**
- `devagent autofix-pr <pr-url>` — polls a PR every N seconds (default 120); on each new failed CI run, fetches job logs and fires a `DevAgentSession` to fix and push; on each new review comment, fires a session to address it
- `--poll-interval` and `--max-polls` flags for CI usage
- Existing failures and comments at startup are seeded into `seen` sets so they are not re-processed

**`@agent-name` REPL mention syntax (Phase 25)**
- `@code-reviewer please check the auth changes` inside `devagent run` spawns the named agent as a background daemon thread; progress is tracked via the task store
- Respects `AgentDef.isolation = "worktree"` for isolated execution
- Use `/tasks` to check status; agents are looked up from `.devagent/agents/*.toml` and the user config dir

**Plugin bundle format (Phase 26)**
- `PluginBundle` dataclass — third-party packages declare tools, skills, hooks, and MCP servers via the `devagent.plugins` entry-point group in their `pyproject.toml`
- `devagent plugins list` — discovers and renders all installed plugin bundles in a table
- `devagent plugins install <package>` — wraps `pip install` and reports success/failure
- `devagent tasks` — list all background agent tasks in the current process (running, done, failed)

---

## [1.2.0] - 2026-09-25

### Added
- 24-task benchmark set covering Python (20), JavaScript (2), and Go (2) fixture projects
- JS fixture project (`js_project/`) with `add-feature-001` and `test-write-js-001` tasks
- Go fixture project (`go_project/`) with `add-feature-go-001` and `test-write-go-001` tasks
- `devagent bench leaderboard` command — groups results by (model, provider), shows best and latest score
- `devagent bench leaderboard --remote` — fetches results from `bench-results` git branch
- `devagent bench leaderboard --output <file>` — writes markdown leaderboard to a file
- `LEADERBOARD.md` seeded with live benchmark scores (gpt-oss:20b: 21/24, llama3.2:3b: 9/20)
- CI auto-update step in `bench-persist.yml`: regenerates `LEADERBOARD.md` on main after every push
- `devagent bench history --remote` flag for fetching result files from the `bench-results` branch
- Go binary validation in canary workflow (ensures Go fixtures compile before running)
- Native dry-run results persisted to `bench-results` branch alongside canary JSON
- Multi-task `-t` flag (repeatable): `devagent bench native -t bug-fix-001 -t refactor-002`
- Model/provider metadata embedded in saved benchmark JSON files for leaderboard tracking

### Fixed
- `code-review-001`: raised `timeout_sec` from 60 → 120 to prevent API call timeouts
- `refactor-002`: removed false task description premise ("multiply bug is already fixed"); agent now runs pytest first to discover and fix failures before adding type hints
- `test-write-002`: added explicit import pattern, "run each function via shell to verify expected values before writing assertions", and raised `timeout_sec` to 300
- Multi-task `-t` flag: switched from `str | None` to `list[str] | None` so multiple `-t` values accumulate correctly
- Unicode check marks in canary output replaced with ASCII for cross-platform terminal compatibility

### Changed
- Benchmark result JSON format extended: `{"meta": {...}, "results": [...]}` envelope (backward compatible with old plain-list format)
- `BenchReport.save_json` accepts optional `model` and `provider` parameters
- `BenchReport.render_leaderboard` and `generate_leaderboard_md` added to `report.py`

## [1.1.0] - 2026-08-28

### Added
- `INTEGRATIONS.md` — setup guides for Claude Code, ChatGPT, Antigravity, GitHub Copilot, Cursor, Windsurf, VS Code, JetBrains, Zed
- `BENCHMARKS.md` — full benchmark documentation with per-task results table
- Ollama Cloud provider support (`gpt-oss:20b`, `nemotron-3-nano:30b`, `gemma4:31b`, 15+ hosted models)
- First live 20-task benchmark run: gpt-oss:20b scored 20/20 (100%)
- B4 cost-to-correctness sweep infrastructure: `devagent bench sweep` with parameter grid
- `devagent bench history` command for cross-run trend comparison
- `expected_files_touched` enforcement in benchmark runner — reports files missed or extra
- Syntax checking for `.py` files written during benchmark runs (auto-surfaces errors to model)
- Token-savings measurement in `bench_token_usage.py` using real CodePrism graph queries
- Real `call_count` tracking for iteration counting in live benchmark runs
- Phases 10–14: hooks infrastructure, permission modes, REPL UX improvements, agent definition files

### Fixed
- Removed `--skip-legacy` from CI — all legacy benchmark scripts pass reliably
- Benchmark oracle fixes: `DEVAGENT_OUTPUT.txt` auto-write, syntax check, task-id filter

### Changed
- README overhauled to match the full current feature set (Phases 1–16 complete)

## [0.3.0] - 2026-08-13

### Added
- New `devagent watch` command to monitor a GitHub repository for newly opened issues
- Watcher storage, scheduler, and reporting flow for recurring repository health checks
- Cross-issue conflict detection to flag files touched by multiple open issues
- Watcher-specific terminal rendering for watched repos, health reports, and stored analyses

### Changed
- GitHub client now supports listing repository issues for watcher checks
- Configuration now includes watcher defaults such as interval, labels, and cross-conflict behavior
- Added `apscheduler` runtime support and enabled automatic asyncio handling for pytest

### Fixed
- Added watcher-focused tests covering conflict detection, analysis building, and watcher storage

## [0.2.0] - 2026-08-11

### Added
- Direct GitHub issue and pull request URL input for `devagent analyze` via `--url`
- Interactive terminal chat sessions for exploring a generated gap analysis
- Compact chat-focused report rendering and conversation history support
- Test coverage for GitHub URL parsing and chat prompt grounding

### Changed
- `devagent analyze` can now open a chat session immediately with `--chat`
- Pull request URLs are analyzed as specifications using PR title and description
- Spec analysis MCP server integration now uses `FastMCP`

### Fixed
- Configuration path resolution now supports the legacy `SPECSYNC_CONFIG_PATH` override
- Test imports and assertions were aligned with the `devagent` package naming

## [0.1.1] - 2026-08-10

### Fixed
- Initial bug fixes and stability improvements

## [0.1.0] - 2026-08-09

### Added
- Initial release of DevAgent
- Automated gap analysis between specifications and codebase
- Local LLM support via Ollama
- Model Context Protocol (MCP) integration
- Semantic search with ChromaDB
- Rich terminal UI and Markdown report generation
