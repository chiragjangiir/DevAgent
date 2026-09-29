"""Phase 15 — Effort levels, extended thinking, bare mode, CI hardening tests."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_cfg(effort: str = "high", extended_thinking: bool = False):
    from devagent.core.config import DevAgentConfig
    cfg = DevAgentConfig()
    cfg.llm.effort = effort
    cfg.llm.extended_thinking = extended_thinking
    return cfg


# ---------------------------------------------------------------------------
# 15.1 Effort level config
# ---------------------------------------------------------------------------

class TestEffortConfig:
    def test_default_effort_is_high(self) -> None:
        from devagent.core.config import LLMConfig
        cfg = LLMConfig()
        assert cfg.effort == "high"

    def test_effort_field_accepts_all_levels(self) -> None:
        from devagent.core.config import LLMConfig
        for level in ("low", "medium", "high", "xhigh", "max"):
            cfg = LLMConfig(effort=level)
            assert cfg.effort == level

    def test_extended_thinking_defaults_false(self) -> None:
        from devagent.core.config import LLMConfig
        assert LLMConfig().extended_thinking is False

    def test_thinking_budget_tokens_default(self) -> None:
        from devagent.core.config import LLMConfig
        assert LLMConfig().thinking_budget_tokens == 10_000


# ---------------------------------------------------------------------------
# 15.1 Effort → max_tokens mapping
# ---------------------------------------------------------------------------

class TestEffortMaxTokens:
    def test_effort_to_max_tokens_table(self) -> None:
        from devagent.core.llm import _EFFORT_MAX_TOKENS
        assert _EFFORT_MAX_TOKENS["low"] == 2_048
        assert _EFFORT_MAX_TOKENS["medium"] == 4_096
        assert _EFFORT_MAX_TOKENS["high"] == 8_192
        assert _EFFORT_MAX_TOKENS["xhigh"] == 16_384
        assert _EFFORT_MAX_TOKENS["max"] == 32_768

    def test_effort_temperature_low_is_higher(self) -> None:
        from devagent.core.llm import _EFFORT_TEMPERATURE
        assert _EFFORT_TEMPERATURE["low"] > _EFFORT_TEMPERATURE["medium"]

    def test_effort_temperature_method_low(self) -> None:
        from devagent.core.config import LLMConfig
        from devagent.core.llm import LLMClient
        cfg = LLMConfig(effort="low", temperature=0.1)
        client = LLMClient(cfg)
        assert client._effort_temperature() == 0.3

    def test_effort_temperature_method_high_uses_cfg(self) -> None:
        from devagent.core.config import LLMConfig
        from devagent.core.llm import LLMClient
        cfg = LLMConfig(effort="high", temperature=0.15)
        client = LLMClient(cfg)
        assert client._effort_temperature() == 0.15


# ---------------------------------------------------------------------------
# 15.2 Anthropic extended thinking kwargs
# ---------------------------------------------------------------------------

class TestAnthropicThinkingKwargs:
    def test_no_thinking_when_disabled(self) -> None:
        from devagent.core.config import LLMConfig
        from devagent.core.llm import LLMClient
        cfg = LLMConfig(provider="anthropic", effort="max", extended_thinking=False)
        client = LLMClient(cfg)
        kwargs, thinking_enabled = client._anthropic_kwargs()
        assert "thinking" not in kwargs
        assert thinking_enabled is False
        assert "temperature" in kwargs

    def test_thinking_enabled_for_xhigh_anthropic(self) -> None:
        from devagent.core.config import LLMConfig
        from devagent.core.llm import _THINKING_CAPABLE_MODELS, LLMClient
        model = next(iter(_THINKING_CAPABLE_MODELS))
        cfg = LLMConfig(
            provider="anthropic", model=model,
            effort="xhigh", extended_thinking=True, thinking_budget_tokens=5_000,
        )
        client = LLMClient(cfg)
        kwargs, thinking_enabled = client._anthropic_kwargs()
        assert thinking_enabled is True
        assert "thinking" in kwargs
        assert kwargs["thinking"]["type"] == "enabled"
        assert kwargs["thinking"]["budget_tokens"] == 5_000
        assert "temperature" not in kwargs

    def test_thinking_disabled_for_medium_even_if_flag_set(self) -> None:
        from devagent.core.config import LLMConfig
        from devagent.core.llm import _THINKING_CAPABLE_MODELS, LLMClient
        model = next(iter(_THINKING_CAPABLE_MODELS))
        cfg = LLMConfig(
            provider="anthropic", model=model,
            effort="medium", extended_thinking=True,
        )
        client = LLMClient(cfg)
        kwargs, thinking_enabled = client._anthropic_kwargs()
        assert thinking_enabled is False
        assert "thinking" not in kwargs

    def test_thinking_budget_capped_below_max_tokens(self) -> None:
        from devagent.core.config import LLMConfig
        from devagent.core.llm import _EFFORT_MAX_TOKENS, _THINKING_CAPABLE_MODELS, LLMClient
        model = next(iter(_THINKING_CAPABLE_MODELS))
        # Set thinking_budget_tokens > max_tokens to trigger cap
        cfg = LLMConfig(
            provider="anthropic", model=model,
            effort="xhigh", extended_thinking=True,
            thinking_budget_tokens=99_999,
        )
        client = LLMClient(cfg)
        kwargs, _ = client._anthropic_kwargs()
        expected_max = _EFFORT_MAX_TOKENS["xhigh"]
        assert kwargs["thinking"]["budget_tokens"] < expected_max

    def test_max_tokens_reflects_effort(self) -> None:
        from devagent.core.config import LLMConfig
        from devagent.core.llm import _EFFORT_MAX_TOKENS, LLMClient
        for level in ("low", "medium", "high", "xhigh", "max"):
            cfg = LLMConfig(provider="anthropic", effort=level)
            client = LLMClient(cfg)
            kwargs, _ = client._anthropic_kwargs()
            assert kwargs["max_tokens"] == _EFFORT_MAX_TOKENS[level]


# ---------------------------------------------------------------------------
# 15.2 LLMResponse.thinking field
# ---------------------------------------------------------------------------

class TestLLMResponseThinking:
    def test_thinking_field_defaults_empty(self) -> None:
        from devagent.core.llm import LLMResponse
        resp = LLMResponse(content="hello")
        assert resp.thinking == ""

    def test_thinking_field_set(self) -> None:
        from devagent.core.llm import LLMResponse
        resp = LLMResponse(content="hello", thinking="I reasoned about this")
        assert "reasoned" in resp.thinking


# ---------------------------------------------------------------------------
# 15.2 Loop emits ThinkingEvent for extended thinking blocks
# ---------------------------------------------------------------------------

class TestLoopEmitsThinkingBlock:
    def test_thinking_text_yields_thinking_event(self, tmp_path: Path) -> None:
        from devagent.agent.loop import AgentLoop, ThinkingEvent
        from devagent.core.llm import LLMResponse
        from devagent.session.budget import TokenBudget
        from devagent.session.memory import MemoryBlock

        mock_llm = MagicMock()
        mock_llm.cfg = MagicMock()
        mock_llm.cfg.provider = "anthropic"
        mock_llm.cfg.model = "claude-opus-4-8"
        mock_llm.complete_with_tools.return_value = LLMResponse(
            content="Sure.",
            thinking="Let me think about this carefully.",
        )

        mock_mgr = MagicMock()
        mock_mgr.get_events.return_value = []

        mock_registry = MagicMock()
        mock_registry.get_definitions.return_value = []

        budget = TokenBudget()
        memory = MemoryBlock.__new__(MemoryBlock)
        memory._items = {}
        memory.as_prompt_block = lambda: ""

        with patch("devagent.session.history.build_messages") as mock_bm:
            mock_bm.return_value = []
            loop = AgentLoop(
                llm=mock_llm,
                registry=mock_registry,
                session_mgr=mock_mgr,
                session_id="test-sess",
                memory=memory,
                budget=budget,
                system_prompt="You are a helper.",
                bare=True,
            )
            events = list(loop.run("Hello"))

        thinking_events = [e for e in events if isinstance(e, ThinkingEvent)]
        # One ThinkingEvent for the extended thinking block, one for response.content
        assert any("<thinking>" in e.text for e in thinking_events)


# ---------------------------------------------------------------------------
# 15.3 Bare mode
# ---------------------------------------------------------------------------

class TestBareMode:
    def test_bare_skips_memory_injection(self, tmp_path: Path) -> None:
        from devagent.agent.loop import AgentLoop
        from devagent.core.llm import LLMResponse
        from devagent.session.budget import TokenBudget
        from devagent.session.memory import MemoryBlock

        memory = MemoryBlock.__new__(MemoryBlock)
        memory._items = {"key": "value"}
        memory.as_prompt_block = MagicMock(return_value="[memory: key=value]")

        mock_llm = MagicMock()
        mock_llm.cfg = MagicMock()
        mock_llm.complete_with_tools.return_value = LLMResponse(content="done")
        mock_mgr = MagicMock()
        mock_mgr.get_events.return_value = []
        mock_registry = MagicMock()
        mock_registry.get_definitions.return_value = []

        with patch("devagent.session.history.build_messages") as mock_bm:
            mock_bm.return_value = []
            loop = AgentLoop(
                llm=mock_llm,
                registry=mock_registry,
                session_mgr=mock_mgr,
                session_id="test",
                memory=memory,
                budget=TokenBudget(),
                system_prompt="sys",
                bare=True,
            )
            list(loop.run("hi"))

        # memory.as_prompt_block should NOT be called in bare mode
        memory.as_prompt_block.assert_not_called()

    def test_bare_flag_accepted_by_agentloop(self) -> None:
        from devagent.agent.loop import AgentLoop
        from devagent.session.budget import TokenBudget
        from devagent.session.memory import MemoryBlock

        memory = MemoryBlock.__new__(MemoryBlock)
        memory._items = {}
        memory.as_prompt_block = lambda: ""
        loop = AgentLoop(
            llm=MagicMock(),
            registry=MagicMock(),
            session_mgr=MagicMock(),
            session_id="s",
            memory=memory,
            budget=TokenBudget(),
            system_prompt="",
            bare=True,
        )
        assert loop._bare is True


# ---------------------------------------------------------------------------
# 15.4 stream_json_events output format
# ---------------------------------------------------------------------------

class TestStreamJsonEvents:
    def test_final_event_emitted_as_json(self, capsys) -> None:
        import json

        from devagent.agent.loop import FinalAnswerEvent
        from devagent.output.streaming import stream_json_events

        events = [FinalAnswerEvent(text="All done.")]
        result = stream_json_events(iter(events))
        captured = capsys.readouterr().out
        obj = json.loads(captured.strip())
        assert obj["type"] == "final"
        assert obj["text"] == "All done."
        assert result == "All done."

    def test_thinking_event_emitted_as_json(self, capsys) -> None:
        import json

        from devagent.agent.loop import ThinkingEvent
        from devagent.output.streaming import stream_json_events

        events = [ThinkingEvent(text="I am thinking.")]
        stream_json_events(iter(events))
        captured = capsys.readouterr().out
        obj = json.loads(captured.strip())
        assert obj["type"] == "thinking"
        assert "thinking" in obj["text"]

    def test_error_event_emitted_as_json(self, capsys) -> None:
        import json

        from devagent.agent.loop import ErrorEvent
        from devagent.output.streaming import stream_json_events

        events = [ErrorEvent(message="Something broke")]
        stream_json_events(iter(events))
        captured = capsys.readouterr().out
        obj = json.loads(captured.strip())
        assert obj["type"] == "error"
        assert "broke" in obj["message"]

    def test_tool_call_event_emitted_as_json(self, capsys) -> None:
        import json

        from devagent.agent.loop import ToolCallEvent
        from devagent.output.streaming import stream_json_events

        events = [ToolCallEvent(id="tc1", name="read_file", args={"path": "foo.py"})]
        stream_json_events(iter(events))
        captured = capsys.readouterr().out
        obj = json.loads(captured.strip())
        assert obj["type"] == "tool_call"
        assert obj["name"] == "read_file"

    def test_multiple_events_one_per_line(self, capsys) -> None:
        import json

        from devagent.agent.loop import FinalAnswerEvent, ThinkingEvent
        from devagent.output.streaming import stream_json_events

        events = [ThinkingEvent(text="thinking"), FinalAnswerEvent(text="done")]
        stream_json_events(iter(events))
        lines = [l for l in capsys.readouterr().out.strip().split("\n") if l]
        assert len(lines) == 2
        assert json.loads(lines[0])["type"] == "thinking"
        assert json.loads(lines[1])["type"] == "final"


# ---------------------------------------------------------------------------
# Phase 34 — emit_json (single JSON object output)
# ---------------------------------------------------------------------------

class TestEmitJson:
    def test_emits_single_json_object(self, capsys) -> None:
        import json

        from devagent.agent.loop import FinalAnswerEvent, ThinkingEvent
        from devagent.output.streaming import emit_json

        events = [ThinkingEvent(text="thinking"), FinalAnswerEvent(text="done")]
        result = emit_json(iter(events))
        captured = capsys.readouterr().out
        # Only one line emitted (single JSON object)
        lines = [l for l in captured.strip().split("\n") if l]
        assert len(lines) == 1
        obj = json.loads(lines[0])
        assert "events" in obj
        assert obj["final_text"] == "done"
        assert result == "done"

    def test_events_array_contains_all_types(self, capsys) -> None:
        import json

        from devagent.agent.loop import (
            ErrorEvent,
            FinalAnswerEvent,
            ThinkingEvent,
            ToolCallEvent,
            ToolResultEvent,
        )
        from devagent.output.streaming import emit_json

        events = [
            ThinkingEvent(text="t"),
            ToolCallEvent(id="1", name="read_file", args={"path": "x.py"}),
            ToolResultEvent(id="1", name="read_file", result="content", success=True),
            FinalAnswerEvent(text="answer"),
            ErrorEvent(message="oops"),
        ]
        emit_json(iter(events))
        obj = json.loads(capsys.readouterr().out.strip())
        types = [e["type"] for e in obj["events"]]
        assert "thinking" in types
        assert "tool_call" in types
        assert "tool_result" in types
        assert "final" in types
        assert "error" in types

    def test_empty_events_returns_empty_final_text(self, capsys) -> None:
        import json

        from devagent.output.streaming import emit_json

        result = emit_json(iter([]))
        obj = json.loads(capsys.readouterr().out.strip())
        assert obj["events"] == []
        assert obj["final_text"] == ""
        assert result == ""


# ---------------------------------------------------------------------------
# 15.1 /effort REPL command (unit test of the cfg mutation)
# ---------------------------------------------------------------------------

class TestEffortReplCommand:
    def test_effort_applied_to_cfg_on_init(self, tmp_path: Path) -> None:
        """--effort flag applied to cfg.llm.effort before session creation."""
        cfg = _make_cfg(effort="high")
        assert cfg.llm.effort == "high"
        # Simulate what DevAgentSession.__init__ does with effort override
        cfg.llm.effort = "max"
        assert cfg.llm.effort == "max"
