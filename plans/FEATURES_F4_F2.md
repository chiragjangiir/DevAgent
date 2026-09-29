# DevAgent — Feature Implementation Guide: F4 (URL Input) + F2 (Chat Interface)

> **For the AI code editor reading this file:**
> This document describes two features to be added to an already working DevAgent codebase that has completed Phases 1–6 as described in `PROJECT.md`. Read `PROJECT.md` first to understand the existing architecture, directory structure, and conventions. This file describes only what is NEW or CHANGED. Do not rewrite existing working code unless this document explicitly says to modify a specific file. Build F4 first — it is a prerequisite for F2's `--url` flag. Then build F2.

---

## Context — What Already Exists

Before implementing anything, understand what the codebase already has:

- `devagent/cli.py` — Typer CLI with all commands. The `analyze` command already accepts `--issue`, `--spec`, `--text`, `--output`, `--repo` flags.
- `devagent/agents/pipeline.py` — `run_pipeline()` function that runs all three agents and returns a `GapReport`
- `devagent/core/models.py` — all Pydantic models including `GapReport`, `PipelineState`, `Requirement`, `RequirementAnalysis`
- `devagent/core/config.py` — `load_config()`, `DevAgentConfig`
- `devagent/core/llm.py` — `get_llm()` provider factory
- `devagent/mcp/manager.py` — `MCPManager` async context manager that launches all 5 MCP servers
- `devagent/output/terminal.py` — `render_gap_report(report: GapReport)` renders Rich output to terminal
- `devagent/output/markdown.py` — `save_gap_report(report: GapReport, path: Path)` saves markdown file

The current `analyze` command flow is:
1. Parse flags → determine spec source
2. Open MCPManager
3. Call `run_pipeline()`
4. Call `render_gap_report()`
5. Call `save_gap_report()`
6. Close MCPManager → exit

F4 adds a `--url` flag to this existing command.
F2 adds a `--chat` flag that keeps the process alive after step 5 and drops into an interactive session.

---

## FEATURE F4 — Direct GitHub URL Input

### What it does

A developer can now pass a full GitHub issue or PR URL directly instead of specifying `--issue` and `--repo` separately:

```
# Before F4 (still works after F4):
devagent analyze --issue 142 --repo myorg/backend

# After F4:
devagent analyze --url https://github.com/myorg/backend/issues/142
devagent analyze --url https://github.com/myorg/backend/pull/87
```

DevAgent parses the URL, extracts the owner, repo name, and issue/PR number, and proceeds identically to how it would with `--issue` and `--repo` specified manually.

### Why it matters

Developers share GitHub URLs constantly — in Slack, in emails, in Notion docs. The current flow requires them to mentally extract the issue number and repo name and type them separately. With `--url`, they copy-paste the URL directly. This is the natural interaction pattern.

### Exact scope — what F4 touches

F4 is intentionally minimal. It touches exactly three things:

1. `devagent/cli.py` — add `--url` option to the `analyze` command
2. `devagent/core/url_parser.py` — new file, URL parsing logic
3. `tests/test_url_parser.py` — new file, tests for URL parsing

Nothing else changes. The pipeline, the agents, the MCP servers, the output — all unchanged.

---

### Implementation — `devagent/core/url_parser.py`

Create this file. It is a pure utility module with no dependencies on the rest of DevAgent. It has no side effects. It does not make network calls.

```
devagent/
  core/
    url_parser.py    ← NEW FILE
```

Implement the following:

**`ParsedGitHubURL` dataclass:**

```python
from dataclasses import dataclass
from typing import Literal

@dataclass
class ParsedGitHubURL:
    owner: str                          # e.g. "myorg"
    repo: str                           # e.g. "backend"
    number: int                         # issue or PR number
    resource_type: Literal["issue", "pull_request"]
    raw_url: str                        # the original URL as provided
```

**`parse_github_url(url: str) -> ParsedGitHubURL` function:**

This function takes a raw URL string and returns a `ParsedGitHubURL`. It raises `InvalidGitHubURLError` (define this as a custom exception in the same file) if the URL cannot be parsed.

URL patterns to handle — all of these must work:

```
# Standard issue URL
https://github.com/owner/repo/issues/142

# Standard PR URL
https://github.com/owner/repo/pull/87

# With trailing slash
https://github.com/owner/repo/issues/142/

# With query parameters (GitHub sometimes adds these)
https://github.com/owner/repo/issues/142?notification_referrer_id=abc

# With fragment
https://github.com/owner/repo/issues/142#issuecomment-123456

# Without https (user pasted without protocol)
github.com/owner/repo/issues/142

# Short form — not supported, raise clear error
owner/repo#142   → raise InvalidGitHubURLError("Use the full GitHub URL")
142              → raise InvalidGitHubURLError("Use the full GitHub URL")
```

Implementation approach — use `urllib.parse.urlparse` from the standard library. Do not use regex as the primary approach — it is brittle for URLs. Use `urlparse` to get the path component, then split the path.

Pseudocode:
```
1. If URL does not start with "http", prepend "https://"
2. urlparse the URL to get scheme, netloc, path
3. Validate netloc is "github.com" — raise InvalidGitHubURLError if not
4. Split path by "/" — filter empty strings
   Result for "/owner/repo/issues/142" → ["owner", "repo", "issues", "142"]
5. Validate length is exactly 4
6. Extract: owner=parts[0], repo=parts[1], resource_type_str=parts[2], number_str=parts[3]
7. Validate resource_type_str is "issues" or "pull" — raise InvalidGitHubURLError if not
8. Validate number_str is a valid integer — raise InvalidGitHubURLError if not
9. Map: "issues" → "issue", "pull" → "pull_request"
10. Return ParsedGitHubURL(owner, repo, int(number_str), resource_type, url)
```

**`InvalidGitHubURLError` exception:**

```python
class InvalidGitHubURLError(Exception):
    def __init__(self, url: str, reason: str):
        self.url = url
        self.reason = reason
        super().__init__(f"Cannot parse GitHub URL '{url}': {reason}")
```

**`format_repo_string(parsed: ParsedGitHubURL) -> str` function:**

Simple helper. Returns `"owner/repo"` formatted string. Used to set `github_repo` in PipelineState.

```python
def format_repo_string(parsed: ParsedGitHubURL) -> str:
    return f"{parsed.owner}/{parsed.repo}"
```

---

### Implementation — changes to `devagent/cli.py`

Find the `analyze` command function. Add one new optional parameter:

```python
url: Annotated[Optional[str], typer.Option("--url", help="Full GitHub issue or PR URL")] = None,
```

The full parameter list for `analyze` after F4:

```python
@app.command()
def analyze(
    issue: Annotated[Optional[int], typer.Option("--issue", "-i", help="GitHub issue number")] = None,
    spec: Annotated[Optional[Path], typer.Option("--spec", "-s", help="Path to spec markdown file")] = None,
    text: Annotated[Optional[str], typer.Option("--text", "-t", help="Inline spec text")] = None,
    url: Annotated[Optional[str], typer.Option("--url", "-u", help="Full GitHub issue or PR URL")] = None,
    output: Annotated[str, typer.Option("--output", "-o", help="Output format: terminal, markdown, both, json")] = "both",
    repo: Annotated[Optional[str], typer.Option("--repo", "-r", help="GitHub repo as owner/repo")] = None,
    chat: Annotated[bool, typer.Option("--chat", "-c", help="Drop into chat session after analysis")] = False,
):
```

Note: `--chat` is added here too even though it is F2. Add both flags at the same time so the signature is complete.

**Validation logic at the top of the `analyze` function** — add this block after the existing validation:

```python
# F4: Handle --url flag
if url is not None:
    # Cannot combine --url with --issue, --repo
    if issue is not None:
        console.print("[red]Cannot use --url together with --issue. Use one or the other.[/red]")
        raise typer.Exit(1)
    if repo is not None:
        console.print("[red]Cannot use --url together with --repo. Use one or the other.[/red]")
        raise typer.Exit(1)

    # Parse the URL
    try:
        parsed_url = parse_github_url(url)
    except InvalidGitHubURLError as e:
        console.print(f"[red]Invalid GitHub URL:[/red] {e.reason}")
        console.print(f"[dim]Expected format: https://github.com/owner/repo/issues/NUMBER[/dim]")
        raise typer.Exit(1)

    # Set issue and repo from parsed URL
    issue = parsed_url.number
    repo = format_repo_string(parsed_url)

    # If it's a PR URL, show a note
    if parsed_url.resource_type == "pull_request":
        console.print(
            f"[dim]Note: Analyzing PR #{parsed_url.number} as a spec — "
            f"extracting intent from PR description and title.[/dim]"
        )
```

After this block, the rest of the `analyze` function runs exactly as before — `issue` and `repo` are now populated from the URL, and the existing logic handles them identically to when they were passed directly.

**Import to add at the top of `cli.py`:**

```python
from devagent.core.url_parser import parse_github_url, format_repo_string, InvalidGitHubURLError
```

---

### PR URL handling — what changes in the pipeline

When a PR URL is provided, `resource_type` is `"pull_request"`. The GitHub MCP's `get_issue` tool does not fetch PRs — GitHub PRs use a different API endpoint. Add handling in `devagent/mcp/clients/github_client.py`:

Add a new method alongside the existing `get_issue` method:

```python
async def get_pull_request(self, owner: str, repo: str, pr_number: int) -> dict:
    """Fetches PR title, body, and changed files for spec analysis."""
    result = await self.mcp_client.call_tool(
        "get_pull_request",
        {"owner": owner, "repo": repo, "pullNumber": pr_number}
    )
    return result
```

In `devagent/agents/spec_parser.py`, in the `fetch_spec` node, check `state.resource_type`:
- If `"issue"` → call `github_client.get_issue()` as before
- If `"pull_request"` → call `github_client.get_pull_request()`. The PR body becomes the spec text. The PR title is prepended as context: `f"PR Title: {pr['title']}\n\nDescription:\n{pr['body']}"`.

Add `resource_type: str = "issue"` to `PipelineState` in `devagent/core/models.py`. Default to `"issue"` so existing code paths are unaffected.

---

### Tests — `tests/test_url_parser.py`

Create this file. Write tests for every case described in the URL patterns section. Use `pytest`. No mocking needed — `parse_github_url` is a pure function.

Test cases to cover:

```python
def test_standard_issue_url():
    result = parse_github_url("https://github.com/myorg/backend/issues/142")
    assert result.owner == "myorg"
    assert result.repo == "backend"
    assert result.number == 142
    assert result.resource_type == "issue"

def test_pr_url():
    result = parse_github_url("https://github.com/myorg/backend/pull/87")
    assert result.resource_type == "pull_request"
    assert result.number == 87

def test_trailing_slash():
    result = parse_github_url("https://github.com/myorg/backend/issues/142/")
    assert result.number == 142

def test_url_with_query_params():
    result = parse_github_url("https://github.com/myorg/backend/issues/142?notification_referrer_id=abc")
    assert result.number == 142

def test_url_with_fragment():
    result = parse_github_url("https://github.com/myorg/backend/issues/142#issuecomment-123456")
    assert result.number == 142

def test_without_https():
    result = parse_github_url("github.com/myorg/backend/issues/142")
    assert result.owner == "myorg"
    assert result.number == 142

def test_non_github_url_raises():
    with pytest.raises(InvalidGitHubURLError):
        parse_github_url("https://gitlab.com/myorg/backend/issues/142")

def test_short_form_raises():
    with pytest.raises(InvalidGitHubURLError):
        parse_github_url("myorg/backend#142")

def test_invalid_number_raises():
    with pytest.raises(InvalidGitHubURLError):
        parse_github_url("https://github.com/myorg/backend/issues/abc")

def test_format_repo_string():
    parsed = parse_github_url("https://github.com/myorg/backend/issues/142")
    assert format_repo_string(parsed) == "myorg/backend"
```

---

### F4 Verification

F4 is complete when all of the following work:

```
devagent analyze --url https://github.com/owner/repo/issues/142
```
Produces the same output as:
```
devagent analyze --issue 142 --repo owner/repo
```

```
devagent analyze --url https://github.com/owner/repo/pull/87
```
Shows the PR note and produces a gap report from the PR description.

```
devagent analyze --url not-a-url
```
Shows a friendly error panel, not a Python traceback.

```
devagent analyze --url https://github.com/owner/repo/issues/142 --issue 142
```
Shows "Cannot use --url together with --issue" error.

All tests in `test_url_parser.py` pass.

---

---

## FEATURE F2 — Chat Terminal Interface

### What it does

After `devagent analyze` completes and the gap report is displayed, instead of exiting, the `--chat` flag keeps the process alive and drops the developer into an interactive terminal session. They can ask questions about the gap report in plain English:

```
devagent analyze --issue 142 --chat
devagent analyze --url https://github.com/myorg/backend/issues/142 --chat
```

After the gap report renders, the terminal shows:

```
─────────────────────────────────────────────────────
  DevAgent Chat  ·  Ask anything about this analysis
  Type 'exit' or press Ctrl+C to quit
─────────────────────────────────────────────────────

  You ❯
```

The developer types questions. DevAgent responds. The conversation continues until they type `exit` or press Ctrl+C.

They can also start a chat session against a previously saved report without re-running the analysis:

```
devagent chat --report issue-142-2025-01-15-143022
devagent chat                                         # lists available reports to choose from
```

### What the chat session knows

The chat session has access to the full `GapReport` object as its context. Every message the developer sends is answered with knowledge of:

- Every requirement that was extracted from the spec
- The status of each requirement (REUSE / EXTEND / CONFLICT / NET_NEW)
- The specific files matched for each requirement
- The conflict details — which files are affected, severity, explanation
- The edge cases inferred from the spec
- The effort estimate and implementation order
- The project name and spec source

The chat does NOT have access to the actual source files — it reasons about the gap report, not the raw codebase. This is intentional and important: it keeps the chat fast (no MCP server calls during conversation), consistent (answers are grounded in the structured report), and predictable.

### What kinds of questions it answers well

Design the system prompt so the chat handles these question types naturally:

**Clarification questions:**
- "Why is session.py marked as a conflict?"
- "What does PARTIALLY_EXISTS mean for REQ-2?"
- "Explain the conflict in auth/routes.py in plain English"

**Planning questions:**
- "Where should I start?"
- "Which conflict is most dangerous to leave unresolved?"
- "Can I skip the conflict resolution and do it later?"
- "How long will the net new work take?"

**Trade-off questions:**
- "What happens if I just ignore the edge cases?"
- "Is the effort estimate realistic?"
- "Which requirement is the highest risk?"

**Structural questions:**
- "Which files will I definitely need to touch?"
- "Are any of the conflicts related to each other?"
- "What should I tell the PM before I start coding?"

**Questions the chat should decline gracefully:**
- "Write the code for me" → "I can help you understand what to build, but I don't write code. Use the gap report as your plan."
- "Search the codebase for X" → "I don't have access to the raw codebase in chat mode. Run `devagent search X` in a separate terminal."
- Anything unrelated to the gap report → "I'm focused on this gap analysis. For general questions, use your preferred AI assistant."

---

### New files created by F2

```
devagent/
  chat/
    __init__.py
    session.py          ← ChatSession class — the core chat loop
    context.py          ← builds the system prompt from a GapReport
    history.py          ← manages conversation history with context window trimming
  output/
    chat_renderer.py    ← Rich rendering for chat UI (input prompt, responses, borders)
```

Changes to existing files:

```
devagent/cli.py              ← add --chat flag to analyze, add `chat` command
tests/test_chat_context.py   ← new test file
```

---

### Implementation — `devagent/chat/context.py`

This module builds the system prompt that grounds the LLM in the gap report. This is the most important part of F2 — a well-constructed system prompt is what makes the chat actually useful rather than generic.

**`build_system_prompt(report: GapReport, project_name: str) -> str` function:**

This function takes the `GapReport` object and serializes it into a structured natural language document that becomes the LLM's system prompt. It is called once when the chat session starts and remains constant for the entire conversation.

The system prompt has three sections:

**Section 1 — Role and constraints:**

```
You are DevAgent Chat, an assistant that helps developers understand and plan
implementation work based on a codebase gap analysis.

You have been given a complete gap analysis report for a specific GitHub issue
or specification. Your job is to answer questions about this analysis: explain
findings, help prioritize work, surface risks, and assist with planning.

Strict rules you must follow:
- Only answer questions about this specific gap analysis. Do not answer general
  coding questions, write code, or discuss topics unrelated to this report.
- If asked to write code, say: "I help with planning and understanding, not
  writing code. Use the gap report as your implementation guide."
- If asked about something not in the report, say so clearly rather than
  guessing or making something up.
- Base every answer on the specific data in the report below. Name specific
  files, functions, and requirements when relevant.
- Keep answers concise but complete. Use bullet points for lists of items.
  Do not pad answers.
```

**Section 2 — The gap report as structured text:**

Serialize the entire `GapReport` into a readable structured format. This is NOT the raw JSON — it is a human-readable rendering that the LLM can reason over easily.

Format it as follows:

```
PROJECT: {project_name}
SPEC SOURCE: {report.spec_source}
ANALYZED AT: {report.generated_at}
TOTAL REQUIREMENTS: {total count}

━━━ REQUIREMENTS AND STATUS ━━━

[REQ-1] {requirement.description}
  Type: {requirement.requirement_type}
  Priority: {requirement.priority}
  Status: {analysis.status}
  {if FULLY_EXISTS or PARTIALLY_EXISTS:}
    Matched in: {matched_files joined by ", "}
    Matched functions: {matched_functions joined by ", "}
  {if CONFLICTED:}
    Conflict severity: {conflict_details.conflict_severity}
    Affected files ({count}): {affected_files joined by ", "}
    Conflict explanation: {conflict_details.explanation}
  Classification reason: {analysis.classification_reason}

[REQ-2] ...

━━━ EDGE CASES ━━━

{for each edge_case:}
- {edge_case.description} [{edge_case.severity}]
  Related to: REQ-{edge_case.related_requirement_id}

━━━ DATA MODEL CHANGES ━━━

{for each data_model:}
- {data_model description}

━━━ API CHANGES ━━━

{for each api_change:}
- {api_change description}

━━━ IMPLEMENTATION ORDER ━━━

{implementation_order as numbered list}

━━━ EFFORT ESTIMATE ━━━

Conflict resolution: {conflict_resolution_hours}h
Extensions: {extension_hours}h
Net new work: {net_new_hours}h
Testing: {testing_hours}h
Total: {total_days} days (confidence: {confidence})
Notes: {notes}
```

The total system prompt length will typically be 1,500–3,000 tokens depending on the number of requirements. This is well within the context window of any supported LLM.

**`estimate_prompt_tokens(text: str) -> int` utility function:**

Rough token estimator — `len(text) // 4`. Used by the history manager to stay within context limits.

---

### Implementation — `devagent/chat/history.py`

Manages the conversation history. The history is an in-memory list of message dictionaries — it is not persisted to disk. If the user exits and re-enters chat, history resets. This is intentional for v0.1 of the feature.

```python
from dataclasses import dataclass, field
from typing import Literal

@dataclass
class Message:
    role: Literal["user", "assistant"]
    content: str

class ConversationHistory:
    def __init__(self, system_prompt: str, max_tokens: int = 6000):
        self.system_prompt = system_prompt
        self.max_tokens = max_tokens
        self.messages: list[Message] = []
        self._system_tokens = estimate_prompt_tokens(system_prompt)

    def add_user_message(self, content: str) -> None:
        self.messages.append(Message(role="user", content=content))
        self._trim_if_needed()

    def add_assistant_message(self, content: str) -> None:
        self.messages.append(Message(role="assistant", content=content))

    def to_langchain_messages(self) -> list:
        """Returns messages in LangChain format for LLM invocation."""
        from langchain_core.messages import SystemMessage, HumanMessage, AIMessage
        result = [SystemMessage(content=self.system_prompt)]
        for msg in self.messages:
            if msg.role == "user":
                result.append(HumanMessage(content=msg.content))
            else:
                result.append(AIMessage(content=msg.content))
        return result

    def _trim_if_needed(self) -> None:
        """
        If total estimated tokens exceed max_tokens, remove the oldest
        user+assistant message pair from the history. Keeps the system
        prompt intact always. Never removes the most recent user message.
        """
        while self._total_tokens() > self.max_tokens and len(self.messages) > 1:
            # Remove oldest pair (user + assistant)
            if len(self.messages) >= 2:
                self.messages.pop(0)  # remove oldest user
                if self.messages and self.messages[0].role == "assistant":
                    self.messages.pop(0)  # remove its response
            else:
                break

    def _total_tokens(self) -> int:
        msg_tokens = sum(estimate_prompt_tokens(m.content) for m in self.messages)
        return self._system_tokens + msg_tokens

    @property
    def message_count(self) -> int:
        return len(self.messages)
```

**Why trimming matters:** The system prompt is ~2,000 tokens. The LLM context window for Ollama small models is typically 4,096–8,192 tokens. After several exchanges, the history will exceed the window. Trimming the oldest pairs keeps the conversation functional without crashing. The system prompt is never trimmed — the gap report context is always present.

---

### Implementation — `devagent/chat/session.py`

This is the core chat loop. It handles input, LLM calls, output, and special commands.

```python
import asyncio
from rich.console import Console
from rich.panel import Panel
from rich.markdown import Markdown
from devagent.chat.history import ConversationHistory
from devagent.chat.context import build_system_prompt
from devagent.core.models import GapReport
from devagent.core.config import DevAgentConfig
from devagent.core.llm import get_llm

console = Console()

class ChatSession:
    def __init__(self, report: GapReport, config: DevAgentConfig, project_name: str):
        self.report = report
        self.config = config
        self.project_name = project_name
        self.llm = get_llm(config)
        system_prompt = build_system_prompt(report, project_name)
        self.history = ConversationHistory(system_prompt, max_tokens=6000)

    async def run(self) -> None:
        """Main chat loop. Runs until user exits."""
        self._print_welcome()

        while True:
            try:
                user_input = await self._get_input()
            except (KeyboardInterrupt, EOFError):
                self._print_goodbye()
                break

            if not user_input.strip():
                continue

            # Handle special commands
            command_handled = self._handle_special_command(user_input.strip().lower())
            if command_handled == "exit":
                self._print_goodbye()
                break
            if command_handled:
                continue

            # Normal message — get LLM response
            self.history.add_user_message(user_input)

            with console.status("[dim]Thinking...[/dim]", spinner="dots"):
                try:
                    response = await self._get_llm_response()
                except Exception as e:
                    console.print(f"[red]Error getting response:[/red] {e}")
                    # Remove the user message we just added since we have no response
                    self.history.messages.pop()
                    continue

            self.history.add_assistant_message(response)
            self._print_response(response)

    async def _get_input(self) -> str:
        """Gets user input. Uses asyncio.get_event_loop().run_in_executor
        to avoid blocking the event loop."""
        loop = asyncio.get_event_loop()
        console.print()
        console.print("[bold cyan]  You ❯[/bold cyan] ", end="")
        return await loop.run_in_executor(None, input)

    async def _get_llm_response(self) -> str:
        """Calls the LLM with the full conversation history."""
        messages = self.history.to_langchain_messages()
        loop = asyncio.get_event_loop()
        # Run LLM call in executor to avoid blocking
        response = await loop.run_in_executor(
            None,
            lambda: self.llm.invoke(messages)
        )
        return response.content

    def _handle_special_command(self, command: str) -> str | bool:
        """
        Handles built-in chat commands.
        Returns "exit" to signal exit, True if handled, False if not a command.
        """
        if command in ("exit", "quit", "q", ":q", "bye"):
            return "exit"

        if command in ("help", "?"):
            self._print_help()
            return True

        if command in ("summary", "/summary"):
            self._print_report_summary()
            return True

        if command in ("conflicts", "/conflicts"):
            self._print_conflicts()
            return True

        if command in ("order", "/order"):
            self._print_implementation_order()
            return True

        if command in ("estimate", "/estimate"):
            self._print_effort_estimate()
            return True

        if command in ("clear", "/clear"):
            self.history.messages.clear()
            console.print("[dim]Conversation history cleared.[/dim]")
            return True

        return False

    def _print_welcome(self) -> None:
        console.print()
        console.print(Panel(
            "[bold]DevAgent Chat[/bold]  ·  Ask anything about this analysis\n"
            "[dim]Commands: /summary  /conflicts  /order  /estimate  /clear  exit[/dim]",
            border_style="cyan",
            padding=(0, 2)
        ))

    def _print_response(self, response: str) -> None:
        console.print()
        console.print(Panel(
            Markdown(response),
            border_style="dim",
            title="[dim]DevAgent[/dim]",
            title_align="left",
            padding=(1, 2)
        ))

    def _print_goodbye(self) -> None:
        console.print()
        console.print("[dim]Chat session ended.[/dim]")
        console.print()

    def _print_help(self) -> None:
        from rich.table import Table
        table = Table(show_header=False, box=None, padding=(0, 2))
        table.add_row("[cyan]/summary[/cyan]", "Show the full gap report summary")
        table.add_row("[cyan]/conflicts[/cyan]", "List all conflicts and affected files")
        table.add_row("[cyan]/order[/cyan]", "Show recommended implementation order")
        table.add_row("[cyan]/estimate[/cyan]", "Show effort estimate breakdown")
        table.add_row("[cyan]/clear[/cyan]", "Clear conversation history")
        table.add_row("[cyan]exit[/cyan]", "End the chat session")
        console.print(Panel(table, title="[dim]Available Commands[/dim]", border_style="dim"))

    def _print_report_summary(self) -> None:
        """Re-renders a compact version of the gap report."""
        from devagent.output.terminal import render_gap_report_compact
        render_gap_report_compact(self.report)

    def _print_conflicts(self) -> None:
        """Shows just the conflicts section."""
        from devagent.output.terminal import render_conflicts_only
        render_conflicts_only(self.report)

    def _print_implementation_order(self) -> None:
        for i, step in enumerate(self.report.implementation_order, 1):
            console.print(f"  [dim]{i}.[/dim] {step}")

    def _print_effort_estimate(self) -> None:
        e = self.report.effort_estimate
        from rich.table import Table
        table = Table(show_header=False, box=None, padding=(0, 2))
        table.add_row("Conflict resolution", f"{e.conflict_resolution_hours}h")
        table.add_row("Extensions", f"{e.extension_hours}h")
        table.add_row("Net new work", f"{e.net_new_hours}h")
        table.add_row("Testing", f"{e.testing_hours}h")
        table.add_row("[bold]Total[/bold]", f"[bold]{e.total_days} days[/bold]")
        table.add_row("Confidence", e.confidence)
        console.print(Panel(table, title="[dim]Effort Estimate[/dim]", border_style="dim"))
```

---

### Implementation — `devagent/output/chat_renderer.py`

This module is intentionally thin. Most rendering is done inside `ChatSession` using Rich directly. This module holds the two helper functions that `ChatSession` calls from `devagent/output/terminal.py`:

**`render_gap_report_compact(report: GapReport) -> None`:**

A condensed version of the full gap report — same information but in a more compact layout suitable for re-displaying inside a chat session. The full render is shown once at the start. This compact version is for `/summary` in the chat.

Show:
- Requirement count by status (a one-line summary: "4 requirements: 1 reuse · 1 extend · 1 conflict · 1 net new")
- A simple table: Requirement ID | Status | File(s) matched
- Edge cases as a bullet list
- One-line effort summary

**`render_conflicts_only(report: GapReport) -> None`:**

Shows only the CONFLICTED requirements with full detail — affected files, severity, explanation. Used for the `/conflicts` command.

Add both functions to `devagent/output/terminal.py` (not a new file — add to the existing terminal output module).

---

### Implementation — `devagent/chat/__init__.py`

```python
from devagent.chat.session import ChatSession

__all__ = ["ChatSession"]
```

---

### Implementation — changes to `devagent/cli.py` for F2

**Change 1 — Add `--chat` flag to `analyze` command:**

Already shown in the F4 section above. The flag is already listed in the parameter signature. Now implement its behavior.

At the end of the `analyze` command function, after the gap report has been rendered and the markdown file saved, add:

```python
# F2: Drop into chat if --chat flag was provided
if chat:
    # MCP servers are still running inside the MCPManager context
    # Create and run the chat session
    chat_session = ChatSession(
        report=gap_report,
        config=config,
        project_name=detected_project_name  # already computed earlier in analyze
    )
    asyncio.run(chat_session.run())
    # After chat exits, the MCPManager context manager will clean up normally
```

Important: the MCPManager context must still be open when the chat runs, because the chat's `/conflicts` and `/summary` commands re-render from the in-memory `GapReport` object (no MCP calls needed). The MCP servers are not called during chat — but keeping them alive is fine and costs nothing.

**Change 2 — Add standalone `chat` command:**

Add a completely new command to `cli.py`:

```python
@app.command()
def chat(
    report_id: Annotated[Optional[str], typer.Option("--report", "-r", help="Report ID to chat about")] = None,
):
    """Start a chat session about a previously saved gap analysis report."""
    config = _load_config_or_exit()
    project_root = _detect_project_root_or_exit()

    if report_id is None:
        # No report specified — list available reports and let user choose
        _show_report_picker_and_chat(config, project_root)
        return

    # Load the specified report
    report = _load_report_by_id(report_id, project_root)
    if report is None:
        console.print(f"[red]Report not found:[/red] {report_id}")
        console.print("[dim]Run 'devagent reports' to see available reports.[/dim]")
        raise typer.Exit(1)

    project_name = _get_project_name(project_root)
    chat_session = ChatSession(report=report, config=config, project_name=project_name)
    asyncio.run(chat_session.run())
```

**`_load_report_by_id(report_id: str, project_root: Path) -> GapReport | None`:**

Private helper function in `cli.py`. Finds the markdown report file by ID, but more importantly, we need the structured `GapReport` object — not just the markdown. This means reports must be saved as JSON alongside the markdown.

**This requires a small change to Phase 6's report saving logic:**

In `devagent/output/markdown.py`, alongside saving the `.md` file, also save a `.json` file with `report.model_dump_json()`. Same filename, different extension:
- `issue-142-2025-01-15-143022.md`
- `issue-142-2025-01-15-143022.json`

The JSON file is the source for reloading a report. Load it with `GapReport.model_validate_json(json_file.read_text())`.

**`_show_report_picker_and_chat(config, project_root)`:**

Lists all `.json` report files in the project's reports directory. Shows them as a numbered list with Rich. Prompts user to pick one by number. Loads and starts chat.

```
Available reports for this project:

  1.  issue-142-2025-01-15   "Add OAuth2 login with Google"    4 reqs · 1 conflict
  2.  issue-89-2025-01-10    "Add rate limiting to API"         3 reqs · 0 conflicts
  3.  spec-auth-2025-01-08   "Auth refactor spec"               6 reqs · 2 conflicts

  Pick a report (1-3) or press Enter to cancel:
```

---

### The `devagent chat` command terminal behavior — full example

```
$ devagent chat --report issue-142-2025-01-15-143022

  Loading report: issue-142-2025-01-15  ✓

╭─────────────────────────────────────────────────────────────╮
│  DevAgent Chat  ·  Ask anything about this analysis         │
│  Commands: /summary  /conflicts  /order  /estimate  exit    │
╰─────────────────────────────────────────────────────────────╯

  You ❯ where should i start?

╭─ DevAgent ──────────────────────────────────────────────────╮
│                                                             │
│  Start with the conflict in `auth/session.py`.             │
│                                                             │
│  The `create_session()` function expects an existing        │
│  `user_id` from the database, but OAuth creates new users  │
│  on first login — the user doesn't exist in your DB yet    │
│  at the point `create_session()` is called.                │
│                                                             │
│  This conflict affects 6 files that import it, so          │
│  resolving it first prevents you from having to touch       │
│  those files multiple times.                               │
│                                                             │
│  After that: extend `auth/routes.py` with the callback     │
│  route, then build the new `auth/oauth.py` file.          │
│                                                             │
╰─────────────────────────────────────────────────────────────╯

  You ❯ which 6 files does it affect?

╭─ DevAgent ──────────────────────────────────────────────────╮
│                                                             │
│  The 6 files that import `create_session()` are:           │
│                                                             │
│  - `api/middleware.py`                                      │
│  - `tests/test_auth.py`                                     │
│  - `api/routes/user.py`                                     │
│  - `api/routes/admin.py`                                    │
│  - `services/auth_service.py`                               │
│  - `utils/session_helpers.py`                               │
│                                                             │
│  All of these will need to be updated once you change the   │
│  `create_session()` signature.                              │
│                                                             │
╰─────────────────────────────────────────────────────────────╯

  You ❯ /estimate

╭─ Effort Estimate ───────────────────────────────────────────╮
│  Conflict resolution    4.0h                                │
│  Extensions             2.0h                                │
│  Net new work           3.0h                                │
│  Testing                2.7h                                │
│  Total                  1.5 days                            │
│  Confidence             medium                              │
╰─────────────────────────────────────────────────────────────╯

  You ❯ exit

  Chat session ended.
```

---

### Tests — `tests/test_chat_context.py`

```python
from devagent.chat.context import build_system_prompt, estimate_prompt_tokens
from devagent.chat.history import ConversationHistory

def test_system_prompt_contains_requirements(sample_gap_report, sample_project_name):
    prompt = build_system_prompt(sample_gap_report, sample_project_name)
    # All requirement descriptions must appear in the prompt
    for ra in sample_gap_report.reuse + sample_gap_report.conflicts + \
              sample_gap_report.extend + sample_gap_report.net_new:
        assert ra.requirement.description in prompt

def test_system_prompt_contains_files(sample_gap_report, sample_project_name):
    prompt = build_system_prompt(sample_gap_report, sample_project_name)
    # Conflicted files must appear
    for ra in sample_gap_report.conflicts:
        if ra.conflict_details:
            for f in ra.conflict_details.affected_files:
                assert f in prompt

def test_history_trimming():
    history = ConversationHistory(system_prompt="test", max_tokens=200)
    # Add enough messages to exceed limit
    for i in range(20):
        history.add_user_message(f"question number {i} that is somewhat long")
        history.add_assistant_message(f"answer number {i} that is also somewhat long")
    # History should be trimmed
    total_tokens = history._total_tokens()
    assert total_tokens <= 200 + 50  # allow small buffer

def test_history_preserves_system_prompt():
    system = "This is my system prompt with important context."
    history = ConversationHistory(system_prompt=system, max_tokens=100)
    history.add_user_message("x" * 1000)  # force trim
    messages = history.to_langchain_messages()
    # First message must always be the system prompt
    assert messages[0].content == system

def test_to_langchain_messages_format(sample_gap_report, sample_project_name):
    from langchain_core.messages import SystemMessage, HumanMessage, AIMessage
    prompt = build_system_prompt(sample_gap_report, sample_project_name)
    history = ConversationHistory(system_prompt=prompt)
    history.add_user_message("where do I start?")
    history.add_assistant_message("Start with the conflicts.")
    messages = history.to_langchain_messages()
    assert isinstance(messages[0], SystemMessage)
    assert isinstance(messages[1], HumanMessage)
    assert isinstance(messages[2], AIMessage)
```

Add a `sample_gap_report` fixture to `tests/conftest.py` that creates a realistic `GapReport` object with at least 4 requirements (one of each status type), 2 edge cases, and an effort estimate.

---

### F2 Verification

F2 is complete when all of the following work:

**Basic chat flow:**
```
devagent analyze --issue 142 --chat
```
Gap report renders → chat session starts → questions are answered with knowledge of the specific gap report.

**URL + chat:**
```
devagent analyze --url https://github.com/owner/repo/issues/142 --chat
```
Works identically to above. F4 and F2 compose correctly.

**Standalone chat from saved report:**
```
devagent chat --report issue-142-2025-01-15-143022
```
Loads the report from the JSON file, starts chat. No re-analysis.

**Standalone chat with picker:**
```
devagent chat
```
Shows list of available reports, user picks one, chat starts.

**Special commands all work:**
```
/summary     → compact report re-renders
/conflicts   → conflicts section renders
/order       → numbered implementation order
/estimate    → effort estimate table
/clear       → history clears, confirmation shown
exit         → clean exit
Ctrl+C       → clean exit (no traceback)
```

**Out-of-scope questions are declined gracefully:**
```
You ❯ write the code for the OAuth callback for me
```
Response declines and explains what the chat is for, without being rude.

**Context trimming does not crash:**
A conversation with 30+ back-and-forth messages must not raise a context length error from the LLM. The trimming logic must kick in transparently.

**Report JSON files are saved alongside markdown:**
After any `devagent analyze` run, both `.md` and `.json` files exist in the reports directory.

---

## Summary — Exact File Change List

### New files (create from scratch):
```
devagent/core/url_parser.py
devagent/chat/__init__.py
devagent/chat/session.py
devagent/chat/context.py
devagent/chat/history.py
tests/test_url_parser.py
tests/test_chat_context.py
```

### Modified files (change only what is documented above):
```
devagent/cli.py                    ← add --url flag, --chat flag, chat command, helper functions
devagent/core/models.py            ← add resource_type field to PipelineState
devagent/mcp/clients/github_client.py  ← add get_pull_request method
devagent/agents/spec_parser.py     ← handle pull_request resource_type in fetch_spec node
devagent/output/terminal.py        ← add render_gap_report_compact and render_conflicts_only
devagent/output/markdown.py        ← also save .json alongside .md
tests/conftest.py                  ← add sample_gap_report fixture
```

### Files that must NOT be touched:
```
devagent/mcp/manager.py            ← unchanged
devagent/mcp/servers/             ← unchanged
devagent/agents/pipeline.py        ← unchanged
devagent/agents/code_inventory.py  ← unchanged
devagent/agents/gap_report.py      ← unchanged
devagent/core/config.py            ← unchanged
devagent/core/llm.py               ← unchanged
devagent/core/storage.py           ← unchanged
```

---

## Build Order

Build in this exact sequence:

1. `devagent/core/url_parser.py` + `tests/test_url_parser.py` — pure utility, no dependencies
2. `devagent/cli.py` — add `--url` flag using the parser — verify F4 works end to end
3. `devagent/core/models.py` — add `resource_type` to PipelineState
4. `devagent/mcp/clients/github_client.py` — add `get_pull_request`
5. `devagent/agents/spec_parser.py` — handle PR URLs in `fetch_spec` node
6. `devagent/output/markdown.py` — add JSON saving alongside markdown
7. `devagent/chat/context.py` — build system prompt from GapReport
8. `devagent/chat/history.py` — conversation history with trimming
9. `devagent/chat/session.py` — the full chat loop
10. `devagent/output/terminal.py` — add compact render and conflicts-only render
11. `devagent/cli.py` — wire `--chat` flag and `chat` command
12. `tests/test_chat_context.py` + `tests/conftest.py` — tests
13. End-to-end verification of both features together
