# SpecSync — Project Explanation & Build Guide

> **For the AI code editor reading this file:**
> This is the single source of truth for the SpecSync project. Read this entire file before writing any code. Every architectural decision, every technology choice, every command, every file path, and every phase of the build is documented here. Do not deviate from what is written. When in doubt about anything — structure, naming, behavior — refer back to this file. Build phase by phase in the exact order written. Do not proceed to the next phase until the current phase is fully working and verified.

---

## 1. What SpecSync Is

SpecSync is a terminal-first developer tool that bridges the gap between a product specification (a GitHub issue, a markdown doc, or plain text) and an existing codebase. It reads the spec, semantically searches the codebase, and produces a structured gap analysis telling the developer exactly:

- What already exists in the codebase that covers the requirement (reuse, touch nothing)
- What partially exists and needs extending (extend, don't rewrite)
- What conflicts with the new requirement and needs to be resolved first (resolve before coding)
- What is genuinely net new work (build from scratch)
- What edge cases the spec implies but does not state explicitly

It is installed globally once with `pip install specsync` or `pipx install specsync`. It is used from the terminal inside any project directory. It stores all its data in the user's home directory — it never writes anything inside the user's project. It works completely offline if the user has Ollama running locally, which is the default and primary intended usage.

SpecSync is NOT a chat interface. It is NOT a code generator. It does NOT write code. It is a pre-implementation intelligence tool that gives developers a clear, accurate picture of what work a spec actually requires before they begin.

---

## 2. The Problem Being Solved

A developer receives a GitHub issue: "Add OAuth2 login with Google." They estimate 3 days, start coding, and on day 2 discover:

- Session management already exists in `auth/session.py` but its interface assumes an existing user — OAuth creates new users on first login, so the interface is wrong
- That interface is imported by 6 other files — changing it breaks them all
- `authlib` is already in `requirements.txt` and unused — the OAuth library was already added by someone
- The spec didn't mention what happens when a Google account email matches an existing email/password account

None of this was visible at estimation time. SpecSync surfaces all of it in 30 seconds before the developer writes a line.

---

## 3. How It Is Installed and Used

### Installation (once, globally)

```
pip install specsync
# or, preferred:
pipx install specsync
```

SpecSync is a Python package on PyPI. It is installed once globally on the machine. It is not a project dependency. It does not appear in any project's `requirements.txt` or `pyproject.toml`.

### First-time setup

```
specsync init
```

Interactive setup. Prompts for:
- LLM provider choice (ollama / groq / anthropic / openai / gemini)
- Model name for the chosen provider
- API keys if applicable (not needed for Ollama)
- GitHub token (for fetching issues)
- Brave Search API key (for web search, optional)

Writes everything to `%APPDATA%\specsync\config.toml` on Windows.

### Indexing a project (once per project, then incremental)

```
cd C:\path\to\your\project
specsync index
```

Builds the semantic vector index of the codebase. On first run, indexes all files. On subsequent runs, only re-indexes files that changed since the last run (incremental, fast). Stores the index in SpecSync's own data directory — never inside the project.

### Running an analysis (daily use)

```
specsync analyze --issue 142
specsync analyze --spec .\docs\feature.md
specsync analyze --text "Add rate limiting to the API"
```

Runs the full 3-agent pipeline and outputs the gap analysis to the terminal in rich formatted output AND saves a markdown file to the reports directory.

### All other commands

```
specsync index --status         # show index state for current project
specsync index --full           # force full re-index
specsync index --clear          # wipe index for current project
specsync search "query"         # semantic search without full analysis
specsync reports                # list saved reports for current project
specsync reports --show ID      # re-display a saved report
specsync config --show          # display current config
specsync config --set key=val   # update a config value
specsync doctor                 # check all dependencies are working
```

---

## 4. Storage — Where Everything Lives

SpecSync follows Windows conventions for application data storage. It uses the `platformdirs` Python library to resolve paths correctly across Windows, macOS, and Linux. On Windows specifically:

```
%APPDATA%\specsync\
  └── config.toml                    ← API keys, LLM provider, preferences

%LOCALAPPDATA%\specsync\
  └── projects\
      └── {project_hash}\            ← one folder per indexed project
          ├── chroma\                ← ChromaDB vector index (the RAG store)
          ├── specsync.db            ← SQLite: file index, timestamps, cache
          └── meta.toml              ← project name, root path, last indexed at

%LOCALAPPDATA%\specsync\
  └── reports\
      └── {project_hash}\
          ├── issue-142-2025-01-15.md
          └── spec-oauth-2025-01-10.md

%TEMP%\specsync\                     ← temporary files, MCP server logs
```

The `project_hash` is a deterministic SHA256 of the absolute project root path. This means the same project always maps to the same folder regardless of how SpecSync is invoked.

**Critical rule:** SpecSync never creates, reads, or modifies any file inside the user's project directory. The only thing it reads from the project is source files for indexing, and those reads are read-only.

---

## 5. Architecture Overview

SpecSync has three layers:

### Layer 1 — CLI (what the user sees)
Built with `Typer` for command definitions and `Rich` for all terminal output. Every command is a Typer command. All output goes through Rich — colored panels, progress bars, formatted tables. No raw print statements anywhere.

### Layer 2 — Agent Pipeline (the intelligence)
Three LangGraph agents that run sequentially. Each agent is a stateful LangGraph `StateGraph`. They share state through a typed Python dataclass — not through files, not through a database, just a Python object passed through the pipeline. The agents call MCP tools as their only way to interact with external systems.

### Layer 3 — MCP Servers (the tools)
Five MCP servers total. Three are official published servers (GitHub, Filesystem, Brave Search) launched as managed child processes. Two are custom-built Python MCP servers (SpecAnalysisMCP, CodeSearchMCP) that run as Python processes managed by SpecSync. All five are launched automatically when `specsync analyze` runs and shut down when it finishes.

---

## 6. The MCP Design — Complete Specification

### Why MCP matters here

Every agent tool call goes through the MCP protocol. This means agents have no hardcoded API calls. They discover tools through the protocol and call them by name with typed arguments. This also means the two custom MCP servers (SpecAnalysisMCP and CodeSearchMCP) can be used independently by Claude Desktop, Cursor, or any other MCP-compatible tool — not just SpecSync's CLI. That is a deliberate design choice.

### The three official MCP servers (Node.js, managed as subprocesses)

SpecSync launches these using the `mcp` Python SDK's `StdioServerParameters` — they run as child processes communicating over stdio. The Python MCP client connects to them transparently. The developer never needs to start them manually. SpecSync checks for `node` availability on startup and raises a clear, actionable error if it is not installed.

**GitHub MCP**
- Package: `@modelcontextprotocol/server-github`
- Launch: `npx -y @modelcontextprotocol/server-github`
- Environment: `GITHUB_PERSONAL_ACCESS_TOKEN`
- Tools used by agents:
  - `get_issue(owner, repo, issue_number)` — fetches issue title, body, labels, comments
  - `get_file_contents(owner, repo, path, branch)` — reads specific files for conflict analysis
  - `search_code(query, owner, repo)` — keyword search across the repo
  - `list_directory(owner, repo, path)` — directory tree exploration

**Filesystem MCP**
- Package: `@modelcontextprotocol/server-filesystem`
- Launch: `npx -y @modelcontextprotocol/server-filesystem {project_root}`
- Tools used by agents:
  - `read_file(path)` — reads a specific file's full content
  - `list_directory(path)` — lists directory contents
  - `search_files(path, pattern)` — glob pattern file search

**Brave Search MCP**
- Package: `@modelcontextprotocol/server-brave-search`
- Launch: `npx -y @modelcontextprotocol/server-brave-search`
- Environment: `BRAVE_API_KEY`
- Tools used by agents:
  - `brave_web_search(query, count)` — searches for implementation context, library docs, known patterns

**Node.js availability:** On first run, SpecSync checks for `node` in PATH. If missing, it prints a formatted error explaining that Node.js is required for the official MCP servers, with a download link, and exits cleanly. It does not attempt to install Node.js itself.

**npx caching:** The `-y` flag on npx auto-accepts the install. After the first run, npx caches the packages locally so subsequent runs are instant. SpecSync documents this in the output the first time ("downloading MCP servers, this is a one-time step...").

### The two custom MCP servers (Python, built by us)

Both are built using `FastMCP` from the `mcp` Python SDK. Both run as Python subprocess child processes using the same stdio transport pattern as the Node.js servers. Both are bundled inside the SpecSync package — they are part of the codebase, not separate packages.

---

**SpecAnalysisMCP** — parses specifications into structured requirements

This server's job is to take raw text (a GitHub issue body, a markdown doc, or inline text) and return a structured JSON list of requirements. It uses the configured LLM internally (whatever provider the user set up — Ollama, Groq, Anthropic, OpenAI, Gemini).

Tools:

`parse_spec_to_requirements(spec_text: str, context: str) -> list[Requirement]`
Takes the raw spec text and optional project context. Uses the LLM with a structured output prompt to extract atomic, testable requirements. Each requirement has: id, description, requirement_type (feature | constraint | data_model | api_change | behaviour), priority (high | medium | low), and raw_text (the exact spec sentence it came from). Returns a JSON list. The LLM is instructed to return ONLY valid JSON — no preamble, no markdown fences. If the LLM returns invalid JSON, the server retries once with a JSON repair prompt before raising an error.

`infer_edge_cases(requirements: list[Requirement], spec_text: str) -> list[EdgeCase]`
Takes the structured requirements and the original spec and asks the LLM: what edge cases does this spec imply but not state? Returns a list of EdgeCase objects: {description, related_requirement_id, severity (must_discuss | should_discuss)}. These appear in the output as questions for the PM.

`extract_data_models(spec_text: str) -> list[DataModel]`
Identifies any data model changes implied by the spec — new fields, new tables, changed relationships. Returns structured DataModel objects.

`identify_api_changes(spec_text: str) -> list[APIChange]`
Identifies any API endpoint changes implied — new routes, changed signatures, new parameters.

---

**CodeSearchMCP** — semantic RAG search over the codebase

This is the most technically important custom server. It maintains the ChromaDB vector index and handles all semantic search and conflict detection.

This server is long-lived relative to the others. On first tool call, it loads the ChromaDB collection for the current project. Subsequent calls reuse the loaded collection. It uses `sentence-transformers` with the `all-MiniLM-L6-v2` model for embeddings — this model is downloaded once (~90MB), runs fully on CPU, requires no GPU, and produces 384-dimension vectors.

**Chunking strategy (critical detail):**
When indexing Python files, SpecSync uses the `ast` module to chunk by semantic boundaries:
- Each function definition becomes one chunk: its docstring + signature + body
- Each class becomes one chunk: its docstring + `__init__` + list of method names
- Each method becomes one chunk: its docstring + signature + body
- Module-level code becomes one chunk: imports + module docstring + module-level variables

For non-Python files (JSON, YAML, MD, TOML, .env.example):
- Files under 200 lines: one chunk each
- Files over 200 lines: split at blank line boundaries into chunks of ~150 lines

Each chunk is stored in ChromaDB with metadata: `file_path`, `chunk_type` (function/class/method/module/config), `name` (function or class name if applicable), `start_line`, `end_line`, `language`.

Tools:

`index_codebase(project_root: str, incremental: bool) -> IndexResult`
Walks the project directory. Respects `.gitignore` using the `pathspec` library — does not index files that git ignores. Also has a built-in ignore list: `node_modules`, `.venv`, `__pycache__`, `.git`, `dist`, `build`, `*.pyc`, `*.pyo`, `*.egg-info`. For incremental indexing, compares file modification timestamps against the SQLite cache and only re-chunks and re-embeds changed files. Returns: {files_indexed, chunks_created, files_skipped, duration_seconds}.

`semantic_search(query: str, top_k: int, filter_language: str | None) -> list[SearchResult]`
Embeds the query using the local sentence-transformers model. Queries ChromaDB for the top_k nearest chunks by cosine similarity. Returns each result with: file_path, chunk_type, name, start_line, end_line, similarity_score (0–1), and the actual code content. Minimum similarity threshold: 0.3 — results below this are not returned even if they are the "closest."

`get_import_graph(project_root: str) -> dict`
Uses Python's `ast` module to parse every Python file and extract its imports. Returns a dictionary: {file_path: [list of files it imports from this project]}. This is used for conflict detection — if a file needs to change, this graph shows what else breaks.

`detect_conflicts(file_path: str, proposed_change_description: str) -> ConflictResult`
Given a file that will need to change, uses the import graph to find all files that depend on it. For each dependent file, reads it (via the already-loaded chunks) and asks: does this dependent file call the specific function or use the specific interface that will change? Returns: {affected_files: list[str], conflict_severity: high|medium|low, explanation: str}.

`find_similar_implementations(description: str, exclude_files: list[str]) -> list[SearchResult]`
Same as semantic_search but specifically designed to find existing implementations of something — with a prompt prefix that biases the search toward implementation code rather than tests or configs.

---

## 7. The LLM Provider System

### Design principle

The LLM provider is a runtime configuration choice, not a code choice. Every agent uses the same `get_llm()` function from `specsync/core/llm.py`. That function reads the config, instantiates the correct LangChain-compatible LLM object, and returns it. Agents call `llm.invoke(messages)` — they do not know or care which provider is underneath.

### Supported providers

All providers are wrapped using LangChain's provider integrations so agents use a consistent interface.

**Ollama (default, recommended)**
- Library: `langchain-ollama`
- Config: `provider = "ollama"`, `model = "qwen2.5-coder:7b"`, `base_url = "http://localhost:11434"`
- No API key required
- Recommended model for SpecSync: `qwen2.5-coder:7b` — fine-tuned on code, excellent at understanding technical specifications and code structure. Also acceptable: `llama3.2:3b` for lower RAM usage, `qwen2.5-coder:14b` for better quality on machines with more RAM
- SpecSync checks that Ollama is running on startup when this provider is configured. If Ollama is not reachable, it prints a clear error with the command to start Ollama
- Temperature: 0.1 for all agents (deterministic, factual reasoning — not creative generation)

**Groq**
- Library: `langchain-groq`
- Config: `provider = "groq"`, `model = "llama-3.3-70b-versatile"` or `"llama-3.1-8b-instant"`
- API key: `GROQ_API_KEY`
- Rate limiting: 30 RPM on free tier. SpecSync implements a token-bucket rate limiter in `specsync/core/llm.py` that sleeps between calls if the rate is approached. This is transparent to agents.
- Recommended for users who want cloud inference without paying

**Anthropic**
- Library: `langchain-anthropic`
- Config: `provider = "anthropic"`, `model = "claude-3-5-haiku-20241022"`
- API key: `ANTHROPIC_API_KEY`
- Haiku is recommended over Sonnet for cost — SpecSync makes many LLM calls per analysis

**OpenAI**
- Library: `langchain-openai`
- Config: `provider = "openai"`, `model = "gpt-4o-mini"`
- API key: `OPENAI_API_KEY`
- gpt-4o-mini is recommended for cost efficiency

**Gemini**
- Library: `langchain-google-genai`
- Config: `provider = "gemini"`, `model = "gemini-1.5-flash"`
- API key: `GOOGLE_API_KEY`

### Fallback provider

Config supports an optional `[llm.fallback]` section. If the primary provider fails (Ollama not running, API key invalid, rate limit hit), SpecSync automatically retries the call with the fallback provider. If no fallback is configured and the primary fails, SpecSync exits with a clear error message.

### Provider validation

`specsync init` validates the provider connection before saving config. It makes one lightweight test call (for Ollama: check if the model is available; for API providers: check API key validity with the models list endpoint — not an inference call). It does not proceed to save config if validation fails.

---

## 8. The Three Agents — Complete Specification

State is a typed Python dataclass `PipelineState` passed through all three agents:

```python
@dataclass
class PipelineState:
    # Input
    raw_spec: str
    spec_source: str          # "github_issue" | "file" | "text"
    issue_number: int | None
    project_root: str
    github_repo: str | None   # "owner/repo"

    # SpecParserAgent output
    requirements: list[Requirement]
    edge_cases: list[EdgeCase]
    data_models: list[DataModel]
    api_changes: list[APIChange]

    # CodeInventoryAgent output
    requirement_map: list[RequirementAnalysis]
    import_graph: dict

    # GapReportAgent output
    gap_report: GapReport
    implementation_order: list[str]
    effort_estimate: EffortEstimate
```

### Agent 1 — SpecParserAgent

**Purpose:** Transform raw spec text into structured, atomic requirements.

**LangGraph graph nodes:**

Node `fetch_spec`: If source is `github_issue`, calls GitHub MCP `get_issue()` to fetch the issue body, title, labels, and comments. Concatenates all into `raw_spec`. If source is `file`, calls Filesystem MCP `read_file()`. If source is `text`, uses the provided text directly.

Node `search_context`: Calls Brave Search MCP `brave_web_search()` with a query derived from the spec topic. For example, if the spec mentions "OAuth2 with Google," it searches "Google OAuth2 PKCE flow Python implementation requirements 2024." Returns top 3 results. This context is injected into the parsing prompt to ground the LLM in real-world implementation knowledge — not just what the spec says, but what implementing it actually requires. This node is skipped if Brave API key is not configured (the tool is optional).

Node `parse_requirements`: Calls SpecAnalysisMCP `parse_spec_to_requirements()` with the raw spec and the search context. Receives structured Requirement objects. Validates that at least one requirement was extracted — if zero, raises a user-friendly error explaining the spec may be too vague.

Node `extract_metadata`: Calls SpecAnalysisMCP `extract_data_models()` and `identify_api_changes()` in parallel. These enrich the state with implied structural changes.

Node `infer_edge_cases`: Calls SpecAnalysisMCP `infer_edge_cases()` with the requirements and raw spec. Receives EdgeCase objects. These will appear in the final output as "questions to discuss before starting."

**Output:** Populated `requirements`, `edge_cases`, `data_models`, `api_changes` fields in PipelineState.

**Model used:** Smart model (70B if Groq, the configured model if Ollama). This is the highest-reasoning task — parsing informal language into precise technical requirements.

**Error handling:** If the LLM returns malformed JSON from SpecAnalysisMCP, the MCP server retries once internally. If it fails again, SpecParserAgent catches the error and exits with: "Could not parse the specification. Try being more specific or breaking the spec into smaller pieces."

---

### Agent 2 — CodeInventoryAgent

**Purpose:** For every requirement, search the codebase and classify it as FULLY_EXISTS, PARTIALLY_EXISTS, MISSING, or CONFLICTED.

**LangGraph graph nodes:**

Node `ensure_index`: Checks the SQLite cache to see when this project was last indexed. If never indexed, calls CodeSearchMCP `index_codebase()` automatically with a progress bar shown to the user ("indexing your codebase for the first time, this takes 30–60 seconds..."). If the index is stale (more than 24 hours old or if git detects changed files), offers to re-index incrementally. Stores index timestamp in SQLite.

Node `build_import_graph`: Calls CodeSearchMCP `get_import_graph()` once. Stores the full import graph in PipelineState. This is used by the conflict detection step.

Node `search_requirements`: For each requirement in the requirements list, calls CodeSearchMCP `semantic_search()` with the requirement description as the query. Returns top 5 results per requirement. This node processes all requirements in parallel using `asyncio.gather` — all searches happen simultaneously, not sequentially. This is important for performance.

Node `classify_requirements`: For each requirement and its search results, uses the LLM to classify. Prompt includes: the requirement description, the top 3 search results (file path + function name + code snippet), and instructions to classify as FULLY_EXISTS / PARTIALLY_EXISTS / MISSING / CONFLICTED with a one-sentence reason. Uses the fast model (8B if Groq, configured model if Ollama) — this is a classification task, not deep reasoning.

Node `detect_conflicts`: For any requirement classified as PARTIALLY_EXISTS or CONFLICTED, calls CodeSearchMCP `detect_conflicts()` with the matched file path and the requirement description. Gets back the list of affected files. Updates the classification with full conflict information. The import graph from `build_import_graph` is passed in here.

**Output:** Populated `requirement_map` and `import_graph` fields in PipelineState.

**Performance note:** The parallel search in `search_requirements` is critical. A spec with 6 requirements makes 6 semantic searches. Sequential would take 6 × latency. Parallel takes 1 × latency.

---

### Agent 3 — GapReportAgent

**Purpose:** Assemble the full analysis into a structured, actionable report. Determine implementation order. Estimate effort.

**LangGraph graph nodes:**

Node `group_by_status`: Groups RequirementAnalysis objects into four buckets: REUSE, EXTEND, CONFLICT, NET_NEW. Sorts within each bucket by priority.

Node `determine_order`: Uses the LLM to determine the correct implementation order given the four buckets. The rule is always: resolve CONFLICT first, then EXTEND, then NET_NEW, REUSE is touched last (or never). But within CONFLICT, there may be ordering dependencies — if conflict A affects file X, and conflict B also affects file X, they must be resolved together. LLM reasons about this and returns an ordered list of implementation steps.

Node `estimate_effort`: Uses the LLM to estimate effort per bucket. Prompt includes: the requirement classifications, the conflict details (how many files affected), and the data model changes. Returns structured effort estimates: {conflict_resolution_hours, extension_hours, net_new_hours, testing_hours, total_days, confidence: low|medium|high}. The confidence is low if there are CONFLICTED items (conflicts are hard to estimate without reading all affected files deeply), medium for EXTEND, high for NET_NEW.

Node `format_report`: Assembles the GapReport object. This is a pure data assembly step — no LLM call. Combines: bucketed requirements, implementation order, effort estimate, edge cases, data model changes, API changes into one structured object.

Node `render_and_save`: Renders the GapReport to two outputs simultaneously:
1. Rich terminal output — formatted panels, colored status indicators, progress tables
2. Markdown file — saved to `%LOCALAPPDATA%\specsync\reports\{project_hash}\{name}.md`

**Output:** Both terminal display and saved markdown file.

---

## 9. Project Directory Structure

This is the exact directory and file structure to create. Every file listed must exist with full implementation — no stubs, no TODOs.

```
specsync/
│
├── pyproject.toml                    ← package definition, entry points, dependencies
├── README.md                         ← user-facing readme
├── PROJECT.md                        ← this file (stored in root)
├── .env.example                      ← example env file (never used by the tool itself)
│
├── specsync/                         ← main package
│   ├── __init__.py
│   ├── cli.py                        ← Typer CLI — all command definitions
│   │
│   ├── core/
│   │   ├── __init__.py
│   │   ├── config.py                 ← config loading/saving using platformdirs + tomllib
│   │   ├── llm.py                    ← LLM provider factory, rate limiting, fallback logic
│   │   ├── storage.py                ← all path resolution using platformdirs
│   │   ├── project.py                ← project detection, project hash computation
│   │   └── models.py                 ← all Pydantic/dataclass models for the entire system
│   │
│   ├── mcp/
│   │   ├── __init__.py
│   │   ├── manager.py                ← launches and manages all 5 MCP server processes
│   │   ├── client.py                 ← MCP client wrapper — connects to servers, calls tools
│   │   │
│   │   ├── servers/                  ← the two custom MCP servers
│   │   │   ├── __init__.py
│   │   │   ├── spec_analysis/
│   │   │   │   ├── __init__.py
│   │   │   │   └── server.py         ← FastMCP server: SpecAnalysisMCP
│   │   │   └── code_search/
│   │   │       ├── __init__.py
│   │   │       ├── server.py         ← FastMCP server: CodeSearchMCP
│   │   │       ├── indexer.py        ← chunking logic, AST parsing, embedding, ChromaDB write
│   │   │       └── searcher.py       ← semantic search, import graph, conflict detection
│   │   │
│   │   └── clients/                  ← typed clients for each MCP server
│   │       ├── __init__.py
│   │       ├── github_client.py
│   │       ├── filesystem_client.py
│   │       ├── brave_client.py
│   │       ├── spec_analysis_client.py
│   │       └── code_search_client.py
│   │
│   ├── agents/
│   │   ├── __init__.py
│   │   ├── pipeline.py               ← orchestrates the 3-agent sequence, manages PipelineState
│   │   ├── spec_parser.py            ← SpecParserAgent LangGraph definition
│   │   ├── code_inventory.py         ← CodeInventoryAgent LangGraph definition
│   │   └── gap_report.py             ← GapReportAgent LangGraph definition
│   │
│   └── output/
│       ├── __init__.py
│       ├── terminal.py               ← Rich rendering of GapReport to terminal
│       └── markdown.py               ← Markdown rendering of GapReport to file
│
└── tests/
    ├── __init__.py
    ├── test_config.py
    ├── test_storage.py
    ├── test_mcp_servers.py
    ├── test_agents.py
    ├── test_indexer.py
    └── fixtures/
        ├── sample_spec.txt
        └── sample_project/           ← small fake Python project for testing
```

---

## 10. Technology Stack — Complete List

Every library listed here must be used for the specified purpose. Do not substitute.

### Core CLI
- `typer[all]` — CLI framework. Provides command definitions, argument parsing, help text generation. The `[all]` extra includes Rich integration.
- `rich` — all terminal output. Progress bars, colored panels, formatted tables, syntax-highlighted code snippets. No `print()` statements anywhere in the codebase except inside Rich console calls.
- `platformdirs` — resolves correct data/config/cache directories per OS. Use `user_data_dir("specsync")`, `user_config_dir("specsync")`, `user_cache_dir("specsync")`. This ensures Windows, macOS, Linux all get the correct paths.

### Configuration
- `tomllib` (stdlib, Python 3.11+) — reading TOML config files
- `tomli-w` — writing TOML config files (tomllib is read-only)

### MCP
- `mcp[cli]` — official Python MCP SDK. Used for both the MCP client (connecting to servers) and the FastMCP server builder (building SpecAnalysisMCP and CodeSearchMCP). Version: latest stable.

### Agent Framework
- `langgraph` — all three agents are LangGraph StateGraph instances
- `langchain-core` — base types (messages, prompts, output parsers)

### LLM Providers (all installed, user chooses one)
- `langchain-ollama` — Ollama local models
- `langchain-groq` — Groq cloud API
- `langchain-anthropic` — Anthropic Claude API
- `langchain-openai` — OpenAI API
- `langchain-google-genai` — Google Gemini API

### Semantic Search / RAG (CodeSearchMCP)
- `sentence-transformers` — local embedding model. Model: `all-MiniLM-L6-v2`. Produces 384-dimension vectors. Runs on CPU. No GPU required.
- `chromadb` — local persistent vector store. Used in persistent mode pointing to the project's data directory. Not a server — file-based.
- `pathspec` — respects `.gitignore` patterns during indexing

### Code Analysis
- `ast` (stdlib) — Python AST parsing for chunking Python files and building import graphs
- `radon` — cyclomatic complexity, used in conflict severity scoring

### Database
- `aiosqlite` — async SQLite for the file index cache (timestamps, indexed files list)

### Networking / HTTP
- `httpx` — async HTTP client used for Ollama health checks and any direct HTTP calls
- `tenacity` — retry logic with exponential backoff, used for all LLM calls and MCP tool calls

### Data Models
- `pydantic` — all data models (Requirement, GapReport, RequirementAnalysis, etc.) are Pydantic models for validation

### Packaging
- `pyproject.toml` with `[project.scripts]` entry point: `specsync = "specsync.cli:app"`
- Build backend: `hatchling`

### Development only
- `pytest` — test framework
- `pytest-asyncio` — async test support
- `ruff` — linting and formatting

---

## 11. The `pyproject.toml` — Complete Specification

```toml
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "specsync"
version = "0.1.0"
description = "Requirements-to-code gap analysis for developers"
requires-python = ">=3.12"
dependencies = [
    "typer[all]>=0.12.0",
    "rich>=13.7.0",
    "platformdirs>=4.2.0",
    "tomli-w>=1.0.0",
    "mcp[cli]>=1.0.0",
    "langgraph>=0.2.0",
    "langchain-core>=0.3.0",
    "langchain-ollama>=0.2.0",
    "langchain-groq>=0.1.9",
    "langchain-anthropic>=0.2.0",
    "langchain-openai>=0.2.0",
    "langchain-google-genai>=2.0.0",
    "sentence-transformers>=3.1.0",
    "chromadb>=0.5.0",
    "pathspec>=0.12.0",
    "radon>=6.0.0",
    "aiosqlite>=0.20.0",
    "httpx>=0.27.0",
    "tenacity>=9.0.0",
    "pydantic>=2.8.0",
]

[project.scripts]
specsync = "specsync.cli:app"

[tool.ruff]
line-length = 100
target-version = "py312"
```

---

## 12. Phase-by-Phase Build Plan

Build strictly in this order. Each phase has a verification step. Do not start the next phase until verification passes.

---

### PHASE 1 — Project Skeleton and Configuration System

**Goal:** A working Python package that installs, shows help text, and correctly reads/writes config.

**Phase 1.1 — Package setup**

Create `pyproject.toml` exactly as specified in Section 11. Create the full directory structure from Section 9 with empty `__init__.py` files in every package directory.

Create `specsync/cli.py` with a Typer app. Define all commands as empty functions that print "not yet implemented" — this establishes the full command surface immediately:
- `init` command
- `config` command with `--show` and `--set` options
- `index` command with `--full`, `--status`, `--clear` options
- `analyze` command with `--issue`, `--spec`, `--text`, `--output`, `--repo` options
- `search` command
- `reports` command with `--show` option
- `doctor` command

Install in development mode: `pip install -e .`

**Verification:** `specsync --help` shows all commands. `specsync analyze --help` shows all options.

**Phase 1.2 — Storage system**

Implement `specsync/core/storage.py` fully. This module is the single source of truth for all file paths. It must provide:

```python
def get_config_path() -> Path          # %APPDATA%\specsync\config.toml
def get_data_dir() -> Path             # %LOCALAPPDATA%\specsync
def get_project_dir(project_root: Path) -> Path   # data_dir/projects/{hash}
def get_chroma_dir(project_root: Path) -> Path    # project_dir/chroma
def get_sqlite_path(project_root: Path) -> Path   # project_dir/specsync.db
def get_reports_dir(project_root: Path) -> Path   # data_dir/reports/{hash}
def get_project_hash(project_root: Path) -> str   # SHA256 of absolute path
def ensure_dirs(project_root: Path) -> None       # creates all dirs if missing
```

Use `platformdirs` for the base paths. Use `hashlib.sha256` for the project hash. All paths are `pathlib.Path` objects — never strings.

**Phase 1.3 — Configuration system**

Implement `specsync/core/config.py` fully.

The config file lives at `get_config_path()`. It is a TOML file with this schema:

```toml
[llm]
provider = "ollama"
model = "qwen2.5-coder:7b"
base_url = "http://localhost:11434"
temperature = 0.1

[llm.fallback]
# optional section
provider = "groq"
model = "llama-3.1-8b-instant"

[github]
token = ""
default_repo = ""    # "owner/repo" — inferred from git remote if empty

[brave]
api_key = ""         # optional

[output]
verbosity = "normal"  # "quiet" | "normal" | "verbose"
```

Implement:
```python
def load_config() -> SpecSyncConfig       # reads TOML, returns Pydantic model
def save_config(config: SpecSyncConfig)   # writes TOML using tomli-w
def config_exists() -> bool               # checks if config file exists
```

`SpecSyncConfig` is a Pydantic model with nested models for each section. All fields have defaults so a minimal config (just the LLM provider) works.

**Phase 1.4 — The `specsync init` command**

Implement the `init` command fully in `cli.py`. It is interactive — uses Rich `Prompt.ask` and `Confirm.ask` (not `input()`). The flow:

1. Print a welcome panel with Rich
2. Ask: which LLM provider? (show numbered list: 1=Ollama, 2=Groq, 3=Anthropic, 4=OpenAI, 5=Gemini)
3. Ask: model name (show sensible default per provider)
4. If Ollama: ask base_url (default: http://localhost:11434)
5. If not Ollama: ask for the API key (masked input with `Prompt.ask(password=True)`)
6. Ask: GitHub personal access token (show link to create one)
7. Ask: Brave Search API key (mark as optional, show skip option)
8. Validate the LLM provider: make a lightweight test call. Show spinner while testing. Print success or failure.
9. Validate GitHub token: make a simple authenticated request. Show success or failure.
10. Save config to `get_config_path()`
11. Print success summary

If init is re-run, show current values and ask which to update.

**Phase 1.5 — The `specsync doctor` command**

Implement `doctor` fully. Checks:
- Config file exists and is valid
- LLM provider is reachable
- GitHub token is valid
- Brave API key is valid (if configured)
- Node.js is installed (`node --version` in subprocess)
- npx is available (`npx --version` in subprocess)

Output a Rich table: service name, status (✅/❌), details.

**Verification for Phase 1:** `specsync init` completes successfully with Ollama. `specsync doctor` shows all green. Config file exists at correct Windows path with correct content.

---

### PHASE 2 — MCP Infrastructure

**Goal:** All 5 MCP servers launch correctly, tools are callable, and the manager handles startup/shutdown cleanly.

**Phase 2.1 — MCP Manager**

Implement `specsync/mcp/manager.py`. This is the component that launches all 5 MCP servers as child processes and provides the `MCPClient` connections to each.

The manager is an async context manager:

```python
async with MCPManager(config, project_root) as manager:
    github = manager.github
    filesystem = manager.filesystem
    brave = manager.brave
    spec_analysis = manager.spec_analysis
    code_search = manager.code_search
```

On `__aenter__`:
1. Check Node.js is available (subprocess `node --version`). Raise `NodeNotFoundError` with instructions if not.
2. Launch all 5 MCP servers as `asyncio.subprocess` processes using `mcp` SDK's `StdioServerParameters`
3. Establish `ClientSession` connections to each
4. Verify each server responds to a `list_tools()` call
5. If any server fails to start, shut down all others and raise with a clear error

On `__aexit__`: terminate all child processes cleanly, close all sessions.

For the two custom Python MCP servers (SpecAnalysisMCP, CodeSearchMCP), the launch command is:
```python
StdioServerParameters(
    command="python",
    args=["-m", "specsync.mcp.servers.spec_analysis.server"],
    env={**os.environ, "SPECSYNC_CONFIG_PATH": str(get_config_path())}
)
```

For the three Node.js servers, use `npx -y @modelcontextprotocol/server-{name}` as the command.

**Phase 2.2 — MCP Client wrapper**

Implement `specsync/mcp/client.py`. The `MCPClient` class wraps an MCP `ClientSession` and provides typed tool calling with retry logic:

```python
async def call_tool(self, tool_name: str, arguments: dict) -> dict:
    # wraps session.call_tool with tenacity retry (3 attempts, exponential backoff)
    # raises ToolCallError with descriptive message on failure
```

**Phase 2.3 — Typed clients for each server**

Implement each file in `specsync/mcp/clients/`. Each typed client wraps the generic `MCPClient` and exposes named methods that parse the MCP response into Pydantic models. No agent ever calls `call_tool` directly — they use these typed clients.

Example for `code_search_client.py`:
```python
class CodeSearchClient:
    def __init__(self, mcp_client: MCPClient): ...

    async def semantic_search(
        self, query: str, top_k: int = 5
    ) -> list[SearchResult]: ...

    async def index_codebase(
        self, project_root: str, incremental: bool = True
    ) -> IndexResult: ...

    async def get_import_graph(self, project_root: str) -> dict: ...

    async def detect_conflicts(
        self, file_path: str, proposed_change: str
    ) -> ConflictResult: ...
```

**Phase 2.4 — SpecAnalysisMCP server**

Implement `specsync/mcp/servers/spec_analysis/server.py` as a FastMCP server.

The server reads its LLM config from the environment variable `SPECSYNC_CONFIG_PATH`, loads the config, and instantiates the configured LLM provider using `specsync/core/llm.py`. All tool implementations call this LLM.

For `parse_spec_to_requirements`: the system prompt must instruct the LLM to return ONLY a JSON array of Requirement objects with no other text. The user prompt includes the spec text and optional context. Parse the response with `json.loads()`. If parsing fails, send a repair prompt: "The previous response was not valid JSON. Return only the JSON array, nothing else: {previous_response}". If repair fails, raise an MCP error.

For `infer_edge_cases`: ask the LLM to think like a QA engineer — what would break, what would a user try that the spec didn't consider, what happens at the boundaries?

**Phase 2.5 — CodeSearchMCP server**

This is the most complex component. Implement across `server.py`, `indexer.py`, and `searcher.py`.

`indexer.py` implements:
- `chunk_python_file(file_path: Path) -> list[CodeChunk]` — uses Python `ast` module. Walk the AST tree. For each `FunctionDef`, `AsyncFunctionDef`, `ClassDef` at module level, create a chunk. For each method inside a class, create a chunk. For module-level code (imports, assignments), create one chunk. Each CodeChunk: {content: str, chunk_type: str, name: str, file_path: str, start_line: int, end_line: int}
- `chunk_generic_file(file_path: Path) -> list[CodeChunk]` — for non-Python files, split by blank lines into chunks of 150 lines
- `embed_chunks(chunks: list[CodeChunk]) -> list[list[float]]` — uses `sentence_transformers.SentenceTransformer("all-MiniLM-L6-v2")`. Load the model once at server startup and keep it in memory. Do not reload per call.
- `index_project(project_root: Path, chroma_dir: Path, sqlite_path: Path, incremental: bool)` — the main indexing function

`searcher.py` implements:
- `semantic_search(query: str, collection, top_k: int) -> list[SearchResult]` — embeds query, queries ChromaDB
- `build_import_graph(project_root: Path) -> dict` — AST-based import analysis
- `detect_conflicts(file_path: str, import_graph: dict, collection) -> ConflictResult`

ChromaDB collection name: `"codebase_{project_hash}"`. Use `chromadb.PersistentClient(path=str(chroma_dir))`.

**Verification for Phase 2:** Run `specsync doctor` and see all MCP servers listed as reachable. Write a small test script that instantiates the MCPManager and calls one tool on each server. All five should respond.

---

### PHASE 3 — Indexing System

**Goal:** `specsync index` correctly indexes a Python project, stores the vector index in ChromaDB, and handles incremental re-indexing.

**Phase 3.1 — SQLite schema**

Implement `specsync/core/storage.py` database functions using `aiosqlite`. Schema:

```sql
CREATE TABLE IF NOT EXISTS indexed_files (
    file_path TEXT PRIMARY KEY,
    last_modified REAL NOT NULL,       -- os.path.getmtime()
    chunk_count INTEGER NOT NULL,
    indexed_at TEXT NOT NULL           -- ISO timestamp
);

CREATE TABLE IF NOT EXISTS project_meta (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
-- Stores: last_full_index, project_root, total_files, total_chunks
```

**Phase 3.2 — The `specsync index` command**

Implement fully in `cli.py`. The command:

1. Detects project root: walk up from `os.getcwd()` looking for `.git`, `pyproject.toml`, `setup.py`, `package.json`. First found determines root. If none found, use `os.getcwd()` and warn the user.
2. Calls `storage.ensure_dirs(project_root)` to create all required directories
3. Shows a Rich progress bar during indexing: "Indexing {filename}..." updating per file
4. Calls CodeSearchMCP `index_codebase()` through the MCP manager
5. On completion, shows a summary: files indexed, chunks created, time taken

The `--status` flag: shows current index state from SQLite — how many files, last indexed, how many files have changed since last index.

The `--clear` flag: deletes the ChromaDB directory and SQLite file for this project. Asks for confirmation first.

**Phase 3.3 — Incremental indexing logic**

In `indexer.py`, implement incremental detection:
1. Load the `indexed_files` table from SQLite
2. Walk the project directory, respecting `.gitignore` using `pathspec`
3. For each file, compare `os.path.getmtime()` against the stored value
4. Files with newer mtime: re-chunk, re-embed, update ChromaDB document, update SQLite
5. Files that no longer exist: delete from ChromaDB, delete from SQLite
6. New files: chunk, embed, add to ChromaDB, insert into SQLite

**Verification for Phase 3:** Run `specsync index` on a real Python project. Verify ChromaDB directory is created in the correct Windows path. Run `specsync index --status` and see accurate counts. Modify one file and run `specsync index` again — verify only that file is re-indexed (check logs).

---

### PHASE 4 — Agent Pipeline

**Goal:** All three agents implemented and working end-to-end on real input.

**Phase 4.1 — Data models**

Implement all Pydantic models in `specsync/core/models.py`. Every model used anywhere in the system is defined here. Key models:

```python
class RequirementType(str, Enum):
    FEATURE = "feature"
    CONSTRAINT = "constraint"
    DATA_MODEL = "data_model"
    API_CHANGE = "api_change"
    BEHAVIOUR = "behaviour"

class RequirementStatus(str, Enum):
    FULLY_EXISTS = "FULLY_EXISTS"
    PARTIALLY_EXISTS = "PARTIALLY_EXISTS"
    MISSING = "MISSING"
    CONFLICTED = "CONFLICTED"

class Requirement(BaseModel):
    id: str
    description: str
    requirement_type: RequirementType
    priority: Literal["high", "medium", "low"]
    raw_text: str

class SearchResult(BaseModel):
    file_path: str
    chunk_type: str
    name: str
    start_line: int
    end_line: int
    similarity_score: float
    content: str

class RequirementAnalysis(BaseModel):
    requirement: Requirement
    status: RequirementStatus
    matched_files: list[str]
    matched_functions: list[str]
    conflict_details: ConflictResult | None
    classification_reason: str

class ConflictResult(BaseModel):
    affected_files: list[str]
    conflict_severity: Literal["high", "medium", "low"]
    explanation: str

class EffortEstimate(BaseModel):
    conflict_resolution_hours: float
    extension_hours: float
    net_new_hours: float
    testing_hours: float
    total_days: float
    confidence: Literal["low", "medium", "high"]
    notes: str

class GapReport(BaseModel):
    spec_source: str
    reuse: list[RequirementAnalysis]
    extend: list[RequirementAnalysis]
    conflicts: list[RequirementAnalysis]
    net_new: list[RequirementAnalysis]
    edge_cases: list[EdgeCase]
    data_models: list[DataModel]
    api_changes: list[APIChange]
    implementation_order: list[str]
    effort_estimate: EffortEstimate
    generated_at: datetime
```

**Phase 4.2 — LLM factory**

Implement `specsync/core/llm.py` fully. The `get_llm()` function:

```python
def get_llm(config: SpecSyncConfig) -> BaseChatModel:
    provider = config.llm.provider
    if provider == "ollama":
        from langchain_ollama import ChatOllama
        return ChatOllama(
            model=config.llm.model,
            base_url=config.llm.base_url,
            temperature=config.llm.temperature
        )
    elif provider == "groq":
        from langchain_groq import ChatGroq
        return ChatGroq(
            model=config.llm.model,
            api_key=config.llm.groq_api_key,
            temperature=config.llm.temperature
        )
    # ... etc for all providers
```

Also implement `get_llm_with_fallback(config)` which wraps the primary LLM with a fallback using LangChain's `.with_fallbacks()` method.

**Phase 4.3 — SpecParserAgent**

Implement `specsync/agents/spec_parser.py` as a LangGraph `StateGraph`. Implement every node as described in Section 8. The graph state type is `PipelineState`. Use `TypedDict` for the LangGraph state (LangGraph requires TypedDict, not dataclass). Implement all nodes. Connect with edges. The graph must handle the case where Brave Search is not configured — the `search_context` node returns empty context and the graph continues.

**Phase 4.4 — CodeInventoryAgent**

Implement `specsync/agents/code_inventory.py`. The critical implementation detail is the parallel search in `search_requirements` — use `asyncio.gather(*[search_one(req) for req in requirements])`. The LLM classification in `classify_requirements` uses structured output parsing — use LangChain's `.with_structured_output(RequirementClassification)` to get typed output directly.

**Phase 4.5 — GapReportAgent**

Implement `specsync/agents/gap_report.py`. The effort estimation uses a combination of heuristics and LLM reasoning. Base heuristics: each CONFLICTED requirement with >5 affected files = 6h, with 2–5 files = 4h, with <2 files = 2h. Each EXTEND = 2h. Each NET_NEW feature = 4h, data_model = 1h, api_change = 2h. Testing = 30% of total. The LLM then reviews these estimates and can adjust them with a reason.

**Phase 4.6 — Pipeline orchestrator**

Implement `specsync/agents/pipeline.py`. The `run_pipeline(config, mcp_manager, inputs) -> GapReport` function:

1. Initializes `PipelineState` from inputs
2. Runs SpecParserAgent — awaits completion
3. Runs CodeInventoryAgent — awaits completion
4. Runs GapReportAgent — awaits completion
5. Returns `GapReport`

Each agent run is wrapped in a try/except. If an agent fails, a Rich error panel is shown with the error message and the command exits with code 1.

**Verification for Phase 4:** Run the pipeline manually with a test spec string against the sample project fixture. Verify each agent produces correct output. The full `PipelineState` should be populated end-to-end.

---

### PHASE 5 — Terminal Output and Report Generation

**Goal:** `specsync analyze` produces beautiful, informative terminal output AND a well-formatted markdown file.

**Phase 5.1 — Terminal renderer**

Implement `specsync/output/terminal.py`. Uses Rich throughout — no raw strings.

Output structure (in order):

1. **Header panel:** "SpecSync Analysis" title, spec source, timestamp, project name
2. **Requirements extracted:** a Rich table showing each requirement with ID, type, priority, description (truncated at 60 chars)
3. **Gap Analysis section** — four subsections with distinct visual treatment:
   - ✅ REUSE (green panel): list of requirement + matched file + matched function
   - ⚠ EXTEND (yellow panel): list with file to extend
   - ❌ CONFLICT (red panel): list with conflict details, affected file count, severity
   - 🔨 NET NEW (blue panel): list with suggested new file location
4. **Edge Cases section:** yellow warning panel listing each edge case as a question
5. **Implementation Order:** numbered list showing the recommended sequence
6. **Effort Estimate:** a Rich table: category, hours, then total with confidence badge
7. **Footer:** path to saved markdown report

**Phase 5.2 — Markdown renderer**

Implement `specsync/output/markdown.py`. Generates a clean markdown file with the same information as the terminal output but in document form. Uses headings, tables, and checkboxes. The markdown file is designed to be committed to the repo or shared with the team.

File naming: `{source}-{date}-{time}.md`. For GitHub issues: `issue-142-2025-01-15-143022.md`.

**Phase 5.3 — The full `specsync analyze` command**

Wire everything together in `cli.py`. The command:

1. Validates config exists (if not, tells user to run `specsync init`)
2. Detects project root (same logic as `specsync index`)
3. Checks if project is indexed — if not, asks user if they want to index now
4. Opens MCPManager as context manager (launches all 5 servers, shows spinner)
5. Runs `run_pipeline()`
6. Renders terminal output via `terminal.py`
7. Saves markdown report via `markdown.py`
8. Shuts down MCPManager (kills all child processes)

The `--output` flag:
- `terminal` (default): Rich output only, no file saved
- `markdown`: Rich output + markdown file saved
- `both` (default when flag omitted): both
- `json`: outputs raw JSON of the GapReport to stdout (for scripting)

**Phase 5.4 — The `specsync search` command**

Implement the standalone search command. Launches only CodeSearchMCP (not all 5 servers — startup is faster). Takes the query string, calls `semantic_search`, shows results as a Rich table: file path, function name, similarity score (as a percentage), first line of content.

**Verification for Phase 5:** Run `specsync analyze --issue {any real issue number}` against a real GitHub repo with a real codebase indexed. Verify: terminal output renders correctly with colors and panels, markdown file is saved to correct Windows path, JSON output works for piping.

---

### PHASE 6 — Polish, Error Handling, and `specsync reports`

**Goal:** The tool feels complete, handles edge cases gracefully, and has full report management.

**Phase 6.1 — The `specsync reports` command**

`specsync reports` lists all saved reports for the current project. Output: Rich table with report ID, spec source, date, number of requirements, number of conflicts.

`specsync reports --show REPORT_ID` reads the markdown file and renders it to the terminal using Rich's Markdown renderer.

**Phase 6.2 — Error handling audit**

Go through every command and every agent node. Ensure every error path shows a Rich-formatted error panel — never a raw Python traceback to the user. The traceback is only shown in `--verbose` mode. Normal mode shows: what went wrong, why it likely happened, what to do about it.

Common errors to handle specifically:
- Ollama not running: "Ollama is not reachable at {url}. Start it with: ollama serve"
- Node.js not found: "Node.js is required for SpecSync. Download it from nodejs.org"
- GitHub token invalid: "Your GitHub token is invalid or expired. Run: specsync init to update it"
- Project not indexed: "This project has not been indexed yet. Run: specsync index"
- No requirements extracted: "No requirements could be extracted from the spec. Try being more specific."
- Groq rate limit hit: "Groq rate limit reached. Waiting {N} seconds..." (then retries automatically)

**Phase 6.3 — The `specsync config` command**

`specsync config --show`: displays current config as a Rich table. Masks API keys — shows only last 4 characters.

`specsync config --set key=value`: updates a single config value. Supports dot notation: `specsync config --set llm.model=llama3.2:3b`. Validates the value makes sense before saving.

**Phase 6.4 — Windows-specific validation**

On Windows with Python 3.12:
- All paths use `pathlib.Path` throughout — never string concatenation for paths
- `platformdirs` returns correct `%APPDATA%` and `%LOCALAPPDATA%` paths
- Subprocess launches for Node.js use `shell=True` on Windows to ensure `npx` resolves correctly (npx.cmd on Windows)
- ChromaDB persistent client works correctly on Windows paths (no forward-slash issues)

**Verification for Phase 6:** Run the full flow start to finish on a real project. Every error path tested manually. `specsync doctor` shows all green. `specsync reports` shows saved reports correctly.

---

### PHASE 7 — Testing

**Goal:** Core functionality covered by automated tests.

Test files to implement:

`test_config.py`: config reads/writes correctly, defaults are correct, path resolution uses platformdirs correctly

`test_storage.py`: project hash is deterministic, directories are created in correct locations, SQLite schema creation works

`test_indexer.py`: Python file chunking produces correct chunks for functions, classes, methods; incremental indexing only re-indexes changed files; gitignore patterns are respected

`test_mcp_servers.py`: SpecAnalysisMCP returns valid Requirement objects for a sample spec; CodeSearchMCP semantic_search returns results above similarity threshold

`test_agents.py`: each agent produces correct output type given mocked MCP clients; pipeline runs end-to-end with fixture data

Use the `sample_project/` fixture — a small Python project with a clear structure that can be indexed in tests.

---

## 13. What Does Not Exist in SpecSync

To be explicit about scope boundaries:

- **No web UI.** Terminal only. Streamlit is not used.
- **No database server.** SQLite is file-based. ChromaDB is file-based. No Postgres, no Redis, no running servers.
- **No cloud sync.** Reports and indexes are local only.
- **No code generation.** SpecSync tells you what to do. It does not write code for you.
- **No real-time watching.** SpecSync runs on demand. It does not watch files for changes.
- **No multi-language AST parsing in v0.1.** The AST-based chunker works on Python files. JavaScript, TypeScript, Go, and other languages get the generic line-based chunker. Python-specific chunking (by function/class) is the primary language support. This can be extended in future versions.
- **No authentication or multi-user.** SpecSync is a single-developer local tool.

---

## 14. Definition of Done

The project is complete when:

1. `pipx install specsync` (or `pip install specsync`) installs cleanly on Windows with Python 3.12
2. `specsync init` completes successfully with Ollama (`qwen2.5-coder:7b` or any available model)
3. `specsync doctor` shows all services green
4. `specsync index` indexes a real Python project and reports accurate file/chunk counts
5. `specsync analyze --issue {N}` runs end-to-end against a real GitHub issue and a real indexed codebase and produces a meaningful gap report
6. Terminal output renders correctly with Rich formatting
7. Markdown report is saved to the correct Windows path
8. `specsync search "query"` returns semantically relevant results
9. `specsync reports` lists saved reports
10. All error paths show friendly Rich error panels, not raw tracebacks
11. The tool works completely offline when Ollama is the configured provider (only GitHub API call requires internet — for fetching the issue)
