# Companion Library Ideas

Private ideation notes. Not for public distribution.
`dev-docs/` is gitignored — this file is never committed.

Last updated: 2026-08-22

---

## Context

DevAgent + CodePrism form the core of the ecosystem. These are standalone libraries
that solve real pains in the AI coding agent space, are usable by anyone (not just
DevAgent), and each exposes a natural MCP server interface.

Each library follows the same pattern as CodePrism: independent PyPI package,
MCP server mode, usable as a Python library or a drop-in MCP source for any
AI editor (Claude Desktop, Cursor, Windsurf, etc.).

---

## The real problems these solve

1. "I can't tell what the agent did or why it made that choice" → AgentTrace
2. "I renamed a function and 40 callers broke silently" → ChangePropagator
3. "I'm scared to let the agent run shell commands on my machine" → SandboxKit
4. "The docs for this codebase waste 80% of tokens on human formatting" → DocPrism
5. "AI agents write code but I have no idea if it meets the spec" → SpecToTest
6. "Agents keep getting confused by my codebase's structure" → RepoAudit
7. "Long sessions hit the context window and degrade" → MemoryPrism (already logged in roadmap)

---

## Library 1: AgentTrace

**Tagline:** OpenTelemetry for AI agent sessions.

### The problem

When an agent session goes wrong, you have no structured way to understand why.
The session log is a flat list of messages. You can't see the decision tree,
can't replay a step with a different choice, can't compare two runs that diverged.
Worse in multi-agent systems (Phase 9) where multiple agents interact.

### What it is

A library that captures agent sessions as structured execution traces — spans,
decisions, tool calls, token costs — stored in a queryable format.

### API sketch

```python
from agenttrace import Tracer

tracer = Tracer(session_id="abc123", backend="sqlite")

with tracer.span("read_relevant_files") as span:
    result = read_file("auth/middleware.py")
    span.record_tool_call("read_file", {"path": "auth/middleware.py"}, result)
    span.set_token_cost(input=840, output=0)

with tracer.span("edit_auth_logic") as span:
    span.record_decision(
        prompt="Should I edit verify_token or create a new function?",
        choice="edit_verify_token",
        alternatives=["create_new_function", "add_wrapper"],
        reasoning="verify_token is called in 3 places; changing it affects them all"
    )
```

Trace output:
- Visualise as a decision tree in a browser UI
- Replay from any branch point with a different choice
- Compare two runs of the same task (what diverged?)
- Query: "show all sessions where the agent read a file 10+ times without writing"

### MCP surface

```
Resources:
  agenttrace://sessions                    → list all traced sessions
  agenttrace://sessions/{id}/tree          → decision tree JSON
  agenttrace://sessions/{id}/replay/{span} → replay from a specific point

Tools:
  record_span(session_id, span_name, data)
  record_decision(session_id, prompt, choice, alternatives, reasoning)
  get_session_summary(session_id)
  compare_sessions(session_id_a, session_id_b)
```

### Who else uses it

- Any AI editor that wants to debug agent behaviour
- Claude Code, Cursor — export traces for debugging
- CI pipelines: assert on agent behaviour ("task should complete in < 15 tool calls")
- Multi-agent orchestration systems: trace coordinator + worker interaction

### Differentiation

LangSmith: LangChain-coupled, cloud-only.
LangFuse: evaluation-focused, not replay-focused.
AgentTrace: local-first, framework-agnostic, built around replay and branch-point debugging.

### Priority

Medium term — becomes much more valuable once multi-agent orchestration (Phase 9)
exists. Tracing a multi-agent session is where debugging genuinely gets hard.

---

## Library 2: ChangePropagator

**Tagline:** Given "symbol X changed from A to B" — fix all callers automatically.

### The problem

You change a function signature, rename a class, or modify an interface. CodePrism
tells you *where* the callers are. But fixing them still requires reading each one,
understanding context, and writing the fix. For a renamed parameter or changed
return type, this is mechanical work the computer should do.

### What it is

A library that takes a *semantic change specification* and produces a list of file
patches to cascade that change across all affected callers.

### API sketch

```python
from changepropagator import ChangeSpec, Propagator

change = ChangeSpec(
    kind="rename_parameter",
    file="devagent/core/llm.py",
    symbol="LLMClient.complete_with_tools",
    from_="messages",
    to="conversation",
)

propagator = Propagator(project_root=".")
patches = propagator.compute(change)

# patches: list of FilePatches
# [
#   FilePatch(file="devagent/agent/loop.py", hunks=[...]),
#   FilePatch(file="tests/test_llm.py", hunks=[...]),
# ]

propagator.apply(patches, dry_run=True)   # preview
propagator.apply(patches)                 # apply to disk
```

### Supported change types

- **Rename:** function, class, method, variable, module
- **Signature change:** add parameter (with default), remove, reorder, change type annotation
- **Interface change:** add required field to dataclass / TypedDict / Pydantic model
- **Return type change:** update callers that pattern-match the return value
- **Move:** symbol moved from one module to another — update all imports

### MCP surface

```
Tools:
  compute_change_patches(change_spec) → list of patch hunks
  preview_change(change_spec) → human-readable summary of impact
  apply_change(change_spec, dry_run=False) → apply patches to disk
  estimate_change_effort(change_spec) → N files, M hunks, estimated risk
```

### Who else uses it

- IDE plugins (rename refactor, currently fragile across files)
- AI agents making signature changes (proactive fix instead of discovering breakage via tests)
- Code migration tooling (upgrade from API v1 to v2 across a whole repo)

### Differentiation

Rope (Python): AST-only, misses dynamic call patterns.
LSP rename: per-file, no cross-file semantic understanding.
ChangePropagator: combines AST analysis with CodePrism call graph to handle
patterns pure AST tools miss.

### Relationship to DevAgent

ChangePropagator becomes a tool in DevAgent's registry. When the agent changes
a function signature, it calls `compute_change_patches` to fix callers proactively
rather than discovering breakage through test failures.

### Priority

**Highest ROI — build soonest.** CodePrism already provides the call graph;
this is the natural next layer. Immediately useful in DevAgent's own refactoring flows.

---

## Library 3: SandboxKit

**Tagline:** Safe, ephemeral execution environments for AI agent tool calls.

### The problem

AI agents run shell commands on your machine. The DevAgent security gate catches
patterns in *code being written* but doesn't sandbox *commands being executed*.
"Clean up the build artifacts" is benign. The same command with a badly-scoped
glob is not. Agents need a safe place to run without risk to the host system.

### What it is

A library providing ephemeral, resource-limited, audited execution environments
for AI agent shell tool calls. Snapshot/restore is the key primitive — before any
destructive command, take a snapshot; if the result is wrong, roll back.

### API sketch

```python
from sandboxkit import Sandbox, ExecutionPolicy

policy = ExecutionPolicy(
    network=False,
    max_memory_mb=512,
    max_cpu_pct=50,
    allowed_paths=["/project", "/tmp"],
    blocked_paths=["/etc", "/root", "~/.ssh"],
    timeout_sec=30,
    allow_installs=False,       # block pip install / npm install
)

with Sandbox(project_root="/my/project", policy=policy) as box:
    result = box.run("pytest tests/ -x -q")
    # result.stdout, result.stderr, result.exit_code, result.duration_ms
    # result.file_changes: list of files created / modified / deleted
    # result.network_calls: blocked (policy.network=False)

    snapshot = box.snapshot()
    box.run("rm -rf build/")
    box.restore(snapshot)       # build/ is back
```

### MCP surface

```
Tools:
  create_sandbox(policy) → sandbox_id
  run_in_sandbox(sandbox_id, command) → ExecutionResult
  snapshot_sandbox(sandbox_id) → snapshot_id
  restore_sandbox(sandbox_id, snapshot_id)
  get_file_changes(sandbox_id) → files changed since last snapshot
  destroy_sandbox(sandbox_id)
```

### Who else uses it

- Any AI agent that runs shell commands
- CI systems where AI proposes and runs commands before human review
- Pair-programming tools where agent shell access should be scoped
- DevAgent: `run_shell` uses SandboxKit as its backend when sandbox mode is on

### Differentiation

Docker: heavyweight, not designed for per-tool-call granularity.
Firejail: Linux-only, complex configuration.
SandboxKit: Python-first, designed around the snapshot/restore pattern,
native MCP interface, targets macOS + Linux.

### Priority

Later / bigger scope — platform complexity is real (macOS and Linux sandboxing
are different beasts). More of a v0.8+ thing after the core agent features are solid.

---

## Library 4: DocPrism

**Tagline:** AI-optimized documentation — dense, structured, fact-first.

### The problem

Documentation is written for humans. Human docs include narrative, examples,
warnings, and context that cost tokens without adding signal when fed to an LLM.
A 3000-token docstring could be 200 tokens of structured facts that the LLM
actually uses. There is no tooling to bridge this gap.

### What it is

A library that generates AI-optimized documentation for a codebase — a parallel
layer alongside human docs, built for LLM consumption. Not a replacement for human
docs — a different format for a different audience.

### Output example

```
# Human docstring for LLMClient.complete_with_tools:
# 800 tokens of narrative, examples, warnings, history

# DocPrism output for the same symbol:
# complete_with_tools(messages, tools) → LLMResponse
# REQUIRES: messages[-1].role == "user"
# MODIFIES: nothing (pure function)
# RAISES: LLMError if provider unreachable; BudgetExceeded if over limit
# KEY BEHAVIOUR: if response.has_tool_calls → caller must loop; else turn is done
# COST: 1 API call; tokens_in ≈ sum(len(m.content) for m in messages) / 4
# TESTS: tests/test_llm.py::test_complete_with_tools_*
# CALLERS: agent/loop.py:192, agent/flows.py:87
# → 45 tokens (vs 800 in human docstring)
```

### How it generates

Combines:
- AST analysis: types, signatures, raises clauses
- CodePrism call graph: callers, tests, dependencies
- One-shot LLM call: extracts key behaviours from existing docstring + implementation

Not hallucinating — extracting and compressing what's already there.

### MCP surface

```
Resources:
  docprism://{file}/{symbol}    → AI-optimized doc for a symbol
  docprism://{file}             → AI-optimized module summary

Tools:
  generate_docs(file_path) → generate/update AI docs for a file
  get_symbol_doc(file_path, symbol_name) → fetch cached AI doc
  get_module_doc(file_path) → cached module-level AI doc
  invalidate_docs(file_path) → mark stale after a file changes
```

### Who else uses it

- Claude Desktop: connects to DocPrism MCP, gets AI-optimized docs for every symbol
- Cursor: configure as a context source for code navigation
- CI: run `docprism generate` on every merge to keep AI docs current
- DevAgent: replaces raw docstring injection with DocPrism-compressed versions

### Differentiation

Mintlify / ReadTheDocs: generate human-readable docs.
GitHub Copilot doc suggestions: one-off, not persistent.
DocPrism: persistent, queryable, incrementally updated, AI-consumption-optimised.

### Priority

Medium term. More powerful once paired with CodePrism's symbol graph.

---

## Library 5: SpecToTest

**Tagline:** Convert specs and requirements into runnable test suites before writing a line of code.

### The problem

AI agents write code first and tests for the code they wrote — backwards.
TDD says tests come first. But writing tests from a spec (GitHub issue, PRD,
user story) requires understanding requirements as assertions, which is different
from understanding code. No tool does this today.

### What it is

A library that converts natural language requirements into runnable test skeletons.
Tests express the spec's intent as assertions. The agent then implements code to
make them pass — true spec-driven TDD.

### API sketch

```python
from spectotest import SpecConverter

spec = """
The login endpoint should:
- Accept POST /auth/login with {email, password}
- Return 200 with a JWT token if credentials are valid
- Return 401 if credentials are invalid
- Return 422 if email format is invalid
- Rate limit to 5 attempts per IP per minute
- Lock account after 10 consecutive failures
"""

converter = SpecConverter(framework="pytest", target_language="python")
test_file = converter.convert(spec, output_path="tests/test_login.py")
```

Generated `tests/test_login.py`:

```python
class TestLoginEndpoint:

    def test_returns_jwt_on_valid_credentials(self, client):
        resp = client.post("/auth/login", json={"email": "a@b.com", "password": "correct"})
        assert resp.status_code == 200
        assert "token" in resp.json()

    def test_returns_401_on_invalid_credentials(self, client):
        resp = client.post("/auth/login", json={"email": "a@b.com", "password": "wrong"})
        assert resp.status_code == 401

    def test_returns_422_on_invalid_email_format(self, client):
        resp = client.post("/auth/login", json={"email": "not-an-email", "password": "x"})
        assert resp.status_code == 422

    def test_rate_limits_to_5_attempts_per_minute(self, client):
        # SPEC: 5 attempts per IP per minute
        ...  # TODO: implement

    def test_locks_account_after_10_consecutive_failures(self, client):
        # SPEC: lock after 10 consecutive failures
        ...  # TODO: implement
```

`# TODO: implement` markers are intentional — some assertions require setup that
only the implementation knows. The agent fills these in as it builds the feature.

### MCP surface

```
Tools:
  convert_spec_to_tests(spec_text, framework, language) → test file content
  extract_assertions(spec_text) → list of assertion statements
  verify_spec_coverage(spec_text, test_file) → which requirements lack tests
  update_tests_from_spec(spec_text, existing_test_file) → add missing tests
```

### Who else uses it

- Product managers who write specs and want immediate test validation
- DevAgent `implement` flow: call SpecToTest on the GitHub issue body before writing
  any code → generate tests → implement against them
- Any TDD workflow where requirements live in natural language

### Differentiation

GitHub Copilot: generates tests from code (wrong direction).
Testing frameworks (pytest, jest): require you to write tests yourself.
SpecToTest: bridges natural language requirements → executable tests.
No existing tool does this.

### Priority

**Highest ROI — build soonest alongside ChangePropagator.** Straightforward LLM
wrapper with structured output. High visibility because it fits directly into
DevAgent's `implement` flow. Nobody else is building this.

---

## Library 6: RepoAudit

**Tagline:** Repository AI-readiness scoring with actionable remediation tasks.

### The problem

Some repos are easy for AI agents to work with; others are a nightmare. The
difference is structural: good naming, strong typing, clear module boundaries,
comprehensive tests. There is no tool that measures AI-readiness and gives specific
fixes to improve it.

### What it is

A library that audits a repository across dimensions that matter for AI agent
effectiveness and produces a score with a ranked remediation plan.

### Dimensions scored

```
Naming clarity         — do identifiers communicate their purpose?
Type annotation        — % of public functions with type hints
Docstring coverage     — % of public symbols with docstrings
Module cohesion        — are modules focused (one responsibility)?
Test coverage          — % of code with corresponding test files
Dependency depth       — import hops to reach any symbol
Circular dependencies  — cycles in the import graph
Dead code              — unreferenced symbols that confuse agents
Naming consistency     — snake_case vs camelCase mixing, abbreviations
```

### Output example

```
RepoAudit Score: 67/100

Critical (fix these first):
  ✗ 23 public functions have no type hints
  ✗ 8 circular import cycles detected
  ✗ 4 modules over 600 lines (low cohesion)

High (fix before agent tasks):
  ✗ 41% of public functions lack docstrings
  ✗ 12 files with no corresponding test file
  ✗ 17 dead symbols never referenced outside their file

Medium:
  ✗ Mixed naming conventions in src/api/ (camelCase + snake_case)
  ✗ 5 abbreviations in module names (mgr, proc, util, hlpr, svc)

Estimated agent effectiveness: LOW — expect high token waste on context-gathering
Recommended first action: devagent do "add type hints to all public functions in src/"
```

### MCP surface

```
Resources:
  repoaudit://score             → overall score and breakdown
  repoaudit://issues            → full issue list sorted by impact
  repoaudit://issues/{category} → issues in a specific category

Tools:
  run_audit(project_root) → AuditReport
  get_score(project_root) → int 0-100
  get_remediation_plan(project_root) → ordered list of fix tasks
  watch_score(project_root) → stream score updates as files change
```

### Who else uses it

- Teams evaluating a repo before onboarding an AI agent
- DevAgent's `onboard` command: call RepoAudit to surface what might trip the agent
- CI pipelines: track AI-readiness over time as a metric alongside test coverage

### Differentiation

Linters (ruff, eslint): check errors and style.
Complexity tools (radon, wily): check cyclomatic complexity.
RepoAudit: measures AI agent effectiveness specifically — a different lens that
correlates with but is not identical to human readability metrics.

### Priority

Later — useful but more of a nice-to-have. Linters already cover much of the signal.
Good v0.7+ addition once the core agent features are solid.

---

## How these fit together as an ecosystem

```
CodePrism         — what the codebase IS (structure, symbols, call graph)
MemoryPrism       — what the conversation WAS (compressed history)  [roadmap]
DocPrism          — what the code MEANS in AI-optimal format
ChangePropagator  — what a change AFFECTS across callers
SpecToTest        — what the spec REQUIRES as runnable assertions
RepoAudit         — how AI-READY the codebase is
SandboxKit        — where agent shell commands RUN safely
AgentTrace        — what the agent DID and why
```

Each is independently useful, each exposes an MCP server, and they compose.
A DevAgent session with all of them connected: the agent checks RepoAudit before
starting, uses DocPrism for symbol docs, generates tests via SpecToTest, runs
commands in SandboxKit, cascades changes via ChangePropagator, and the whole
session is captured in AgentTrace for debugging.

---

## Build order recommendation

**Build now (alongside Phase 7):**
- ChangePropagator — CodePrism call graph already exists, natural next layer; immediately useful in DevAgent's refactoring flows
- SpecToTest — straightforward LLM wrapper; fits directly into `implement` flow; no one else building this

**Medium term (alongside Phase 8–9):**
- AgentTrace — becomes critical once multi-agent orchestration exists
- DocPrism — needs CodePrism integration; more powerful as the graph matures

**Later / bigger scope:**
- SandboxKit — platform complexity (macOS + Linux sandboxing differ); v0.8+
- RepoAudit — useful, linters already cover much of it; v0.7+
