# Tool System

The ToolRegistry, SecurityGate, all 29 built-in tools, and how to extend with plugin tools.

---

## ToolRegistry — register / call / get_definitions

```mermaid
flowchart TD
    INIT[ToolRegistry.__init__\n_tools dict]
    REGISTER[registry.register\nname + description + parameters_schema + handler]
    TOOLS_DICT[_tools[name] = ToolEntry\ndescription, schema, handler callable]
    GET_DEFS[registry.get_definitions\nreturn list of tool dicts\nfor LLM API tool_choice array]
    CALL[registry.call(name, args)\nlookup handler + execute]
    NAMES[registry.names\nreturn list of registered tool names]

    INIT --> REGISTER --> TOOLS_DICT
    TOOLS_DICT --> GET_DEFS
    TOOLS_DICT --> CALL
    TOOLS_DICT --> NAMES
```

**`get_definitions()` output shape (what goes to the LLM):**
```json
[
  {
    "name": "read_file",
    "description": "Read the contents of a file...",
    "input_schema": {
      "type": "object",
      "properties": {
        "path": { "type": "string", "description": "Absolute or relative file path" }
      },
      "required": ["path"]
    }
  },
  ...
]
```

---

## SecurityGate — BLOCK / WARN / PASS

The gate wraps `write_file` and `edit_file`. It is installed in `DevAgentSession.__init__` by replacing the raw handler with a wrapped version.

```mermaid
flowchart TD
    WRITE_CALL[Agent calls write_file or edit_file\nargs: path + content]
    GATE[SecurityGate.scan\npath + content]

    BLOCK_CHECKS{Block patterns found?}
    BLOCK_PATTERNS["• hardcoded API key / secret\n• eval(user_input) pattern\n• exec(user_controlled) pattern\n• path traversal ../../etc/passwd\n• subprocess shell=True with untrusted var\n• known CVE patterns"]
    BLOCK_RESULT[return [blocked] Write rejected\nSecurityGate logs action]

    WARN_CHECKS{Warn patterns found?}
    WARN_PATTERNS["• chmod 777 on sensitive path\n• curl | bash pattern\n• disabling auth / rate limiting\n• dev/test credential that looks real"]
    CONFIRM{confirm_fn(warn_msg)?}
    USER_CONFIRMS[User types y/n]
    REJECT[return [security_rejected] Cancelled\nlogs REJECTED_BY_USER]
    PASS_WRITE[call original write handler\nfile written to disk]
    PASS_RESULT[return normal write result]

    WRITE_CALL --> GATE
    GATE --> BLOCK_CHECKS
    BLOCK_CHECKS -->|yes| BLOCK_PATTERNS
    BLOCK_PATTERNS --> BLOCK_RESULT
    BLOCK_CHECKS -->|no| WARN_CHECKS
    WARN_CHECKS -->|yes| WARN_PATTERNS
    WARN_PATTERNS --> CONFIRM
    CONFIRM --> USER_CONFIRMS
    USER_CONFIRMS -->|no| REJECT
    USER_CONFIRMS -->|yes| PASS_WRITE
    WARN_CHECKS -->|no| PASS_WRITE
    PASS_WRITE --> PASS_RESULT
```

**Log entry shape:**
```json
{
  "action": "BLOCKED",
  "file": "src/auth.py",
  "reasons": ["hardcoded_secret: AWS_SECRET_KEY found in content"]
}
```

---

## Built-in tool inventory

### File tools (`tools/file_tools.py`)

| Tool | Args | What it does |
|---|---|---|
| `read_file` | `path`, `offset?`, `limit?` | Read a file, optionally with line offset and limit |
| `write_file` | `path`, `content` | Write entire file content (goes through SecurityGate) |
| `edit_file` | `path`, `old_string`, `new_string` | Exact string replacement in a file |
| `find_files` | `pattern`, `path?` | Glob pattern search, returns matching paths |
| `list_files` | `path?`, `recursive?` | Directory listing |

### Shell tool (`tools/shell_tool.py`)

| Tool | Args | What it does |
|---|---|---|
| `run_shell` | `command`, `timeout?` | Run a shell command, capture stdout+stderr, cap output at 8KB |

### Git tools (`tools/git_tools.py`)

| Tool | Args | What it does |
|---|---|---|
| `git_status` | — | Current working tree status |
| `git_diff` | `path?`, `staged?` | Diff of working tree or staged changes |
| `git_log` | `n?`, `path?` | Recent commits (last N) |
| `git_show` | `ref` | Show a specific commit |
| `git_commit` | `message`, `files?` | Stage files and commit |

### Search tools (`tools/search_tools.py`)

| Tool | Args | What it does |
|---|---|---|
| `grep` | `pattern`, `path?`, `glob?` | ripgrep-style content search |
| `web_search` | `query`, `count?` | Brave or SearchX web search |

### GitHub tools (`tools/github_tools.py`)

| Tool | Args | What it does |
|---|---|---|
| `github_get_issue` | `owner`, `repo`, `number` | Fetch issue JSON |
| `github_get_pr` | `owner`, `repo`, `number` | Fetch PR JSON + diff |
| `github_list_issues` | `owner`, `repo`, `state?` | List issues |
| `github_post_comment` | `owner`, `repo`, `number`, `body` | Post a comment on issue or PR |
| `github_create_pr` | `owner`, `repo`, `title`, `body`, `head`, `base` | Create a PR |
| `github_create_branch` | `owner`, `repo`, `branch`, `sha` | Create a branch |

### CodePrism tools (`tools/codeprism_tools.py`)

| Tool | Args | What it does |
|---|---|---|
| `cp_get_context` | `query`, `top_k?` | Semantic context query — most relevant code for a question |
| `cp_search_symbol` | `name`, `kind?` | Find a symbol by name across the graph |
| `cp_get_module_summary` | `file_path` | Summary of a file: public API, test file, imports |
| `cp_get_callers` | `file_path`, `symbol` | Who calls this function |
| `cp_get_callees` | `file_path`, `symbol` | What this function calls |
| `cp_get_file_map` | — | Full project file map (path → role, symbol count) |
| `cp_get_dependencies` | `file_path` | Import dependency tree |
| `cp_get_impact` | `file_path`, `symbol` | Change impact analysis (severity, surface area) |
| `cp_get_data_flow` | `file_path`, `symbol` | Data flow through a function |
| `cp_get_stats` | — | Graph-wide metrics (node count, edge count, etc.) |

### Memory tools (`tools/memory_tools.py`)

| Tool | Args | What it does |
|---|---|---|
| `remember_fact` | `key`, `value` | Store a fact in the session memory block |
| `recall_facts` | — | Return all stored facts as a formatted string |
| `forget_fact` | `key` | Remove a fact from session memory |

---

## Tool call lifecycle (detailed)

```mermaid
sequenceDiagram
    participant LOOP as AgentLoop
    participant REG as ToolRegistry
    participant GATE as SecurityGate
    participant HANDLER as Tool handler function

    LOOP->>REG: call("write_file", {"path": "x.py", "content": "..."})
    REG->>REG: lookup _tools["write_file"]
    REG->>GATE: wrapped_handler({"path": "x.py", "content": "..."})
    Note over GATE: SecurityGate.scan(path, content)
    GATE->>GATE: check BLOCK patterns
    GATE->>GATE: check WARN patterns
    alt PASS
        GATE->>HANDLER: original_write_handler(args)
        HANDLER->>HANDLER: write file to disk
        HANDLER-->>GATE: "File written: x.py"
        GATE-->>REG: "File written: x.py"
    else WARN + user confirms
        GATE->>GATE: prompt user via confirm_fn
        GATE->>HANDLER: original_write_handler(args)
        HANDLER-->>GATE: "File written: x.py"
        GATE-->>REG: "File written: x.py"
    else BLOCK
        GATE-->>REG: "[blocked] Write rejected: hardcoded_secret"
    end
    REG-->>LOOP: result string
```

---

## Writing a plugin tool

```python
from devagent.tools.registry import ToolRegistry

def search_internal_docs(args: dict) -> str:
    query = args.get("query", "")
    # your logic here — NEVER raise, always return str
    return f"Results for '{query}': ..."

def register(registry: ToolRegistry) -> None:
    registry.register(
        name="search_internal_docs",
        description=(
            "Search the company's internal documentation. "
            "Use when the user asks about internal APIs or processes."
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

**Rules:**
- Handler receives a single `dict`, always returns `str`
- Never raise — return `"[error] ..."` on failure
- Keep description precise — the LLM decides when to call it based on the description
- Avoid side effects that can't be undone without confirmation
- Register the tool in `DevAgentSession.__init__` before the session starts, or load via a plugin entry point

---

## Tool output size conventions

| Tool | Max output |
|---|---|
| `run_shell` | 8KB (truncated, labeled) |
| `read_file` | 50KB (offset/limit available) |
| `grep` | 250 matches (default head limit) |
| `web_search` | Top N results (default 5) |
| `cp_*` tools | JSON — no explicit cap (graph queries are always bounded by symbol count) |
