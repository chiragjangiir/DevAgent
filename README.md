<div align="center">

# DevAgent

**An AI coding agent for your terminal. Offline-first, GitHub-native, benchmarked at 21/24 (87.5%) on real coding tasks.**

[![PyPI version](https://img.shields.io/pypi/v/devagent.svg)](https://pypi.org/project/devagent/)
[![Python Versions](https://img.shields.io/pypi/pyversions/devagent.svg)](https://pypi.org/project/devagent/)
[![License: MIT](https://img.shields.io/pypi/l/devagent.svg)](LICENSE)


</div>

---

DevAgent is a terminal-based AI coding agent that operates on your local codebase. You describe a task in plain language — implement this GitHub issue, review this pull request, fix the failing CI, refactor this module — and the agent reads your files, reasons about the code, makes changes, runs your tests, and reports what it did. It runs fully offline by default using Ollama and is built to complement whatever editor or AI tool you already use, not replace it.

---

## Table of contents

- [What problem it solves](#what-problem-it-solves)
- [How it works](#how-it-works)
- [Supported LLM providers](#supported-llm-providers)
- [Installation](#installation)
- [Quick start](#quick-start)
- [Integrations](#integrations)
- [Benchmarks](#benchmarks)
- [Commands reference](#commands-reference)
- [REPL commands](#repl-commands)
- [GitHub workflows](#github-workflows)
- [Configuration](#configuration)
- [Session management](#session-management)
- [Security gate](#security-gate)
- [Background watcher](#background-watcher)
- [Agent definitions](#agent-definitions)
- [Hooks](#hooks)
- [Effort levels](#effort-levels)
- [Skills](#skills)
- [Plugin bundles](#plugin-bundles)
- [REST API](#rest-api)
- [Writing plugin tools](#writing-plugin-tools)
- [Contributing](#contributing)
- [License](#license)

---

## What problem it solves

Most AI coding tools fall into one of two categories: chat assistants that can reason about code but cannot actually run or edit it, and editor plugins that complete the next few lines but cannot handle multi-step tasks. Neither category handles the full loop of understanding a requirement, identifying which files need to change, making those changes, verifying them with tests, and committing a working result.

DevAgent is built to close that gap. It handles the execution layer — actually reading files, writing code, running commands, querying your version control history — while you stay in control of reviewing and accepting changes.

Three specific problems it addresses:

**Token cost and context quality.** When you paste a 2,000-line file into a chat window, most of that content is irrelevant to your question. DevAgent integrates with [CodePrism](https://pypi.org/project/codeprism-ai/), a persistent code knowledge graph built from your codebase's AST and import graph. The agent queries the graph to find which functions, classes, and modules are relevant to the current task, then injects only those into context. In practice this reduces token usage by 60–80% on large codebases compared to naively dumping files.

**Privacy and offline capability.** The default LLM provider is Ollama, which runs entirely on your machine. Your source code never leaves your network unless you explicitly configure a cloud provider. Cloud APIs (Anthropic, OpenAI, Gemini, Groq) are opt-in for tasks where you want higher model capability.

**Multi-step task execution.** Implementing a feature typically involves reading several files to understand context, writing or editing code, running tests, fixing failures, and sometimes making follow-up edits. DevAgent handles this as a single continuous session with persistent memory, rather than requiring you to manually copy-paste context between steps.

---

## How it works

DevAgent uses a ReAct (Reason + Act) loop. On each turn the LLM decides what to do next — read a file, run a shell command, edit a module, call the GitHub API — executes that action using a tool, and incorporates the result before deciding the next step. This continues until the task is complete or a final answer is reached.

The loop is driven by a set of built-in tools: file reading and writing, shell execution, git operations, grep and search, GitHub API calls, CodePrism graph queries, web search and fetch, image/vision analysis, Jupyter notebook reading and editing, and todo tracking. You can extend it with custom tools through the plugin registry (see [Writing plugin tools](#writing-plugin-tools)).

For complex tasks, `devagent orchestrate` decomposes the work into sub-tasks and runs multiple worker agents in parallel. A planner agent breaks down the high-level goal, workers execute in parallel with shared project context, and a coordinator synthesises the results.

Sessions are persisted in a local SQLite database. You can close the terminal, return later, and resume exactly where you left off. Token usage and estimated cost are tracked per session and displayed live.

---

## Supported LLM providers

| Provider | Models | Offline | Best for |
|---|---|---|---|
| **Ollama** (default) | qwen2.5-coder:7b, llama3.2, deepseek-coder, any pulled model | Yes | Privacy-sensitive projects; day-to-day use |
| **Ollama Cloud** | gpt-oss:20b, nemotron-3-nano:30b, gemma4:31b, and 15+ hosted models | No | Higher capability without switching provider APIs |
| **Anthropic** | claude-sonnet-4-6, claude-opus-4-8, claude-haiku-4-5 | No | Complex reasoning, long-context tasks |
| **OpenAI** | gpt-4o, gpt-4o-mini, o1, o3-mini | No | General coding, broad language support |
| **Google Gemini** | gemini-1.5-pro, gemini-2.0-flash | No | Long context windows, multi-modal tasks |
| **Groq** | llama-3.3-70b-versatile, llama-3.1-8b-instant | No | Fast inference on open-weight models |

All providers use their official Python SDKs. There is no LangChain or LangGraph dependency.

**Multi-model routing.** You can assign different providers and models to different task types. For example, use a small local model for file reads and a stronger cloud model only when the agent is writing or reviewing code. See [Configuration](#configuration) for the router setup.

---

## Installation

Install with `pipx` to keep dependencies isolated from your system Python:

```bash
pipx install devagent
```

Or install into a virtual environment:

```bash
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install devagent
```

**Python requirement:** 3.12 or 3.13.

**Optional — Ollama:** Required for offline use. Download from [ollama.com](https://ollama.com), then pull a model:

```bash
ollama pull qwen2.5-coder:7b
```

**Optional — Node.js:** Required only if you enable the GitHub MCP server integration. Download from [nodejs.org](https://nodejs.org).

**Optional — CodePrism:** The knowledge graph integration. Install separately if not already pulled as a dependency:

```bash
pip install codeprism-ai
```

---

## Quick start

```bash
# Step 1: run the setup wizard
devagent init
```

The wizard prompts for your LLM provider and optionally a GitHub token. All settings are written to a TOML config file — you can edit it directly at any time.

```bash
# Step 2: go to your project root and index the codebase
cd /path/to/your/project
devagent index
```

Indexing builds the CodePrism knowledge graph from your source files. It takes a few seconds for small projects and a couple of minutes for large ones. Run it again after significant code changes; it performs an incremental update automatically.

```bash
# Step 3: (optional) create a DEVAGENT.md project config
devagent init-project
```

This creates a `DEVAGENT.md` file at your project root. The agent reads it at session start and uses it for project-specific instructions: tech stack, test command, code conventions, important paths. Edit it to suit your project.

```bash
# Step 4: start an interactive session
devagent run
```

You now have an interactive session. Type any task in plain language:

```
> explain what src/auth/middleware.py does
> add rate limiting to the login endpoint
> run the tests for the auth module and fix any failures
> implement issue #47 from our GitHub repository
```

The agent works through the task step by step, showing its reasoning and the results of each tool call. When it finishes, you can review the changes in your editor and continue or close the session.

**Run a single task non-interactively:**

```bash
devagent do "add a clamp() function to src/math_utils.py and write a test for it"
```

Exits with code 0 on success, 1 on error. Use `--output-format stream-json` for machine-readable output in CI pipelines.

**Resuming a session:**

```bash
devagent session list
devagent session resume <session-id>
```

---

## Integrations

DevAgent pairs well with every major AI tool and editor. See **[INTEGRATIONS.md](INTEGRATIONS.md)** for full setup guides covering:

- **Claude and Claude Code** — use Claude as the reasoning engine, or run alongside Claude Code for complementary workflows
- **ChatGPT / OpenAI Codex** — route DevAgent through GPT-4o or o1; use ChatGPT for design decisions and DevAgent for execution
- **Antigravity** — terminal integration + MCP server for CodePrism graph access
- **GitHub Copilot** — Copilot handles inline completion; DevAgent handles multi-step implementation
- **Cursor, Windsurf, VS Code, JetBrains, Zed** — run DevAgent in the integrated terminal alongside any editor AI

---

## Benchmarks

DevAgent ships with a 24-task benchmark covering bug fixes, feature adds, refactors, test writing, security audits, and onboarding tasks across Python, JavaScript, and Go fixture projects. Each task runs the full agent loop and passes only if a `pytest` or assertion oracle exits 0.

| Rank | Model | Provider | Best Score | Runs |
|---|---|---|---|---|
| 1 | **gpt-oss:20b** | **Ollama Cloud** | **21/24 (87.5%)** | 2 |
| 2 | llama3.2:3b | Ollama (local) | 9/20 (45%) | 1 |

See **[BENCHMARKS.md](BENCHMARKS.md)** for per-task results, failure analysis, and instructions for running the benchmark against any supported model. See **[LEADERBOARD.md](LEADERBOARD.md)** for the auto-updated rankings.

```bash
# Run against any model
devagent bench native --live --model gpt-oss:20b --provider ollama

# View the leaderboard
devagent bench leaderboard
```

---

## Commands reference

### Interactive and non-interactive sessions

| Command | Description |
|---|---|
| `devagent run` | Start an interactive REPL session in the current directory |
| `devagent run --effort <level>` | Set reasoning effort: `low`, `medium`, `high`, `xhigh`, `max` |
| `devagent run --bare` | Skip DEVAGENT.md, memory, CodePrism, and permission gate |
| `devagent run --plan` | Require plan approval before every task |
| `devagent run --allow <pattern>` | Auto-approve tool calls matching pattern (repeatable) |
| `devagent run --deny <pattern>` | Auto-deny tool calls matching pattern (repeatable) |
| `devagent run --diff-preview` | Show a syntax-highlighted unified diff and prompt accept/reject before each file write or edit |
| `devagent run --add-dir <path>` | Grant read/write access to a directory outside `project_root` (repeatable) |
| `devagent run --ui` | Open the live session graph UI in the browser when the server starts |
| `devagent do "<task>"` | Run a single task non-interactively; exits 0/1 |
| `devagent do "<task>" --json-schema '<schema>'` | Validate response against a JSON Schema; retries once; exit 2 on second failure |
| `devagent do "<task>" --output-format stream-json` | Machine-readable output for CI pipelines |
| `devagent do "<task>" --add-dir <path>` | Grant access to additional directories for this run (repeatable) |
| `devagent orchestrate "<task>"` | Decompose task and run parallel worker agents |
| `devagent orchestrate "<task>" --workers N` | Control worker parallelism |
| `devagent orchestrate "<task>" --plan` | Review the decomposition plan before starting workers |

### Setup and configuration

| Command | Description |
|---|---|
| `devagent init` | Run the setup wizard (LLM provider, GitHub token) |
| `devagent init-project` | Create a `DEVAGENT.md` project config in the current directory |
| `devagent init-project --generate` | Use the LLM to generate a project-specific `DEVAGENT.md` from the codebase |
| `devagent doctor` | Check provider connectivity, index status, offline capability |
| `devagent config --show` | Print current configuration |
| `devagent config --set key=value` | Set a configuration value |

### Codebase indexing and analysis

| Command | Description |
|---|---|
| `devagent index` | Build or update the CodePrism knowledge graph |
| `devagent index --full` | Force a complete re-index |
| `devagent index --status` | Show index statistics |
| `devagent onboard` | Architecture overview: file map, coupled files, symbols, test gaps |
| `devagent analyze` | Run a codebase analysis report |
| `devagent search "<query>"` | Search the knowledge graph |
| `devagent reports` | List and view saved analysis reports |

### GitHub flows

| Command | Description |
|---|---|
| `devagent implement <issue-url>` | Implement a GitHub issue end-to-end |
| `devagent review <pr-url>` | Review a pull request and post inline comments |
| `devagent triage <owner/repo>` | Triage open issues with labels and effort estimates |
| `devagent fix-ci <run-url>` | Analyse a failed CI run and push a fix |
| `devagent autofix-pr <pr-url>` | Watch a PR, auto-fix new CI failures and review comments, then push |
| `devagent autofix-pr <pr-url> --poll-interval 60` | Poll every 60 seconds instead of the default 120 |

### Agent definitions

| Command | Description |
|---|---|
| `devagent agent run <name> <task>` | Run a named agent definition against a task |
| `devagent agent list` | List agent definitions loaded from `.devagent/agents/*.toml` |

### Hooks

| Command | Description |
|---|---|
| `devagent hooks list` | List configured hooks |
| `devagent hooks test <event> <tool>` | Dry-run a hook for a given lifecycle event and tool name |

### Skills

| Command | Description |
|---|---|
| `devagent skills list` | List all available skills |
| `devagent skills new <name>` | Create a new skill interactively |

Skills are reusable task templates invoked with `/<skill-name>` inside a REPL session.

### Plugins

| Command | Description |
|---|---|
| `devagent plugins list` | List all installed plugin bundles |
| `devagent plugins install <package>` | Install a plugin bundle from PyPI or a local path |

### Tasks

| Command | Description |
|---|---|
| `devagent tasks` | List background agent tasks in the current process (running / done / failed) |

### Sessions

| Command | Description |
|---|---|
| `devagent session list` | List all sessions with token usage and date |
| `devagent session resume <id>` | Resume a previous session |
| `devagent session compress` | Compress session history to reduce token usage |
| `devagent session delete <id>` | Delete a session and its history |

### Background watcher

| Command | Description |
|---|---|
| `devagent watch --repo owner/repo --start` | Start background monitoring of a repository |
| `devagent watch --status` | Show watcher state and recent analyses |
| `devagent watch --stop` | Stop the background watcher |

### Benchmark

| Command | Description |
|---|---|
| `devagent bench native` | Dry-run: validate oracle/fixtures without calling the LLM |
| `devagent bench native --live --model <m> --provider <p>` | Live run against a model |
| `devagent bench native --category <c>` | Filter by category (`bug_fix`, `feature_add`, …) |
| `devagent bench native --difficulty <d>` | Filter by difficulty (`easy`, `medium`, `hard`) |
| `devagent bench native -t <id>` | Run one task by ID (repeatable: `-t id1 -t id2`) |
| `devagent bench leaderboard` | Show ranked results grouped by (model, provider) |
| `devagent bench leaderboard --remote` | Fetch latest results from the `bench-results` branch |
| `devagent bench leaderboard --output <file>` | Write markdown leaderboard to a file |
| `devagent bench history` | Show per-task pass/fail trend across saved result files |
| `devagent bench canary` | Run the fast CI canary (no LLM required) |

### Server

| Command | Description |
|---|---|
| `devagent serve` | Start the REST + WebSocket API server on port 7331 |
| `devagent serve --port 8080` | Start on a custom port |
| `devagent serve --ui` | Start server and open the live session graph UI in the browser |

---

## REPL commands

The interactive session (`devagent run`) recognises a set of `/` and `@` commands on top of plain task input.

**Session & context**

| Command | Description |
|---|---|
| `/help` | Show available REPL commands |
| `/status` | Session ID, project, model, tokens used, iteration count, compression count |
| `/context` | Live token breakdown: system prompt / memory / history / hot-window |
| `/memory` | Show or edit the current session memory block |
| `/tokens` | Detailed token usage and cost breakdown by model |
| `/sessions` | List all sessions for the current project (name, ID, last updated) |
| `/rename <name>` | Rename the current session |
| `/clear` | Reset the conversation (keeps persistent memory, wipes history) |
| `/rewind [N]` | Remove the last N turns from history (default 1) |

**Models & effort**

| Command | Description |
|---|---|
| `/model <provider/model>` | Hot-swap the active LLM (e.g. `/model anthropic/claude-opus-4-8`) |
| `/model <model>` | Change model only, keep current provider |
| `/model` | Show numbered list of available Ollama models; pick by number |
| `/effort <level>` | Switch effort level for the next turn (`low` / `medium` / `high` / `xhigh` / `max`) |
| `/think [on\|off]` | Toggle extended thinking (Anthropic models only) |
| `/fast [off]` | Toggle fast mode — swaps to the cheap router tier; `/fast off` restores |

**History & compression**

| Command | Description |
|---|---|
| `/compact [focus on <topic>]` | Compress session history; optional focus string biases what is kept |
| `/autocompact [<tokens>\|off]` | Set or clear the auto-compress token threshold |
| `/recap [N]` | Print the last N messages (default 5) to re-orient after a break |

**Agent & background tasks**

| Command | Description |
|---|---|
| `/fork <task>` | Spawn a background copy of the current session for a sub-task |
| `@agent-name <task>` | Spawn a named agent definition as a background task |
| `/tasks` | List all background tasks with status and elapsed time |
| `/background <task>` | Fire a task as a long-running detached subprocess |
| `/batch <task> -- <glob>` | Fan out a sub-agent per matched file in parallel |
| `/loop N <cmd>` | Repeat a command every N seconds (`/loop off` to cancel) |

**Workflows**

| Command | Description |
|---|---|
| `/goal <condition>` | Loop until the goal condition is met (e.g. `/goal all tests pass`) |
| `/diff` | Re-show the last file diff rendered before a write |
| `/btw <question>` | Ask a side question; response is NOT added to conversation history |
| `/security` | Show the security gate log for this session |
| `/permissions` | Show current permission mode and per-tool allow/deny rules |
| `/undo` | Undo the last file write or edit |

**Git & UI**

| Command | Description |
|---|---|
| `/branch` | Show the current git branch (and switch if a branch name is given) |
| `/theme <name>` | Switch the Rich colour theme (`default`, `dracula`, `monokai`, `solarized`) |
| `/keybindings` | Show keyboard shortcut reference table |

**Built-in skills**

| Command | Description |
|---|---|
| `/explain [path]` | Explain what a file or function does |
| `/test [path]` | Run tests for a file and show coverage gaps |
| `/review` | Review staged git changes before committing |
| `/commit [message]` | Stage, write a commit message, and commit |
| `/summarize` | Summarise what the session has done so far |
| `/deep-research <query>` | Multi-step web research → cited report |

**Other**

| Command | Description |
|---|---|
| `!<shell command>` | Run a shell command and print the output |
| `/exit` | End the session |

**Switching models mid-session:**

```
> /model ollama/qwen2.5-coder:7b
Model switched to ollama/qwen2.5-coder:7b

> /model anthropic/claude-opus-4-8
Model switched to anthropic/claude-opus-4-8
```

**Spawning a named agent:**

```
> @code-reviewer please check the auth changes for security issues
Spawned @code-reviewer [a3f2d1c0]: please check the auth changes for security issues
Check progress with /tasks
```

---

## GitHub workflows

DevAgent treats GitHub as a first-class integration. All GitHub commands accept full issue or PR URLs, so you do not need to configure a default repository.

**Implement an issue:**

```bash
devagent implement https://github.com/owner/repo/issues/42
```

The agent fetches the issue description, analyses which parts of your codebase are affected using the code graph, writes the implementation, runs the relevant tests, and summarises what changed. You review and commit.

**Review a pull request:**

```bash
devagent review https://github.com/owner/repo/pull/17
```

The agent fetches the PR diff, checks the changed code against the repository's conventions, identifies potential bugs or missing test cases, and posts inline review comments via the GitHub API.

**Triage a backlog:**

```bash
devagent triage owner/repo
```

The agent reads all open issues, estimates effort (trivial / small / medium / large), suggests label assignments, and identifies which issues conflict with or depend on each other.

**Fix a failed CI run:**

```bash
devagent fix-ci https://github.com/owner/repo/actions/runs/12345
```

The agent fetches the CI log, identifies the failing step, reads the relevant source files, proposes and applies a fix, and runs the test locally to verify before you push.

**Auto-fix a PR in watch mode:**

```bash
devagent autofix-pr https://github.com/owner/repo/pull/42
```

Polls the PR in a loop. When a new CI run fails it fetches the job logs, fires an agent session to diagnose and fix the code, then pushes. When a new review comment appears it fires a session to address it. Uses `--poll-interval` (default 120 s) and `--max-polls` to control how long it runs.

**Requirement:** A GitHub Personal Access Token with `repo` scope. Set it once:

```bash
devagent config --set github.token=ghp_...
```

---

## Configuration

DevAgent stores configuration in TOML format:

- **Linux / macOS:** `~/.config/devagent/config.toml`
- **Windows:** `%APPDATA%\devagent\config.toml`

**LLM provider:**

```toml
[llm]
provider = "ollama"            # ollama | anthropic | openai | gemini | groq
model    = "qwen2.5-coder:7b"
base_url = "http://localhost:11434"   # Ollama only; omit for cloud providers
```

**Multi-model router:**

Use different providers for different stages of a task. The agent automatically selects the appropriate model based on what it is doing.

```toml
[router]
planning  = { provider = "anthropic", model = "claude-sonnet-4-6" }
coding    = { provider = "ollama",    model = "qwen2.5-coder:7b" }
reviewing = { provider = "anthropic", model = "claude-haiku-4-5-20251001" }
cheap     = { provider = "ollama",    model = "qwen2.5-coder:7b" }
fallback  = { provider = "ollama",    model = "qwen2.5-coder:7b" }
```

**GitHub:**

```toml
[github]
token        = "ghp_..."
default_repo = "owner/repo"    # optional; used when no repo is specified
```

**Token budget:**

```toml
[session]
max_tokens  = 200000    # hard stop; agent halts if this is reached
warn_at_pct = 80        # warn when 80% of budget is consumed
```

**Setting values from the CLI:**

```bash
devagent config --set llm.provider=anthropic
devagent config --set llm.model=claude-sonnet-4-6
devagent config --set session.max_tokens=100000
```

---

## Session management

Sessions persist between terminal restarts. Every message, tool call, and result is stored in a local SQLite database. Token usage is tracked per model and converted to USD cost using built-in rate tables.

```bash
devagent session list
```

```
ID          Title                          Model                  Updated
a1b2c3d4    Implement rate limiting        ollama/qwen2.5-coder   2026-08-21 14:32
e5f6a7b8    Review PR #17                  anthropic/sonnet-4.6   2026-08-20 09:15
```

```bash
devagent session resume a1b2c3d4
```

Resuming restores the full message history and memory block. The agent has access to everything it said and did in the previous session.

**Session memory** is a separate key-value store you can read and write during a session:

```
> remember that the payment module uses Stripe's v3 API
> what do you know about the payment module?
```

Memory entries persist across resumes and are injected into every LLM call as a compact block (~200 tokens), so the agent always has the key facts without replaying the entire history.

---

## Security gate

Every file write passes through a security scanner before hitting disk. The gate has two levels:

**Block** — write is rejected and an error is returned to the agent:

- Hardcoded secrets or API keys in source files
- `eval(user_input)` or `exec(user_controlled_string)` patterns
- Path traversal attempts (`../../etc/passwd`)
- `subprocess.run(user_input, shell=True)` with untrusted input
- Known CVE patterns (configurable)

**Warn** — write proceeds only after confirmation:

- `chmod 777` on sensitive paths
- `curl | bash` or equivalent install-from-internet patterns
- Disabling authentication or rate limiting via code comments
- Development keys or test credentials that look real

Security events are logged per session. Run `devagent session list` and inspect a session to see its security summary.

---

## Background watcher

The watcher monitors a GitHub repository in the background and automatically analyses new issues as they are opened:

```bash
devagent watch --repo owner/repo --start
```

For each new issue the watcher estimates complexity, identifies which files are likely affected, and stores the analysis locally. You can review analyses in your next interactive session or from the CLI:

```bash
devagent watch --status
```

The watcher runs as a background process and survives terminal restarts. Stop it explicitly when you no longer need it:

```bash
devagent watch --stop
```

---

## REST API

Run `devagent serve` to expose a local REST + WebSocket API that editor extensions, browser tools, or scripts can call:

```bash
devagent serve                 # http://localhost:7331
devagent serve --port 8080     # custom port
devagent serve --ui            # also open the live graph UI in the browser
```

**Graph UI**

`GET /` serves an in-memory session graph dashboard — no file is written to disk. It disappears when the server stops. The UI shows a D3.js force-directed graph of all sessions, a sidebar with token and cost metrics, a detail panel per session, and 30 s auto-refresh.

**v1 API endpoints**

| Method | Path | Description |
|---|---|---|
| GET | `/api/v1/status` | Server health, uptime, stats |
| GET | `/api/v1/sessions` | Paginated session list with metadata |
| GET | `/api/v1/sessions/{id}` | Full session detail and token totals |
| DELETE | `/api/v1/sessions/{id}` | Delete a session |
| GET | `/api/v1/sessions/{id}/events` | Paginated event log |
| GET | `/api/v1/sessions/{id}/memory` | Structured memory facts |
| POST | `/api/v1/sessions/{id}/approve` | Approve or deny a pending tool call |
| GET | `/api/v1/orchestrate/{id}/graph` | Task DAG for orchestrate sessions |
| GET | `/api/v1/metrics` | Aggregated token/cost/session metrics (supports `?period=24h`) |
| GET | `/api/docs` | Swagger UI |
| GET | `/api/redoc` | ReDoc |
| WS | `/ws/v1/{session_id}` | Live event stream |

Legacy paths (`/api/health`, `/api/sessions`, `/api/tools`, `/api/graph/stats`, `/api/graph/files`) are kept for backward compatibility.

All responses are JSON. CORS is enabled for local development. No authentication is applied — bind to `127.0.0.1` (the default) to avoid exposing the API on your network.

---

## Agent definitions

Agent definitions are TOML files in `.devagent/agents/` that describe named sub-agents you can invoke by name from the REPL or CLI.

```toml
# .devagent/agents/code-reviewer.toml
name = "code-reviewer"
description = "Review the current diff for correctness and style issues"
permission = "read-only"
memory = "session"       # session | project
isolation = ""           # "" | "worktree"
prompt = "Review the changed code for bugs, style problems, and missing tests."
```

**Fields:**

| Field | Description |
|---|---|
| `name` | Agent identifier (used in `@name` mentions and `devagent agent run`) |
| `description` | Human-readable description |
| `permission` | Tool permission mode: `default`, `read-only`, or `plan` |
| `memory` | `session` (in-memory only) or `project` (persists to `.devagent/agent-memory/<name>/memory.md`) |
| `isolation` | `worktree` to run in a fresh git worktree; empty string for shared working tree |
| `prompt` | Default task prompt if none is given at invocation time |

Project-level definitions override user-level ones with the same name. User agents live in `~/.config/devagent/agents/`.

---

## Hooks

Hooks fire shell commands, HTTP requests, or prompt injections at lifecycle events during a session. Configure them in `DEVAGENT.md` under a `[[hooks]]` section:

```toml
[[hooks]]
event    = "tool_call"
tool     = "write_file"
type     = "shell"
command  = "echo 'Writing {path}' >> devagent.log"

[[hooks]]
event    = "session_start"
type     = "prompt"
template = "Project context: this is a Django 4.2 application on Python 3.12."

[[hooks]]
event    = "session_end"
type     = "http"
url      = "https://hooks.example.com/devagent"
```

**Hook types:**

| Type | What it does |
|---|---|
| `shell` | Runs a shell command; `{tool}` and `{path}` are substituted from the event |
| `prompt` | Injects the `template` text into the next LLM call |
| `http` | POSTs a JSON payload to `url` with event metadata |

**Lifecycle events:** `session_start`, `session_end`, `tool_call`, `tool_result`

Test a hook without running a full session:

```bash
devagent hooks test session_start write_file
```

---

## Plugin bundles

Plugin bundles are distributable Python packages that extend DevAgent with tools, skills, hooks, and MCP servers. They register themselves via a `pyproject.toml` entry point:

```toml
# In the plugin package's pyproject.toml
[project.entry-points."devagent.plugins"]
my-plugin = "my_package.plugin:bundle"
```

```python
# my_package/plugin.py
from devagent.plugins import PluginBundle

bundle = PluginBundle(
    name="my-plugin",
    version="1.0.0",
    description="Adds Docker management tools to DevAgent",
    tools=["docker_run", "docker_logs"],
    skills=[{"name": "docker-build", "prompt": "Build and tag the Docker image."}],
)
```

Once the package is installed, DevAgent discovers it automatically:

```bash
# Install a plugin
devagent plugins install devagent-docker

# Verify it loaded
devagent plugins list
```

```
 Installed DevAgent Plugins
 Name           Version  Description              Skills  Hooks  MCP Servers  Tools
 devagent-docker  1.0.0  Docker management tools       1      0            1      3
```

---

## Effort levels

The `--effort` flag controls how hard the agent tries on each task. Higher effort uses more tokens and takes longer but produces better results on complex tasks.

| Level | When to use |
|---|---|
| `low` | Quick questions, file reads, trivial edits |
| `medium` | Standard coding tasks (default) |
| `high` | Bug fixes across multiple files, refactors |
| `xhigh` | Complex architectural changes; enables extended thinking on Anthropic models |
| `max` | Hardest tasks: security audits, large refactors, novel algorithms |

```bash
devagent run --effort high
devagent do "audit src/ for SQL injection vulnerabilities" --effort max
```

---

## Skills

Skills are reusable task templates that you invoke with a `/` prefix inside a `devagent run` session. They let you package common workflows — code reviews, test generation, deployment checks — as named commands.

```bash
# See what skills are available
devagent skills list

# Create a new skill interactively
devagent skills new pr-review
```

Once created, invoke a skill inside a session:

```
> /pr-review https://github.com/owner/repo/pull/42
```

Skills are stored in your DevAgent config directory and are available in all sessions and projects.

---

## Writing plugin tools

You can extend the agent with custom tools by registering them in the `ToolRegistry`. Tools are plain Python callables; they do not need to live inside the DevAgent package.

```python
from devagent.tools.registry import ToolRegistry

def search_internal_docs(args: dict) -> str:
    query = args.get("query", "")
    # your search logic here
    return f"Results for '{query}': ..."

def register(registry: ToolRegistry) -> None:
    registry.register(
        name="search_internal_docs",
        description=(
            "Search the company's internal documentation. "
            "Use this when the user asks about internal APIs or processes."
        ),
        parameters={
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "The search query",
                },
            },
            "required": ["query"],
        },
        handler=search_internal_docs,
    )
```

**Tool conventions:**

- Always return a `str`. Never raise an exception; return `"[error] ..."` instead.
- Keep descriptions precise — the LLM uses them to decide when to call the tool.
- Avoid side effects that cannot be undone without user confirmation.

See [docs/plugin_tools.md](docs/plugin_tools.md) for the full guide including security wrapping, parameter tips, and examples of the 29 built-in tools.

To distribute a tool as an installable package that other users can add with `devagent plugins install`, see [Plugin bundles](#plugin-bundles).

---

## Contributing

Contributions are welcome. Please read [CONTRIBUTING.md](CONTRIBUTING.md) for the full guide, including code style, test requirements, and the PR process.

**Quick summary:**

```bash
# Clone and install
git clone https://github.com/yourusername/DevAgent.git
cd DevAgent
pip install -e ".[dev]"

# Run tests
python -m pytest tests/

# Run the linter (zero errors required for CI)
ruff check devagent/ tests/

# Open a PR
git checkout -b feat/your-feature
# ... make changes and add tests ...
git push origin feat/your-feature
```

**CI runs automatically on every PR:**

- Lint with `ruff` on Python 3.12
- Tests on Python 3.12 and 3.13
- Wheel build

PyPI publish is triggered by creating a GitHub Release. There are no stored secrets — publish uses OIDC Trusted Publishing.

For bug reports, use the bug report issue template. For feature ideas, use the feature request template. Both are available when opening a new issue on GitHub.

---

## License

MIT. See [LICENSE](LICENSE) for details.

---

<div align="center">
<sub>Built with Python 3.12+. No LangGraph. No mandatory cloud. Your code stays yours.</sub>
</div>
