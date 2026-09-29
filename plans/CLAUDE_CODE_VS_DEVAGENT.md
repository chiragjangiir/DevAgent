# Claude Code vs DevAgent — Feature Comparison

> **Last updated:** August 2025  
> **Source:** Live research against code.claude.com docs + full DevAgent codebase audit  
> **Legend:** ✅ Has it | ❌ Missing | ⚠️ Partial

---

## Quick Verdict

| Dimension | Winner |
|---|---|
| Offline / local models | **DevAgent** (Ollama default, zero cloud required) |
| Security hardening | **DevAgent** (BLOCK/WARN gate, CVE checks, shell blocklist) |
| Codebase understanding | **DevAgent** (CodePrism graph — impact, callers, data flow) |
| GitHub flows | **DevAgent** (implement/review/triage/fix-ci as typed commands) |
| Auto-test repair | **DevAgent** (after every edit, runs tests, fixes failures) |
| Multi-agent typing | **DevAgent** (coordinator/implementer/tester/reviewer roles) |
| Hooks / automation | **Claude Code** (30+ events, 5 hook types — DevAgent has none) |
| Web access | **Claude Code** (WebSearch + WebFetch built-in) |
| Vision / Computer Use | **Claude Code** (screenshot, click, type) |
| Effort / thinking control | **Claude Code** (6 effort levels, extended thinking toggle) |
| Permission system | **Claude Code** (6 modes, per-tool allow/deny) |
| REPL command depth | **Claude Code** (40+ slash commands vs DevAgent's ~10) |
| Plugin ecosystem | **Claude Code** (distributable plugin bundles) |

---

## 1. Core CLI & Invocation

| Feature | Claude Code | DevAgent |
|---|---|---|
| Non-interactive one-shot | `claude -p "task"` | `devagent do "task"` ✅ |
| Resume session | `--continue` / `--resume <id>` | `devagent run --resume <id>` ✅ |
| Structured JSON output | `--output-format json` / `stream-json` | ❌ |
| JSON Schema structured output | `--json-schema <schema>` | ❌ |
| Skip all plugins/hooks/skills | `--bare` | ❌ |
| Auto-approve specific tools | `--allowedTools "Bash,Read"` | ❌ |
| Grant extra directory access | `--add-dir <path>` | ❌ |
| Override system prompt | `--system-prompt` / `--append-system-prompt` | ❌ |
| Start with specific agent | `--agent <name>` | ❌ |
| Permission mode at startup | `--permission-mode <mode>` | ❌ |
| Verbose / debug | N/A | `--verbose` ✅ |
| Exit codes | 0 = success, 143 = SIGTERM | 0 = success, 1 = error ✅ |

---

## 2. Tools Available to the Agent

| Tool | Claude Code | DevAgent |
|---|---|---|
| **File read** | `Read` | `read_file` ✅ |
| **File write** | `Write` | `write_file` ✅ (+ Security Gate) |
| **File edit (targeted)** | `Edit` | `edit_file` ✅ |
| **File list / glob** | `Glob` | `list_files`, `find_files` ✅ |
| **Content search** | `Grep` (ripgrep) | `grep` ✅ |
| **Shell execution** | `Bash` (blocking) | `run_shell` + `background=True` + `poll_shell` ✅ |
| **Web search** | `WebSearch` ✅ | ❌ |
| **Web fetch** | `WebFetch` ✅ | ❌ |
| **Spawn subagent** | `Agent` tool ✅ | via `orchestrate` command (not in-loop) ⚠️ |
| **Vision / Computer Use** | `Computer` (screenshot, click, type) ✅ | ❌ |
| **Jupyter notebooks** | `NotebookRead` + `NotebookEdit` ✅ | ❌ |
| **Todo / task tracking** | `TodoRead` + `TodoWrite` ✅ | ❌ |
| **Git operations** | Via Bash | 9 dedicated tools: `git_status`, `git_diff`, `git_log`, `git_show`, `git_branch`, `git_blame`, `git_branch_create`, `git_checkout`, `git_stash` ✅ |
| **GitHub API** | Via MCP or Bash | 9 dedicated tools: `gh_get_issue`, `gh_list_issues`, `gh_create_pr`, `gh_list_pr_files`, `gh_review_pr`, `gh_comment_issue`, `gh_branch_create`, `gh_list_workflow_runs`, `gh_get_run_logs` ✅ |
| **Session memory** | Via CLAUDE.md / MEMORY.md files | `remember_fact`, `recall_facts`, `forget_fact` ✅ |
| **Graph / impact analysis** | ❌ | 11 CodePrism tools: `cp_get_context`, `cp_get_impact`, `cp_get_callers`, `cp_get_callees`, `cp_search_symbol`, `cp_get_data_flow`, `cp_get_file_map`, `cp_get_module_summary`, `cp_get_dependencies`, `cp_undo_write`, `cp_get_stats` ✅ |

---

## 3. Models, Effort & Thinking

| Feature | Claude Code | DevAgent |
|---|---|---|
| Effort levels | ✅ `low` / `medium` / `high` / `xhigh` / `max` / `ultracode` | ❌ |
| Extended thinking toggle | ✅ `Alt+T`, `alwaysThinkingEnabled` setting, always-on for Fable | ❌ |
| Fast mode | ✅ `/fast` — 2.5× faster Opus | ❌ |
| 1M token context | ✅ `sonnet[1m]`, `opus[1m]` | ❌ |
| Switch model mid-session | ✅ `/model <name>` | ❌ |
| Multi-model auto-routing | ❌ manual only | ✅ planning / coding / reviewing / cheap — automatic per step |
| Offline / local models | ❌ API required | ✅ Ollama is the default provider |
| Providers | Anthropic only | ✅ Ollama, Anthropic, OpenAI, Gemini, Groq |
| Cost tracking | ✅ `/usage` / `/cost` | ✅ live per-model USD tracking |

---

## 4. REPL Slash Commands

### Session & Navigation

| Command | Claude Code | DevAgent |
|---|---|---|
| `/help` | ✅ | ✅ |
| `/exit` / `/quit` | ✅ | ✅ |
| `/clear` | ✅ start fresh (keeps memory) | ❌ |
| `/resume` | ✅ interactive session picker | ❌ (CLI flag only) |
| `/rewind` | ✅ roll back to earlier turn | ❌ |
| `/branch [name]` | ✅ conversation branch | ❌ |
| `/fork [prompt]` | ✅ copy to new background session | ❌ |
| `/background [prompt]` | ✅ detach as background agent | ❌ |
| `/tasks` | ✅ list background tasks | ❌ |

### Context & Memory

| Command | Claude Code | DevAgent |
|---|---|---|
| `/context [all]` | ✅ visual breakdown + optimization tips | ❌ |
| `/compact [instructions]` | ✅ with topic focus | ✅ (no topic focus) ⚠️ |
| `/autocompact [auto\|<tokens>]` | ✅ set threshold dynamically | ❌ (config-only) |
| `/memory` | ✅ edit CLAUDE.md | ✅ show MemoryBlock |
| `/recap` | ✅ re-read key context | ❌ |
| `/tokens` / `/cost` / `/usage` | ✅ | ✅ |

### Model & Config

| Command | Claude Code | DevAgent |
|---|---|---|
| `/model [model]` | ✅ switch mid-session | ❌ |
| `/effort [level]` | ✅ | ❌ |
| `/fast [on\|off]` | ✅ | ❌ |
| `/config` | ✅ settings UI | ✅ (CLI `config` command only) |
| `/theme` / `/color` | ✅ | ❌ |
| `/keybindings` | ✅ | ❌ |

### Code & Review

| Command | Claude Code | DevAgent |
|---|---|---|
| `/code-review [level] [--fix] [--comment]` | ✅ with PR comment posting | ✅ `review` command (no --fix flag) ⚠️ |
| `/security-review` | ✅ | ✅ `/security` (gate log) ⚠️ |
| `/simplify` | ✅ apply cleanups | ❌ |
| `/diff` | ✅ interactive diff viewer | ❌ |

### Planning & Orchestration

| Command | Claude Code | DevAgent |
|---|---|---|
| `/plan` | ✅ | ✅ `--plan` flag |
| `/batch <instruction>` | ✅ parallel codebase changes | ❌ (`orchestrate` is separate command) |
| `/goal <condition>` | ✅ work until condition met | ❌ |

### Automation & Research

| Command | Claude Code | DevAgent |
|---|---|---|
| `/deep-research <q>` | ✅ fan-out search + cited report | ❌ |
| `/loop [interval] [prompt]` | ✅ recurring scheduled prompt | ❌ |
| `/autofix-pr [prompt]` | ✅ watch PR, auto-fix CI | ❌ |
| `/btw <question>` | ✅ side question without context pollution | ❌ |

### Project Setup

| Command | Claude Code | DevAgent |
|---|---|---|
| `/init` | ✅ generate CLAUDE.md | ❌ |
| `/add-dir <path>` | ✅ | ❌ |
| `/cd <path>` | ✅ | ❌ |
| `/mcp` | ✅ manage MCP servers | ✅ |
| `/permissions` | ✅ per-tool rules | ❌ |
| `/doctor` | ✅ | ✅ |
| `/status` | ✅ | ❌ |

---

## 5. Multi-Agent Orchestration

| Aspect | Claude Code | DevAgent |
|---|---|---|
| **Mechanism** | `.claude/agents/*.md` YAML files + `Agent` tool | `devagent orchestrate` command + coordinator LLM call |
| **Worker types** | Custom per definition file | Typed: `coordinator` / `implementer` / `tester` / `reviewer` |
| **Parallelism** | Agent tool spawns subagents ad-hoc | Topological wave scheduling via `ThreadPoolExecutor` |
| **File conflict prevention** | Worktree isolation (separate git worktree per agent) | SQLite file-lock table (`acquire`/`release`) |
| **Agent memory** | Persistent `MEMORY.md` per agent (cross-session) | Session-scoped `MemoryBlock` only |
| **Tool restriction** | Per-agent `tools:` / `disallowedTools:` in YAML | Per-role list (implementer=all, tester=write+run, reviewer=read-only) |
| **Invocation** | `Agent()` tool call, `@agent-name` mention, `--agent` flag | `devagent orchestrate "task"` |
| **Plan approval gate** | `permissionMode: plan` in agent frontmatter | `--plan` flag shows decomposition before spawning |
| **Worktree isolation** | ✅ `isolation: worktree` in frontmatter | ❌ (file locks instead) |
| **Background agents** | ✅ `background: true` in frontmatter | ❌ |
| **In-loop spawn** | ✅ Claude can call `Agent()` mid-task | ❌ (orchestrate is top-level only) |
| **Built-in agent types** | ✅ Explore, Plan, General-purpose | ❌ |
| **Agent @-mention** | ✅ `@"agent-name"` | ❌ |
| **DAG task graph** | ❌ | ✅ dependency-aware wave execution |
| **Synthesis step** | ❌ | ✅ coordinator synthesises all worker results |

---

## 6. Permission System

| Feature | Claude Code | DevAgent |
|---|---|---|
| **Permission modes** | ✅ 6 modes: `default` / `acceptEdits` / `plan` / `auto` / `dontAsk` / `bypassPermissions` | ❌ |
| **Per-tool allow/deny** | ✅ `settings.json` + `/permissions` command | ❌ |
| **Auto-accept file edits** | ✅ `acceptEdits` mode | ❌ |
| **Read-only agent mode** | ✅ `plan` permission mode | ❌ |
| **Org-managed overrides** | ✅ managed settings layer | ❌ |
| **`Shift+Tab` cycle modes** | ✅ in-session toggle | ❌ |

---

## 7. Hooks System

> **This is the biggest single gap.** DevAgent has zero equivalent.

| Feature | Claude Code | DevAgent |
|---|---|---|
| **Hook infrastructure** | ✅ | ❌ |
| **Hook types** | ✅ `command` / `http` / `mcp_tool` / `prompt` / `agent` | ❌ |
| **Number of events** | ✅ 30+ events | ❌ |
| **Key events** | `PreToolUse`, `PostToolUse`, `SessionStart`, `SessionEnd`, `PermissionRequest`, `SubagentStart`, `PreCompact`, `PostCompact`, `FileChanged`, `UserPromptSubmit` | — |
| **Block tool use** | ✅ exit code 2 → blocks + stderr fed back to Claude | ❌ |
| **Rewrite tool input** | ✅ `updatedInput` JSON output field | ❌ |
| **HTTP hooks** | ✅ POST to any URL on event | ❌ |
| **Agent verification hooks** | ✅ multi-turn subagent verifies before proceeding | ❌ |
| **Timeout system** | ✅ 30s fast-path, 10min slow-path, per-type | ❌ |

---

## 8. Project Memory & Configuration

| Feature | Claude Code | DevAgent |
|---|---|---|
| **CLAUDE.md** | ✅ loaded every session; nested subdirectory-scoped; `paths:` frontmatter | ❌ (no per-session markdown file) |
| **MEMORY.md auto re-injection** | ✅ survives `/compact`, re-read from disk | ❌ |
| **Agent MEMORY.md** | ✅ per-agent, scoped to `user`/`project`/`local` | ❌ |
| **4-level settings hierarchy** | ✅ managed → project → project.local → user | ❌ TOML only |
| **Skills** | ✅ Markdown files, chained up to 6 in one message | ✅ TOML files in `~/.config/devagent/skills/` |
| **Plugins** | ✅ distributable bundles (agents + skills + hooks + MCP) | ❌ |
| **Prompt cache TTL control** | ✅ `promptCacheTtl: "5m"\|"1h"` | ❌ |
| **Session graph overlay** | ❌ | ✅ CodePrism session overlay injected each turn |

---

## 9. MCP (Model Context Protocol)

| Feature | Claude Code | DevAgent |
|---|---|---|
| **As MCP client** | ✅ http / stdio / sse / ws | ✅ (CodePrism client) |
| **As MCP server** | ✅ (Claude Code itself is an MCP server) | ✅ `devagent mcp` (stdio + SSE) |
| **OAuth 2.0 auth** | ✅ automatic flow + client credentials | ❌ |
| **Project `.mcp.json`** | ✅ version-controlled per-project config | ❌ |
| **Scoped configs** | ✅ local / project / user scopes | ❌ |
| **WebSocket transport** | ✅ `ws://` | ❌ |
| **MCP output token cap** | ✅ 25k default, `MAX_MCP_OUTPUT_TOKENS` env var | ❌ |
| **Expose CodePrism graph** | ❌ | ✅ `codeprism://graph/summary`, `symbols`, `dependencies` |

---

## 10. Security

| Feature | Claude Code | DevAgent |
|---|---|---|
| **Security gate (BLOCK writes)** | ❌ | ✅ blocks secrets, SQL injection, `eval(user_input)`, `pickle.loads` |
| **WARN writes (needs confirmation)** | ❌ | ✅ weak crypto, DEBUG=True, new deps |
| **CVE dependency check** | ❌ | ✅ OSV API for requirements.txt / pyproject.toml / package.json |
| **Shell hard blocklist** | ❌ | ✅ `rm -rf /`, `curl|bash`, `wget|bash`, `cat .env`, `shutdown`, etc. |
| **Impact scope before edit** | ❌ | ✅ `cp_get_impact` shown before every write |
| **Security log** | ❌ | ✅ `/security` in REPL shows BLOCK/WARN/REJECTED counts |

---

## 11. CI/CD & Headless

| Feature | Claude Code | DevAgent |
|---|---|---|
| **Non-interactive mode** | ✅ `claude -p "task"` | ✅ `devagent do "task"` |
| **JSON output for CI** | ✅ `--output-format json` / `stream-json` | ❌ |
| **Pipe stdin input** | ✅ `git diff main \| claude -p "review"` | ❌ |
| **GitHub Actions docs** | ✅ native integration guide | ❌ |
| **Session persistence** | ✅ | ✅ SQLite |
| **Exit codes** | ✅ 0/143 | ✅ 0/1 |

---

## 12. Context Window Management

| Feature | Claude Code | DevAgent |
|---|---|---|
| **Auto-compress** | ✅ `/autocompact` dynamically | ✅ `auto_compress: true` in config |
| **Manual compress** | ✅ `/compact [focus on X]` | ✅ `devagent session compress <id>` |
| **Topic-focused compression** | ✅ `/compact focus on auth module` | ❌ |
| **Context visualization** | ✅ `/context` — breakdown + suggestions | ❌ |
| **Rewind to earlier turn** | ✅ `/rewind` | ❌ |
| **1M token variants** | ✅ `[1m]` model suffix | ❌ |
| **Prompt cache control** | ✅ TTL settings | ❌ |
| **Compression model config** | ❌ | ✅ `compression_model = "cheap"` |

---

## 13. DevAgent-Only Features (Not in Claude Code)

These are DevAgent's unique differentiators:

| Feature | Details |
|---|---|
| **CodePrism graph integration** | Impact analysis, caller/callee graphs, data flow, token-efficient context (60–80% reduction) |
| **Offline-first (Ollama)** | All features work locally — zero cloud, zero API key required |
| **Multi-model auto-routing** | Automatically uses planning/coding/reviewing/cheap model per step type |
| **Auto-test repair loop** | After every `write_file`/`edit_file`, finds test file via CodePrism, runs it, repairs failures (max 3 attempts) |
| **Security gate (hard BLOCK)** | Secrets, SQL injection, `eval(user_input)`, `pickle.loads(untrusted)` — rejected before write |
| **CVE dependency checking** | OSV API check on new deps in requirements/pyproject/package.json |
| **Shell hard blocklist** | `rm -rf /`, `curl|bash`, `wget|bash`, `cat .env` — always blocked |
| **Stateful background shell** | `run_shell(background=True)` + `poll_shell(pid)` for long-running commands |
| **GitHub first-class flows** | `implement`, `review`, `triage`, `fix-ci` as typed, pre-built agent flows |
| **Typed multi-agent workers** | Coordinator decomposes → DAG wave execution → synthesis; implementer/tester/reviewer roles |
| **Repo health watcher** | `devagent watch` — continuous background monitoring with scheduled reports |
| **Session graph overlay** | CodePrism session context injected every turn (what was read, written, analysed) |
| **Multi-provider support** | Ollama, Anthropic, OpenAI, Gemini, Groq — switchable per config |

---

## Gap Priority for Future Phases

Ordered by impact:

| # | Gap | Group |
|---|---|---|
| 1 | Hooks system (PreToolUse / PostToolUse / block / rewrite) | H |
| 2 | Permission modes + per-tool allow/deny | F |
| 3 | Web search + Web fetch tools | A |
| 4 | `--output-format json/stream-json` + `--json-schema` | C |
| 5 | CLAUDE.md / MEMORY.md project memory files | G |
| 6 | Agent definition files + worktree isolation | E |
| 7 | Persistent agent memory (cross-session) | E |
| 8 | `/goal` mode | D |
| 9 | Effort levels + extended thinking | B |
| 10 | `/context` visualization | D |
| 11 | `/autocompact` dynamic threshold | D |
| 12 | Background agents + `/fork` + `/tasks` | D |
| 13 | `/deep-research` | D |
| 14 | Vision / Computer Use | A |
| 15 | Jupyter Notebook tools | A |
| 16 | `/diff` interactive viewer | D |
| 17 | MCP OAuth + `.mcp.json` project file | I |
| 18 | `/rewind` conversation | D |
| 19 | Structured output (`--json-schema`) | C |
| 20 | Fast mode + 1M context variants | B |
