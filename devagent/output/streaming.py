"""Rich terminal renderer for the agent loop event stream.

Consumes AgentEvent objects from agent.loop.AgentLoop.run() and renders
them using Rich panels, spinners, and syntax highlighting.
"""

from __future__ import annotations

import json
from collections.abc import Generator

from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.rule import Rule
from rich.text import Text

from devagent.agent.loop import (
    AgentEvent,
    ApprovalNeededEvent,
    BudgetWarningEvent,
    ErrorEvent,
    FinalAnswerEvent,
    StatusEvent,
    ThinkingEvent,
    ToolCallEvent,
    ToolResultEvent,
)

console = Console()


def render_diff(diff_text: str) -> None:
    """Public wrapper around _render_diff — for use outside this module."""
    _render_diff(diff_text)


def render_events(
    events: Generator[AgentEvent, None, None],
    permission_mgr=None,   # PermissionManager | None
) -> str:
    """Render a stream of agent events to the terminal.

    Returns the final text answer (or empty string on error).
    """

    final_text = ""
    for event in events:
        if isinstance(event, ThinkingEvent):
            _render_thinking(event)
        elif isinstance(event, ToolCallEvent):
            _render_tool_call(event)
        elif isinstance(event, ToolResultEvent):
            _render_tool_result(event)
        elif isinstance(event, FinalAnswerEvent):
            _render_final_answer(event)
            final_text = event.text
        elif isinstance(event, BudgetWarningEvent):
            _render_budget_warning(event)
        elif isinstance(event, StatusEvent):
            _render_status(event)
        elif isinstance(event, ErrorEvent):
            _render_error(event)
        elif isinstance(event, ApprovalNeededEvent):
            _render_approval_needed(event, permission_mgr)
    return final_text


def emit_json(
    events: Generator[AgentEvent, None, None],
) -> str:
    """Collect all agent events and emit a single JSON object to stdout.

    Useful for CI pipelines that need to parse the whole run at once.
    Returns the final text answer (or empty string on error).
    """
    import sys

    collected: list[dict] = []
    final_text = ""
    for event in events:
        if isinstance(event, ThinkingEvent):
            collected.append({"type": "thinking", "text": event.text})
        elif isinstance(event, ToolCallEvent):
            collected.append({"type": "tool_call", "id": event.id, "name": event.name, "args": event.args})
        elif isinstance(event, ToolResultEvent):
            collected.append({"type": "tool_result", "id": event.id, "name": event.name,
                              "result": event.result, "success": event.success})
        elif isinstance(event, FinalAnswerEvent):
            collected.append({"type": "final", "text": event.text})
            final_text = event.text
        elif isinstance(event, BudgetWarningEvent):
            collected.append({"type": "budget_warning", "used": event.used, "remaining": event.remaining})
        elif isinstance(event, StatusEvent):
            collected.append({"type": "status", "status_line": event.status_line, "iteration": event.iteration})
        elif isinstance(event, ErrorEvent):
            collected.append({"type": "error", "message": event.message})
    sys.stdout.write(json.dumps({"events": collected, "final_text": final_text}) + "\n")
    sys.stdout.flush()
    return final_text


def stream_json_events(
    events: Generator[AgentEvent, None, None],
) -> str:
    """Emit each agent event as a JSON line to stdout (for CI / machine parsing).

    Returns the final text answer (or empty string on error).
    """
    import sys

    final_text = ""
    for event in events:
        if isinstance(event, ThinkingEvent):
            obj = {"type": "thinking", "text": event.text}
        elif isinstance(event, ToolCallEvent):
            obj = {"type": "tool_call", "id": event.id, "name": event.name, "args": event.args}
        elif isinstance(event, ToolResultEvent):
            obj = {"type": "tool_result", "id": event.id, "name": event.name,
                   "result": event.result, "success": event.success}
        elif isinstance(event, FinalAnswerEvent):
            obj = {"type": "final", "text": event.text}
            final_text = event.text
        elif isinstance(event, BudgetWarningEvent):
            obj = {"type": "budget_warning", "used": event.used, "remaining": event.remaining}
        elif isinstance(event, StatusEvent):
            obj = {"type": "status", "status_line": event.status_line, "iteration": event.iteration}
        elif isinstance(event, ErrorEvent):
            obj = {"type": "error", "message": event.message}
        else:
            continue
        sys.stdout.write(json.dumps(obj) + "\n")
        sys.stdout.flush()
    return final_text


def _render_thinking(event: ThinkingEvent) -> None:
    """Render reasoning/thinking text in a subtle style."""
    if not event.text.strip():
        return
    console.print()
    console.print(Markdown(event.text))


def _render_tool_call(event: ToolCallEvent) -> None:
    """Render a tool call with its arguments."""
    args_str = json.dumps(event.args, indent=2) if event.args else "{}"
    # Truncate very long args for readability
    if len(args_str) > 400:
        args_str = args_str[:400] + "\n  ... (truncated)"
    label = Text.assemble(
        Text("  Calling ", style="dim"),
        Text(event.name, style="bold cyan"),
        Text(f"  #{event.id[:6]}", style="dim"),
    )
    console.print()
    console.print(label)
    if event.args:
        console.print(Text(args_str, style="dim"))


def _render_tool_result(event: ToolResultEvent) -> None:
    """Render a tool result, truncated if very long."""
    result = event.result
    style = "green" if event.success else "red"
    prefix = "[OK]" if event.success else "[ERR]"

    # Truncate long output
    max_lines = 30
    lines = result.splitlines()
    if len(lines) > max_lines:
        shown = "\n".join(lines[:max_lines])
        result = f"{shown}\n... ({len(lines) - max_lines} more lines)"

    console.print(
        Panel(
            Text(result, style="dim"),
            title=Text.assemble(Text(prefix + " ", style=style), Text(event.name, style="bold")),
            border_style=style,
            expand=False,
        )
    )

    if event.diff:
        _render_diff(event.diff)


def _render_diff(diff_text: str) -> None:
    """Render a unified diff with colour-coded additions and removals."""
    output = Text()
    for line in diff_text.splitlines():
        if line.startswith(("+++", "---")):
            output.append(line + "\n", style="bold dim")
        elif line.startswith("+"):
            output.append(line + "\n", style="green")
        elif line.startswith("-"):
            output.append(line + "\n", style="red")
        elif line.startswith("@@"):
            output.append(line + "\n", style="cyan dim")
        else:
            output.append(line + "\n", style="dim")
    console.print(output)


def _render_final_answer(event: FinalAnswerEvent) -> None:
    """Render the final LLM answer with token usage footer."""
    console.print()
    console.print(Rule(style="bright_blue"))
    console.print(Markdown(event.text))
    console.print()
    if event.tokens_in or event.tokens_out:
        console.print(
            Text(
                f"  tokens: {event.tokens_in} in / {event.tokens_out} out",
                style="dim",
            )
        )


def _render_budget_warning(event: BudgetWarningEvent) -> None:
    pct = f"{event.used / event.limit * 100:.0f}%" if event.limit else "?"
    console.print(
        Text(
            f"  [budget] {event.used:,} / {event.limit:,} tokens used ({pct})",
            style="yellow",
        )
    )


def _render_status(event: StatusEvent) -> None:
    """Render the live status bar after each LLM call."""
    task_tag = f"  [{event.task}]" if event.task and event.task != "fallback" else ""
    console.print(Text(f"  {event.status_line}{task_tag}", style="dim"))


def _render_error(event: ErrorEvent) -> None:
    console.print()
    console.print(
        Panel(event.message, title="[bold red]Agent Error[/bold red]", border_style="red")
    )


def _render_approval_needed(event: ApprovalNeededEvent, permission_mgr=None) -> None:
    from rich.prompt import Confirm

    label = event.primary_arg or str(event.args)[:80]
    console.print()
    console.print(
        Panel(
            f"[bold]{event.tool_name}[/bold]  {label}",
            title="[yellow bold]Permission required[/yellow bold]",
            border_style="yellow",
        )
    )
    if permission_mgr is not None:
        approved = Confirm.ask("Allow this operation?", default=False)
        permission_mgr.resolve(event.call_id, approved)
    else:
        # No manager wired — auto-allow so the loop is not stuck
        pass
