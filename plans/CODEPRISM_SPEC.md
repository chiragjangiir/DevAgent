# CodePrism — Complete Package Specification

> Standalone Python package + MCP server that builds and maintains a persistent
> knowledge graph of any codebase, exposing precise, token-efficient context to
> AI coding agents.
>
> PyPI name: `codeprism` (confirmed available)
> GitHub repo: separate from DevAgent

---

## 1. What CodePrism Is

CodePrism solves the single biggest bottleneck in AI-assisted coding: **the agent
has to re-read the entire codebase every time it needs context.**

Instead of agents greping through files or doing vector similarity search,
CodePrism maintains a live **knowledge graph** of the codebase — nodes for every
file, module, class, function, variable, and type; edges for every call, import,
data flow, and inheritance relationship. When an agent needs to understand "what
would break if I change `process_payment()`?", CodePrism returns the exact
subgraph — not 4000 lines of raw code.

**Token reduction target: 60–80% on large codebases compared to file-reading.**

CodePrism is designed to be used by:
1. **DevAgent** (primary consumer) — the agent harness that ships with CodePrism integration built in
2. **Claude Code** — via MCP server integration
3. **Cursor / Codex / any MCP-compatible agent** — same MCP interface
4. **Any Python program** — via the direct Python library API

---

## 2. Core Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                     MCP Server (FastMCP)                        │
│   Tool calls from any agent → graph queries → structured JSON   │
└──────────────────────────────┬──────────────────────────────────┘
                               │
┌──────────────────────────────▼──────────────────────────────────┐
│                    CodePrism Core Library                       │
│  GraphEngine  │  QueryEngine  │  SecurityScanner  │  Indexer   │
└──────┬─────────────────────────────────────────┬────────────────┘
       │                                         │
┌──────▼──────┐                        ┌─────────▼──────────────┐
│  Graph DB   │                        │  AST Parser Layer       │
│  (SQLite +  │                        │  tree-sitter            │
│  NetworkX)  │                        │  Python / JS / TS / Go  │
└─────────────┘                        └────────────────────────┘
                                                 ▲
                                       ┌─────────┴──────────────┐
                                       │   File Watcher          │
                                       │   (watchdog)            │
                                       │   Incremental updates   │
                                       └────────────────────────┘
```

---

## 3. Knowledge Graph Schema

### Node Types

| Node Type  | Fields |
|---|---|
| `File`     | path, language, size_bytes, last_modified, checksum, line_count |
| `Module`   | name, file_path, is_package, docstring |
| `Class`    | name, file_path, line_start, line_end, docstring, is_abstract, base_classes |
| `Function` | name, file_path, line_start, line_end, docstring, signature, is_async, is_method, complexity_score |
| `Variable` | name, file_path, scope, type_annotation, is_constant |
| `Import`   | name, file_path, alias, is_from_import, source_module |
| `Type`     | name, file_path, definition |

### Edge Types

| Edge         | From → To               | Meaning |
|---|---|---|
| `calls`      | Function → Function     | A calls B at a specific line |
| `imports`    | File → Module           | File imports this module |
| `inherits`   | Class → Class           | Inheritance relationship |
| `uses`       | Function → Variable     | Function reads/writes this variable |
| `defines`    | File/Class → Function   | Ownership |
| `data_flows` | Variable → Variable     | Data from A is passed into B |
| `exports`    | Module → Symbol         | Public API surface |
| `tests`      | Function → Function     | Test function covers this function |
| `references` | Function → Type         | Function uses this type in signature/body |

### Edge Metadata
Every edge stores: `file_path`, `line_number`, `weight` (call frequency if
available), `is_conditional` (inside if/try blocks).

---

## 4. Tech Stack (Python 3.12+)

### Core
| Package | Version | Purpose |
|---|---|---|
| `tree-sitter` | >=0.23 | Multi-language AST parsing (C extension, very fast) |
| `tree-sitter-python` | latest | Python grammar for tree-sitter |
| `tree-sitter-javascript` | latest | JavaScript grammar |
| `tree-sitter-typescript` | latest | TypeScript grammar |
| `tree-sitter-go` | latest | Go grammar |
| `tree-sitter-rust` | latest | Rust grammar (optional v1) |
| `networkx` | >=3.3 | In-memory graph operations, traversal algorithms |
| `aiosqlite` | >=0.20 | Async SQLite for graph persistence |
| `pydantic` | >=2.8 | All data models and validation |
| `watchdog` | >=4.0 | File system watcher for incremental updates |
| `fastmcp` | >=0.1 | MCP server implementation |

### Semantic Layer (optional, enabled by config flag)
| Package | Purpose |
|---|---|
| `sentence-transformers` | Symbol/docstring embeddings for semantic search |
| `chromadb` | Vector store for embedding-based lookup |

### Security Scanning
| Package | Purpose |
|---|---|
| `bandit` | Python-specific security linting (AST-based) |
| `semgrep` | Cross-language security rule engine |
| `gitpython` | Git-aware secret detection (check .gitignore, staged files) |
| Custom pattern library | Regex + AST patterns for secrets, env vars, OWASP Top 10 |

### CLI & Output
| Package | Purpose |
|---|---|
| `typer[all]` | CLI interface |
| `rich` | Terminal rendering, graph visualization in ASCII |
| `platformdirs` | Cross-OS path resolution |

### Dev & Testing
| Package | Purpose |
|---|---|
| `pytest` + `pytest-asyncio` | Test framework |
| `pytest-cov` | Coverage |
| `ruff` | Linting + formatting |
| `mypy` | Type checking |
| `hypothesis` | Property-based testing for graph invariants |

---

## 5. Directory Structure

```
codeprism/
├── __init__.py                  # Public API surface
├── cli.py                       # typer CLI: index, query, serve, watch, security
│
├── core/
│   ├── graph.py                 # GraphEngine: CRUD for nodes/edges, NetworkX wrapper
│   ├── storage.py               # SQLite persistence layer (async), schema migrations
│   ├── models.py                # All Pydantic node/edge models
│   ├── config.py                # CodePrismConfig (toml-based)
│   └── paths.py                 # platformdirs-based path resolution
│
├── parser/
│   ├── base.py                  # BaseParser abstract class
│   ├── python_parser.py         # tree-sitter Python → graph nodes/edges
│   ├── javascript_parser.py     # tree-sitter JS/TS → graph nodes/edges
│   ├── go_parser.py             # tree-sitter Go → graph nodes/edges
│   ├── generic_parser.py        # Fallback: line-based for unknown langs
│   └── registry.py              # Maps file extension → parser class
│
├── indexer/
│   ├── project_indexer.py       # Full project scan, parallel file processing
│   ├── incremental_updater.py   # File-change handler, partial graph update
│   └── watcher.py               # watchdog integration, debounced update queue
│
├── query/
│   ├── engine.py                # QueryEngine: all graph query methods
│   ├── context.py               # get_context() — assembles minimal LLM context
│   ├── impact.py                # get_impact() — transitive impact analysis
│   └── summary.py               # get_module_summary() — file-level narrative
│
├── security/
│   ├── gate.py                  # SecurityGate: intercepts proposed writes
│   ├── scanner.py               # SecurityScanner: runs all checks
│   ├── detectors/
│   │   ├── secrets.py           # Hardcoded secrets, API keys, passwords
│   │   ├── env_vars.py          # Env var exposure (logged, returned, written)
│   │   ├── injection.py         # SQL injection, command injection, eval/exec
│   │   ├── crypto.py            # Weak crypto (MD5, SHA1, random for secrets)
│   │   ├── dependencies.py      # New dep with known CVE (via OSV/safety)
│   │   └── git_safety.py        # .gitignore compliance, staged file check
│   └── rules/
│       ├── python_rules.json    # Bandit-style rules for Python patterns
│       └── common_rules.json    # Cross-language OWASP patterns
│
├── mcp/
│   ├── server.py                # FastMCP server definition
│   └── tools.py                 # All MCP tool implementations (thin wrappers over query engine)
│
└── embeddings/                  # Optional semantic layer
    ├── embedder.py              # sentence-transformers wrapper
    └── store.py                 # ChromaDB wrapper

tests/
├── conftest.py
├── fixtures/
│   ├── sample_python_project/  # Multi-file Python project for integration tests
│   ├── sample_js_project/      # JS project fixture
│   └── sample_security_issues/ # Files with known security issues for scanner tests
├── test_parser_python.py
├── test_parser_javascript.py
├── test_graph_engine.py
├── test_storage.py
├── test_indexer.py
├── test_incremental_updater.py
├── test_query_engine.py
├── test_impact_analysis.py
├── test_security_gate.py
├── test_security_detectors.py
├── test_mcp_server.py
└── test_cli.py
```

---

## 6. MCP Tools (Full Specification)

These are the tools exposed by the MCP server. Every agent that connects to
CodePrism gets these tools.

### Indexing & Management

```
index_project(path: str, languages: list[str] = None) -> IndexResult
  Build the full knowledge graph for a project.
  Returns: file_count, symbol_count, edge_count, duration_seconds, errors[]

update_file(path: str) -> UpdateResult
  Incrementally update graph for a single changed file.
  Returns: nodes_added, nodes_removed, edges_updated

get_graph_stats(path: str) -> GraphStats
  Returns: file_count, class_count, function_count, edge_count,
           languages[], last_indexed_at, coverage_percent
```

### Context Retrieval

```
get_context(file: str, symbol: str, depth: int = 2) -> ContextResult
  The core tool. Returns minimal, structured context for a symbol.
  depth=1: symbol + direct callees/callers
  depth=2: + their direct neighbors (recommended default)
  depth=3: full transitive neighborhood (use sparingly)
  Returns: symbol_definition, direct_callers[], direct_callees[],
           related_types[], relevant_variables[], estimated_token_count

get_module_summary(file: str) -> ModuleSummary
  Returns: purpose (1-paragraph), public_api[], dependencies[],
           complexity_score, test_coverage_file (if found), key_classes[]

get_file_map(path: str) -> FileMap
  Returns the full file tree with per-file role summaries.
  Token-efficient entry point before any edits — gives the agent
  a map without reading any actual file content.
```

### Impact Analysis

```
get_impact(file: str, symbol: str) -> ImpactResult
  Transitive impact analysis: what breaks if this symbol changes?
  Returns: direct_dependents[], transitive_dependents[],
           severity (LOW/MEDIUM/HIGH/CRITICAL), affected_test_files[],
           public_api_affected (bool), estimated_change_surface

get_callers(file: str, function: str) -> CallerList
  All functions that call this function, with call site line numbers.

get_callees(file: str, function: str) -> CalleeList
  All functions called by this function.

get_data_flow(file: str, symbol: str) -> DataFlowResult
  Where does data from this symbol go? Traces assignments, parameter
  passing, and return values through the graph.
  Returns: sources[], sinks[], intermediate_nodes[], flow_path[]
```

### Symbol Search

```
search_symbol(query: str, project_path: str, kind: str = None) -> SearchResult
  Find symbols by exact name, prefix, or (if embeddings enabled) semantic query.
  kind: "function" | "class" | "variable" | "module" | None (all)
  Returns: matches[] with file, line, signature, docstring_excerpt

get_dependencies(file: str) -> DependencyResult
  All modules/packages this file depends on (direct + transitive).
  Returns: internal_deps[], external_deps[], circular_deps[]

get_dependents(file: str) -> DependentResult
  All files that import or call into this file.
```

### Security

```
scan_file(file: str, content: str = None) -> SecurityReport
  Run all security detectors on a file.
  content: if provided, scans proposed content (pre-write check)
  Returns: issues[] with severity, category, line, description, fix_suggestion

scan_diff(original: str, proposed: str, file: str) -> SecurityReport
  Security-diff: only reports issues introduced by the change, not pre-existing.
  This is the primary tool for the Security Gate.

check_secret_exposure(content: str) -> SecretResult
  Specifically checks for hardcoded secrets, tokens, API keys.
  Uses entropy analysis + pattern matching.
```

### Session Overlay

```
record_read(session_id: str, file: str, symbol: str)
  Tell CodePrism the agent has read this symbol in this session.
  Prevents redundant re-fetches.

record_write(session_id: str, file: str, content_before: str, content_after: str)
  Log a file write. Updates graph, runs security scan, returns SecurityReport.
  This is the core integration point for the Security Gate.

get_session_context(session_id: str) -> SessionContext
  What has been read/written in this session? Returns a compact summary
  the agent can include in its context window instead of re-fetching.

undo_write(session_id: str, steps: int = 1) -> UndoResult
  Restore files to their pre-write state using the session journal.
  Returns: files_restored[], content_before[]
```

---

## 7. Python Library API

For programs that embed CodePrism directly (not via MCP):

```python
from codeprism import CodePrism, SecurityGate

# Initialize for a project
prism = CodePrism(project_path="/path/to/project")
await prism.index()           # build graph (first run)
await prism.watch()           # start incremental updater

# Query
ctx = await prism.get_context("payments/processor.py", "process_payment")
impact = await prism.get_impact("payments/processor.py", "process_payment")
summary = await prism.get_module_summary("payments/processor.py")

# Security Gate integration
gate = SecurityGate(prism)
result = await gate.check_write("payments/processor.py", new_content)
if result.status == "BLOCK":
    raise SecurityError(result.explanation)

# Session management
session = prism.session("sess_abc123")
await session.record_read("payments/processor.py", "process_payment")
await session.record_write("payments/processor.py", old_content, new_content)
ctx_summary = await session.get_context()   # compact context for LLM
await session.undo(steps=2)
```

---

## 8. CLI Commands

```bash
# Index a project
codeprism index /path/to/project
codeprism index /path/to/project --languages python,javascript

# Query (for debugging / exploration)
codeprism context payments/processor.py::process_payment
codeprism impact payments/processor.py::process_payment
codeprism callers payments/processor.py::process_payment
codeprism search "handle authentication"
codeprism summary payments/processor.py

# Security
codeprism scan payments/processor.py
codeprism scan --all                    # scan entire project
codeprism scan --diff HEAD~1 HEAD       # scan only changed files

# Graph stats
codeprism stats
codeprism stats --verbose               # per-file complexity scores

# Watch (incremental updates)
codeprism watch /path/to/project        # foreground watcher

# MCP Server
codeprism serve                         # start MCP server on stdio (for Claude Code etc.)
codeprism serve --transport sse --port 8765   # SSE transport for remote agents
```

---

## 9. Storage Schema (SQLite)

### Tables

```sql
-- Core nodes
CREATE TABLE files (
    id TEXT PRIMARY KEY,
    path TEXT UNIQUE NOT NULL,
    language TEXT,
    checksum TEXT,
    last_modified REAL,
    line_count INTEGER,
    indexed_at REAL
);

CREATE TABLE symbols (
    id TEXT PRIMARY KEY,            -- sha256(file_path + name + kind)
    file_id TEXT REFERENCES files,
    name TEXT NOT NULL,
    kind TEXT NOT NULL,             -- function|class|variable|import|type
    line_start INTEGER,
    line_end INTEGER,
    signature TEXT,
    docstring TEXT,
    is_async BOOLEAN,
    is_public BOOLEAN,
    complexity_score REAL
);

-- Edges
CREATE TABLE edges (
    id TEXT PRIMARY KEY,
    kind TEXT NOT NULL,             -- calls|imports|inherits|uses|data_flows|tests|references
    from_symbol_id TEXT REFERENCES symbols,
    to_symbol_id TEXT REFERENCES symbols,
    file_id TEXT REFERENCES files,
    line_number INTEGER,
    weight REAL DEFAULT 1.0,
    is_conditional BOOLEAN DEFAULT FALSE
);

-- Security issues (persistent scan results)
CREATE TABLE security_issues (
    id TEXT PRIMARY KEY,
    file_id TEXT REFERENCES files,
    symbol_id TEXT REFERENCES symbols,
    detector TEXT NOT NULL,         -- secrets|env_vars|injection|crypto|dependencies
    severity TEXT NOT NULL,         -- INFO|WARN|BLOCK
    category TEXT,
    line_number INTEGER,
    description TEXT,
    fix_suggestion TEXT,
    detected_at REAL,
    resolved BOOLEAN DEFAULT FALSE
);

-- Session journal
CREATE TABLE session_events (
    id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL,
    event_type TEXT NOT NULL,       -- read|write|undo
    file_path TEXT,
    symbol_name TEXT,
    content_before TEXT,            -- stored for undo
    content_after TEXT,
    security_report TEXT,           -- JSON
    created_at REAL
);

-- Indexes
CREATE INDEX idx_symbols_file ON symbols(file_id);
CREATE INDEX idx_edges_from ON edges(from_symbol_id);
CREATE INDEX idx_edges_to ON edges(to_symbol_id);
CREATE INDEX idx_edges_kind ON edges(kind);
CREATE INDEX idx_session_events_session ON session_events(session_id);
```

---

## 10. Incremental Update Strategy

When a file changes (detected by watchdog):

1. Compute new checksum → skip if unchanged
2. Load existing nodes/edges for this file from SQLite
3. Parse file with tree-sitter → new nodes/edges
4. Diff old vs new: compute added/removed/modified symbols
5. Delete removed edges first (FK integrity)
6. Delete removed symbols
7. Insert new symbols, insert new edges
8. Update file record (checksum, last_modified)
9. Run security scanner on changed symbols only
10. Emit `file_updated` event (watcher consumers can subscribe)

**Never rebuild the entire graph for a file change.**

---

## 11. Security Gate — Decision Logic

```
For every proposed file write:

1. Run scan_diff(original, proposed, file)
2. Evaluate results:
   - Any BLOCK severity issue → return BLOCK with explanation, do not write
   - Any WARN severity issue → return WARN with details, agent must confirm
   - All PASS → return PASS, write proceeds

Severity mapping:
   BLOCK: hardcoded secrets, exposed env vars in API responses,
          SQL injection via string concat, eval(user_input),
          new dependency with CRITICAL CVE
   WARN:  weak crypto usage, MD5/SHA1 passwords, broad exception suppression,
          new external dependency (audit required),
          file in .gitignore being written to version-controlled path
   INFO:  style issues, missing type annotations on public API
         (INFO never blocks, only logged)
```

---

## 12. Graph Visualization (Future / UI Hook)

The library exposes a `to_graphviz()` and `to_json()` method on any subgraph
result. The JSON format is compatible with D3.js force-directed graph and Cytoscape.js
so that a future UI (in DevAgent or a standalone web viewer) can render the graph
without any schema changes.

```python
subgraph = await prism.get_subgraph(
    center="payments/processor.py::process_payment",
    depth=2
)
json_data = subgraph.to_json()     # D3/Cytoscape compatible
dot_data = subgraph.to_graphviz()  # render with graphviz
```

---

## 13. Language Support Roadmap

| Language   | Phase | Parser | Notes |
|---|---|---|---|
| Python     | v1.0  | tree-sitter-python | Full: functions, classes, imports, type hints |
| JavaScript | v1.0  | tree-sitter-javascript | Full: functions, classes, requires/imports |
| TypeScript | v1.0  | tree-sitter-typescript | Full: + interface, type alias |
| Go         | v1.1  | tree-sitter-go | Functions, structs, interfaces |
| Rust       | v1.2  | tree-sitter-rust | Functions, structs, traits |
| Java       | v2.0  | tree-sitter-java | Classes, methods, interfaces |
| C/C++      | v2.0  | tree-sitter-c/cpp | Functions, structs |

---

## 14. Configuration (TOML)

```toml
[codeprism]
project_path = "/path/to/project"
languages = ["python", "javascript", "typescript"]
enable_embeddings = false        # semantic search (heavier, slower index)
enable_security_gate = true
watch_debounce_ms = 500          # wait 500ms after last change before re-indexing

[codeprism.security]
block_on_secrets = true
warn_on_weak_crypto = true
check_new_dependencies = true
ignore_paths = ["tests/fixtures/", "*.example.*"]

[codeprism.embeddings]
model = "all-MiniLM-L6-v2"
device = "cpu"                   # or "cuda", "mps"

[codeprism.mcp]
transport = "stdio"              # or "sse"
port = 8765                      # only for sse transport
```

---

## 15. Open Source & Packaging

```toml
# pyproject.toml
[project]
name = "codeprism"
version = "0.1.0"
description = "Persistent knowledge graph for AI coding agents — 60-80% token reduction"
license = "MIT"
python_requires = ">=3.12"

[project.scripts]
codeprism = "codeprism.cli:app"

[project.optional-dependencies]
embeddings = ["sentence-transformers>=3.1.0", "chromadb>=0.5.0"]
security-full = ["bandit>=1.7.0", "semgrep>=1.0.0"]
```

**MIT license.** The graph engine, parsers, and MCP server are fully open source.
Security rule packs (advanced patterns) can be a paid add-on in future.

---

## 16. README Pitch (One-Paragraph)

> CodePrism builds a persistent knowledge graph of your codebase — every function,
> class, import, and data flow — and exposes it to AI agents via MCP. Instead of
> your agent reading 40 files to understand one function, it queries the graph and
> gets precisely what it needs in under 200 tokens. Plug it into Claude Code,
> Cursor, or DevAgent in one command: `codeprism serve`. Works offline. Updates
> incrementally. Scans every write for security issues before they hit disk.

---

*End of CodePrism specification.*
