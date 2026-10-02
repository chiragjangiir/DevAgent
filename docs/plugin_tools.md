# Plugin Tool Interface

DevAgent's agent loop is tool-driven: the LLM decides which tools to call, and the results feed back into the next iteration. The tool interface is a single Python callable — no framework, no decorators.

## Anatomy of a tool

```python
def my_handler(args: dict) -> str:
    """
    Every tool handler:
      - Receives a single dict of arguments (already validated by the LLM)
      - Returns a plain string result
      - NEVER raises — return '[error] <message>' on failure
      - Is synchronous (async handlers are not supported — use run_in_executor if needed)
    """
    value = args.get("key", "")
    return f"Result: {value}"
```

## Registering a tool

```python
from devagent.tools.registry import ToolRegistry

def register_my_tools(registry: ToolRegistry) -> None:
    registry.register(
        name="my_tool",           # called by the LLM — must be snake_case, unique
        description=(             # shown to the LLM — be specific and action-oriented
            "Fetch the latest deployment status for a service. "
            "Returns JSON with fields: status, version, deployed_at."
        ),
        parameters={              # JSON Schema (OpenAI tool-calling format)
            "type": "object",
            "properties": {
                "service": {
                    "type": "string",
                    "description": "The service name, e.g. 'api-gateway'",
                },
                "environment": {
                    "type": "string",
                    "enum": ["staging", "production"],
                    "description": "Target environment",
                },
            },
            "required": ["service"],
        },
        handler=my_handler,
    )
```

## Wiring into a session

Pass a setup callback to `build_registry` via the caller, or register after the registry is built:

```python
from devagent.agent.flows import DevAgentSession
from devagent.tools.registry import build_registry
from my_plugin import register_my_tools

# Option A — after DevAgentSession construction (access the registry directly)
session = DevAgentSession(cfg, project_root)
register_my_tools(session._loop.registry)

# Option B — subclass DevAgentSession
class MySession(DevAgentSession):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        register_my_tools(self._loop.registry)
```

## Tool result conventions

| Prefix | Meaning |
|--------|---------|
| `[error] ...` | Tool failed — LLM sees the error and can try to recover |
| `[blocked] ...` | Security gate blocked a write — LLM cannot bypass this |
| `[remembered] ...` | Memory tool confirmation |
| `[auto_test] ...` | Injected by the repair loop — not a tool result from the LLM |

Any other string is a successful result.

## Security: wrapping write tools

If your tool writes files, wrap it with the security gate so the agent's writes go through the same BLOCK/WARN pipeline as the built-in `write_file`:

```python
from devagent.tools.security_gate import wrap_write_with_security

registry.register("my_write_tool", ..., handler=my_write_handler)
registry._handlers["my_write_tool"] = wrap_write_with_security(
    my_write_handler,
    codeprism_client=cp,
    project_root=project_root,
    operation="write",
    security_log=security_log,
    confirm_fn=confirm_fn,
    extra_dirs=extra_dirs,
)
```

The gate resolves the path through the same rule your write tool uses and refuses
anything outside `project_root` (or `extra_dirs`) with a BLOCK, *before* any
impact or CVE check runs. So `extra_dirs` must be the same list you gave the
write tool: omit it and the gate will block legitimate writes to those
directories, because as far as it can tell they escape the project.

## Parameters schema tips

- Use `"description"` on every property — the LLM reads these to decide what to pass
- Mark genuinely required params in `"required"` — don't over-constrain
- For file paths, say "relative to the project root" explicitly
- For free-text, cap with `"maxLength"` to prevent prompt stuffing

## Built-in tools reference

| Tool | Description |
|------|-------------|
| `read_file` | Read a file by path |
| `write_file` | Write (create/overwrite) a file |
| `edit_file` | Replace a specific string in a file |
| `list_files` | List files in a directory |
| `find_files` | Glob pattern file search |
| `grep` | Regex search across files |
| `run_shell` | Execute a shell command (blocklist enforced) |
| `git_diff` | Show working-tree diff |
| `git_show` | Show a commit's content |
| `git_log` | Recent commit history |
| `cp_get_context` | CodePrism: context for a symbol or file |
| `cp_get_impact` | CodePrism: blast radius of changing a symbol |
| `cp_get_data_flow` | CodePrism: trace data through the graph |
| `cp_search_symbol` | CodePrism: find a symbol by name |
| `cp_get_file_map` | CodePrism: full file map with roles |
| `cp_get_module_summary` | CodePrism: public API + test coverage for a file |
| `cp_get_callers` | CodePrism: who calls a symbol |
| `cp_get_callees` | CodePrism: what a symbol calls |
| `cp_get_dependencies` | CodePrism: dependency graph for a file |
| `remember_fact` | Store a key-value fact in session memory |
| `recall_facts` | List all stored session facts |
| `forget_fact` | Remove a fact from session memory |
| `gh_get_issue` | GitHub: fetch a single issue |
| `gh_list_issues` | GitHub: list open issues |
| `gh_create_pr` | GitHub: open a pull request |
| `gh_list_pr_files` | GitHub: list files changed in a PR |
| `gh_review_pr` | GitHub: post a PR review |
| `gh_comment_issue` | GitHub: comment on an issue |
| `gh_branch_create` | GitHub: create a branch from a SHA |
| `gh_list_workflow_runs` | GitHub: list CI runs |
| `gh_get_run_logs` | GitHub: fetch failed CI job logs |
