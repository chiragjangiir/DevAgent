"""LLM provider factory -- direct official SDKs, no framework wrapper.

Two usage modes:
  1. Simple chat: LLMClient.complete(messages) / acomplete(messages)
  2. Agent loop:  LLMClient.complete_with_tools(agent_messages, tools)

Supports: ollama, anthropic, openai, groq (openai-compat), gemini.
"""

from __future__ import annotations

import asyncio
import json
import time
import uuid
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from typing import Any

from devagent.core.config import DevAgentConfig, LLMConfig

# ---------------------------------------------------------------------------
# Image sentinel (Phase 16 — vision tools)
# Shared with devagent/tools/vision_tools.py — same value, no circular import.
# ---------------------------------------------------------------------------

_IMAGE_SENTINEL = "\n__image__:"

# ---------------------------------------------------------------------------
# Effort-level tables
# ---------------------------------------------------------------------------

_EFFORT_MAX_TOKENS: dict[str, int] = {
    "low":    2_048,
    "medium": 4_096,
    "high":   8_192,
    "xhigh": 16_384,
    "max":   32_768,
}

# Temperature overrides for low/medium; high/xhigh/max use cfg.temperature
_EFFORT_TEMPERATURE: dict[str, float] = {
    "low":    0.3,
    "medium": 0.2,
}

# Effort levels that activate extended thinking (Anthropic only)
_THINKING_EFFORTS: frozenset[str] = frozenset({"xhigh", "max"})

# Anthropic models that support extended thinking
_THINKING_CAPABLE_MODELS: frozenset[str] = frozenset({
    "claude-opus-4-8",
    "claude-sonnet-4-6",
    "claude-haiku-4-5-20251001",
})

# ---------------------------------------------------------------------------
# Shared types
# ---------------------------------------------------------------------------

@dataclass
class Message:
    """Simple message for non-agent chat (used by chat/ module)."""
    role: str   # system | user | assistant
    content: str


@dataclass
class ToolCallRequest:
    """A tool call requested by the LLM."""
    id: str
    name: str
    args: dict[str, Any]


@dataclass
class AgentMessage:
    """Richer message type for the agent loop -- supports tool calls and results."""
    role: str  # system | user | assistant | tool_result
    content: str = ""
    # Populated when role == "assistant" and LLM chose to call tools
    tool_calls: list[ToolCallRequest] = field(default_factory=list)
    # Populated when role == "tool_result"
    tool_call_id: str = ""
    tool_name: str = ""
    tool_success: bool = True


@dataclass
class ToolDef:
    """A tool definition (JSON-Schema parameters, OpenAI-compatible)."""
    name: str
    description: str
    parameters: dict  # JSON Schema object


@dataclass
class LLMResponse:
    content: str
    tool_calls: list[ToolCallRequest] = field(default_factory=list)
    thinking: str = ""   # extended thinking text (Anthropic only; Phase 15)
    input_tokens: int = 0
    output_tokens: int = 0
    model: str = ""
    provider: str = ""

    @property
    def has_tool_calls(self) -> bool:
        return bool(self.tool_calls)


# ---------------------------------------------------------------------------
# Rate limiter (Groq free tier)
# ---------------------------------------------------------------------------

class _TokenBucket:
    def __init__(self, tokens_per_minute: int):
        self.capacity = tokens_per_minute
        self.tokens = float(tokens_per_minute)
        self.fill_rate = tokens_per_minute / 60.0
        self.last_update = time.monotonic()
        self._lock = asyncio.Lock()

    def _update(self) -> None:
        now = time.monotonic()
        self.tokens = min(self.capacity, self.tokens + (now - self.last_update) * self.fill_rate)
        self.last_update = now

    def acquire(self) -> None:
        while True:
            self._update()
            if self.tokens >= 1:
                self.tokens -= 1
                return
            time.sleep(1 / self.fill_rate)

    async def aacquire(self) -> None:
        while True:
            async with self._lock:
                self._update()
                if self.tokens >= 1:
                    self.tokens -= 1
                    return
            await asyncio.sleep(1 / self.fill_rate)


_groq_limiter = _TokenBucket(30)


# ---------------------------------------------------------------------------
# Provider-specific message format converters
# ---------------------------------------------------------------------------

def _to_openai_messages(messages: list[AgentMessage]) -> list[dict]:
    result = []
    for msg in messages:
        if msg.role == "tool_result":
            # OpenAI tool messages don't support image content blocks — strip sentinel
            content = msg.content
            if _IMAGE_SENTINEL in content:
                content = content.split(_IMAGE_SENTINEL, 1)[0]
            result.append({
                "role": "tool",
                "tool_call_id": msg.tool_call_id,
                "name": msg.tool_name,
                "content": content,
            })
        elif msg.role == "assistant" and msg.tool_calls:
            result.append({
                "role": "assistant",
                "content": msg.content or None,
                "tool_calls": [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {
                            "name": tc.name,
                            "arguments": json.dumps(tc.args),
                        },
                    }
                    for tc in msg.tool_calls
                ],
            })
        else:
            result.append({"role": msg.role, "content": msg.content})
    return result


def _to_ollama_messages(messages: list[AgentMessage]) -> list[dict]:
    """Like _to_openai_messages but passes tool_call arguments as dicts.

    The Ollama Python library validates history messages with Pydantic and
    rejects arguments formatted as JSON strings (which is the OpenAI convention).
    """
    result = []
    for msg in messages:
        if msg.role == "tool_result":
            content = msg.content
            if _IMAGE_SENTINEL in content:
                content = content.split(_IMAGE_SENTINEL, 1)[0]
            result.append({
                "role": "tool",
                "tool_call_id": msg.tool_call_id,
                "name": msg.tool_name,
                "content": content,
            })
        elif msg.role == "assistant" and msg.tool_calls:
            result.append({
                "role": "assistant",
                "content": msg.content or None,
                "tool_calls": [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {
                            "name": tc.name,
                            "arguments": tc.args,  # dict, not JSON string
                        },
                    }
                    for tc in msg.tool_calls
                ],
            })
        else:
            result.append({"role": msg.role, "content": msg.content})
    return result


def _to_anthropic_messages(messages: list[AgentMessage]) -> list[dict]:
    """Convert to Anthropic format (strict user/assistant alternation,
    tool results bundled into user messages)."""
    result: list[dict] = []
    pending_tool_results: list[dict] = []

    for msg in messages:
        if msg.role == "system":
            continue  # handled separately

        if msg.role == "tool_result":
            content = msg.content
            if _IMAGE_SENTINEL in content:
                text_part, rest = content.split(_IMAGE_SENTINEL, 1)
                media_type, b64_data = rest.split(":", 1)
                image_content: list[dict] = []
                if text_part:
                    image_content.append({"type": "text", "text": text_part})
                image_content.append({
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": media_type,
                        "data": b64_data,
                    },
                })
                pending_tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": msg.tool_call_id,
                    "content": image_content,
                })
            else:
                pending_tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": msg.tool_call_id,
                    "content": content,
                })
            continue

        # Flush pending tool results before any non-tool_result message
        if pending_tool_results:
            result.append({"role": "user", "content": pending_tool_results})
            pending_tool_results = []

        if msg.role == "assistant" and msg.tool_calls:
            content: list[dict] = []
            if msg.content:
                content.append({"type": "text", "text": msg.content})
            for tc in msg.tool_calls:
                content.append({
                    "type": "tool_use",
                    "id": tc.id,
                    "name": tc.name,
                    "input": tc.args,
                })
            result.append({"role": "assistant", "content": content})
        else:
            result.append({"role": msg.role, "content": msg.content})

    if pending_tool_results:
        result.append({"role": "user", "content": pending_tool_results})

    return result


def _to_openai_tools(tools: list[ToolDef]) -> list[dict]:
    return [
        {
            "type": "function",
            "function": {
                "name": t.name,
                "description": t.description,
                "parameters": t.parameters,
            },
        }
        for t in tools
    ]


def _to_anthropic_tools(tools: list[ToolDef]) -> list[dict]:
    return [
        {
            "name": t.name,
            "description": t.description,
            "input_schema": t.parameters,
        }
        for t in tools
    ]


# ---------------------------------------------------------------------------
# LLMClient
# ---------------------------------------------------------------------------

class LLMClient:
    """Unified LLM client over official provider SDKs."""

    def __init__(self, cfg: LLMConfig) -> None:
        self.cfg = cfg

    # ------------------------------------------------------------------
    # Simple chat (no tools)
    # ------------------------------------------------------------------

    def complete(self, messages: list[Message], **kwargs) -> LLMResponse:
        """Synchronous completion (simple messages)."""
        agent_msgs = [AgentMessage(role=m.role, content=m.content) for m in messages]
        return self._dispatch(agent_msgs, tools=None, **kwargs)

    async def acomplete(self, messages: list[Message], **kwargs) -> LLMResponse:
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, lambda: self.complete(messages, **kwargs))

    async def astream(self, messages: list[Message], **kwargs) -> AsyncIterator[str]:
        """Stream text chunks for simple (no-tool) responses."""
        p = self.cfg.provider
        agent_msgs = [AgentMessage(role=m.role, content=m.content) for m in messages]
        if p == "ollama":
            async for chunk in self._ollama_stream(agent_msgs):
                yield chunk
        elif p in ("openai", "groq"):
            async for chunk in self._openai_stream(agent_msgs):
                yield chunk
        elif p == "anthropic":
            async for chunk in self._anthropic_stream(agent_msgs):
                yield chunk
        else:
            resp = await self.acomplete(messages)
            yield resp.content

    # ------------------------------------------------------------------
    # Agent loop (with tools)
    # ------------------------------------------------------------------

    def complete_with_tools(
        self,
        messages: list[AgentMessage],
        tools: list[ToolDef],
    ) -> LLMResponse:
        return self._dispatch(messages, tools=tools)

    async def acomplete_with_tools(
        self,
        messages: list[AgentMessage],
        tools: list[ToolDef],
    ) -> LLMResponse:
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None, lambda: self.complete_with_tools(messages, tools)
        )

    async def astream_with_tools(
        self,
        messages: list[AgentMessage],
        tools: list[ToolDef],
    ) -> AsyncIterator[str]:
        """Stream text chunks during a tool-capable call.
        Yields text as it arrives; tool calls are NOT streamed (returned
        via complete_with_tools after streaming finishes).
        """
        p = self.cfg.provider
        if p == "ollama":
            async for chunk in self._ollama_stream(messages, tools=tools):
                yield chunk
        elif p in ("openai", "groq"):
            async for chunk in self._openai_stream(messages, tools=tools):
                yield chunk
        elif p == "anthropic":
            async for chunk in self._anthropic_stream(messages, tools=tools):
                yield chunk
        else:
            resp = await self.acomplete_with_tools(messages, tools)
            yield resp.content

    # ------------------------------------------------------------------
    # Internal dispatch
    # ------------------------------------------------------------------

    def _dispatch(
        self,
        messages: list[AgentMessage],
        tools: list[ToolDef] | None,
    ) -> LLMResponse:
        p = self.cfg.provider
        if p == "ollama":
            return self._ollama(messages, tools)
        elif p in ("openai", "groq"):
            return self._openai(messages, tools)
        elif p == "anthropic":
            return self._anthropic(messages, tools)
        elif p == "gemini":
            return self._gemini(messages)
        else:
            raise ValueError(f"Unknown provider: {p!r}")

    # ------------------------------------------------------------------
    # Ollama
    # ------------------------------------------------------------------

    def _effort_temperature(self) -> float:
        effort = self.cfg.effort
        return _EFFORT_TEMPERATURE.get(effort, self.cfg.temperature)

    @staticmethod
    def _extract_text_tool_calls(content: str, valid_names: set[str]) -> list[ToolCallRequest]:
        """Parse JSON tool calls embedded in the model's text output.

        Some smaller models write tool calls as JSON in the content field instead of
        using the structured tool_calls field. Handles two shapes:

            Array:  [{"name": "read_file", "arguments": {"path": "x.py"}}, ...]
            Object: {"name": "write_file", "parameters": {"path": "x.py", ...}}

        Both may optionally appear inside a fenced code block.
        The key for args is accepted as "arguments", "parameters", or "args".
        """
        text = content.strip()
        if text.startswith("```"):
            newline = text.find("\n")
            text = text[newline + 1:] if newline != -1 else text[3:]
            fence_end = text.rfind("```")
            if fence_end != -1:
                text = text[:fence_end]
            text = text.strip()

        if not text.startswith(("[", "{")):
            return []

        # Determine the outer bracket pair and find its closing position.
        open_ch, close_ch = ("[", "]") if text.startswith("[") else ("{", "}")
        depth = 0
        end = 0
        for i, ch in enumerate(text):
            if ch == open_ch:
                depth += 1
            elif ch == close_ch:
                depth -= 1
                if depth == 0:
                    end = i + 1
                    break
        if not end:
            return []

        try:
            parsed = json.loads(text[:end])
        except (json.JSONDecodeError, ValueError):
            return []

        # Normalise to a list of candidate items.
        items: list = parsed if isinstance(parsed, list) else [parsed]

        def _coerce_args(raw: object) -> dict:
            if isinstance(raw, dict):
                return raw
            if isinstance(raw, str):
                try:
                    out = json.loads(raw)
                    return out if isinstance(out, dict) else {}
                except (json.JSONDecodeError, ValueError):
                    return {}
            return {}

        result: list[ToolCallRequest] = []
        for item in items:
            if not isinstance(item, dict):
                continue
            name = item.get("name") or item.get("tool")
            args = _coerce_args(
                item.get("arguments") or item.get("parameters") or item.get("args") or {}
            )
            if not name or name not in valid_names:
                continue
            result.append(ToolCallRequest(id=str(uuid.uuid4())[:8], name=name, args=args))
        return result

    def list_ollama_models(self) -> list[str]:
        """Return model names available at this Ollama endpoint (local or cloud).

        Returns an empty list on any error so callers can degrade gracefully.
        """
        try:
            client = self._ollama_client()
            resp = client.list()
            return [m.model for m in (resp.models or [])]
        except Exception:
            return []

    def _ollama_client(self) -> ollama.Client:
        """Return an ollama.Client configured for local or Ollama Cloud.

        Cloud is detected when api_key is set, or when base_url is not the
        default localhost address.  Cloud requests use https://ollama.com as
        the host and pass the key as an Authorization: Bearer header.
        """
        import ollama

        _LOCAL_DEFAULT = "http://localhost:11434"
        base_url = self.cfg.base_url or _LOCAL_DEFAULT
        api_key = self.cfg.api_key or ""

        # Cloud: explicit key always wins; non-default URL is also cloud-like.
        if api_key:
            host = base_url if base_url != _LOCAL_DEFAULT else "https://ollama.com"
            return ollama.Client(
                host=host,
                headers={"Authorization": f"Bearer {api_key}"},
            )
        if base_url != _LOCAL_DEFAULT:
            return ollama.Client(host=base_url)
        return ollama.Client()

    def _ollama(self, messages: list[AgentMessage], tools: list[ToolDef] | None) -> LLMResponse:

        client = self._ollama_client()
        oai_messages = _to_ollama_messages(messages)
        oai_tools = _to_openai_tools(tools) if tools else []
        kwargs: dict[str, Any] = {
            "model": self.cfg.model,
            "messages": oai_messages,
            "options": {"temperature": self._effort_temperature()},
        }
        if tools:
            kwargs["tools"] = oai_tools

        try:
            resp = client.chat(**kwargs)
            msg = resp.message
            raw_tcs = msg.tool_calls or []
            tool_calls = [
                ToolCallRequest(
                    id=str(uuid.uuid4())[:8],
                    name=tc.function.name,
                    args=tc.function.arguments if isinstance(tc.function.arguments, dict)
                         else json.loads(tc.function.arguments),
                )
                for tc in raw_tcs
            ]
            content = msg.content or ""
            # Fallback: some models emit tool calls as JSON in the content field.
            if tools and not tool_calls and content:
                valid = {t.name for t in tools}
                text_tcs = self._extract_text_tool_calls(content, valid)
                if text_tcs:
                    tool_calls = text_tcs
                    content = ""
            return LLMResponse(
                content=content,
                tool_calls=tool_calls,
                input_tokens=resp.prompt_eval_count or 0,
                output_tokens=resp.eval_count or 0,
                model=self.cfg.model,
                provider="ollama",
            )
        except Exception as exc:
            # Some Ollama versions return tool_call arguments as a JSON string,
            # causing a Pydantic validation error inside the ollama library.
            # Fall back to the raw HTTP response and normalise manually.
            if "arguments" not in str(exc) and "validation" not in str(exc).lower():
                raise
            raw = client._request_raw(
                "POST", "/api/chat",
                json={
                    "model": self.cfg.model,
                    "messages": oai_messages,
                    "tools": oai_tools,
                    "stream": False,
                    "options": {"temperature": self._effort_temperature()},
                },
            ).json()
            msg_raw = raw.get("message", {})
            tool_calls = []
            for tc in (msg_raw.get("tool_calls") or []):
                func = tc.get("function", {})
                args = func.get("arguments", {})
                if isinstance(args, str):
                    try:
                        args = json.loads(args)
                    except (json.JSONDecodeError, ValueError):
                        args = {}
                tool_calls.append(ToolCallRequest(
                    id=str(uuid.uuid4())[:8],
                    name=func.get("name", ""),
                    args=args,
                ))
            return LLMResponse(
                content=msg_raw.get("content") or "",
                tool_calls=tool_calls,
                input_tokens=raw.get("prompt_eval_count") or 0,
                output_tokens=raw.get("eval_count") or 0,
                model=self.cfg.model,
                provider="ollama",
            )

    async def _ollama_stream(
        self,
        messages: list[AgentMessage],
        tools: list[ToolDef] | None = None,
    ) -> AsyncIterator[str]:
        client = self._ollama_client()
        kwargs: dict[str, Any] = {
            "model": self.cfg.model,
            "messages": _to_ollama_messages(messages),
            "options": {"temperature": self._effort_temperature()},
            "stream": True,
        }
        if tools:
            kwargs["tools"] = _to_openai_tools(tools)

        for chunk in client.chat(**kwargs):
            text = chunk.message.content
            if text:
                yield text

    # ------------------------------------------------------------------
    # OpenAI / Groq
    # ------------------------------------------------------------------

    def _openai(self, messages: list[AgentMessage], tools: list[ToolDef] | None) -> LLMResponse:
        import openai

        if self.cfg.provider == "groq":
            _groq_limiter.acquire()
            client = openai.OpenAI(
                api_key=self.cfg.api_key,
                base_url="https://api.groq.com/openai/v1",
            )
        else:
            client = openai.OpenAI(api_key=self.cfg.api_key or None)

        kwargs: dict[str, Any] = {
            "model": self.cfg.model,
            "messages": _to_openai_messages(messages),
            "temperature": self._effort_temperature(),
        }
        if tools:
            kwargs["tools"] = _to_openai_tools(tools)
            kwargs["tool_choice"] = "auto"

        resp = client.chat.completions.create(**kwargs)
        choice = resp.choices[0]
        msg = choice.message

        tool_calls: list[ToolCallRequest] = []
        if msg.tool_calls:
            for tc in msg.tool_calls:
                tool_calls.append(ToolCallRequest(
                    id=tc.id,
                    name=tc.function.name,
                    args=json.loads(tc.function.arguments),
                ))

        return LLMResponse(
            content=msg.content or "",
            tool_calls=tool_calls,
            input_tokens=resp.usage.prompt_tokens if resp.usage else 0,
            output_tokens=resp.usage.completion_tokens if resp.usage else 0,
            model=self.cfg.model,
            provider=self.cfg.provider,
        )

    async def _openai_stream(
        self,
        messages: list[AgentMessage],
        tools: list[ToolDef] | None = None,
    ) -> AsyncIterator[str]:
        import openai

        if self.cfg.provider == "groq":
            await _groq_limiter.aacquire()
            client = openai.AsyncOpenAI(
                api_key=self.cfg.api_key,
                base_url="https://api.groq.com/openai/v1",
            )
        else:
            client = openai.AsyncOpenAI(api_key=self.cfg.api_key or None)

        kwargs: dict[str, Any] = {
            "model": self.cfg.model,
            "messages": _to_openai_messages(messages),
            "temperature": self._effort_temperature(),
            "stream": True,
        }
        if tools:
            kwargs["tools"] = _to_openai_tools(tools)
            kwargs["tool_choice"] = "auto"

        stream = await client.chat.completions.create(**kwargs)
        async for chunk in stream:
            delta = chunk.choices[0].delta
            if delta.content:
                yield delta.content

    # ------------------------------------------------------------------
    # Anthropic
    # ------------------------------------------------------------------

    def _anthropic_kwargs(self) -> tuple[dict[str, Any], bool]:
        """Build common Anthropic kwargs from effort + thinking config.

        Returns (kwargs_dict, thinking_enabled).
        """
        effort = self.cfg.effort
        max_tokens = _EFFORT_MAX_TOKENS.get(effort, 8_192)

        use_thinking = (
            effort in _THINKING_EFFORTS
            and self.cfg.extended_thinking
            and self.cfg.model in _THINKING_CAPABLE_MODELS
        )

        kwargs: dict[str, Any] = {
            "model": self.cfg.model,
            "max_tokens": max_tokens,
        }
        if use_thinking:
            budget = min(self.cfg.thinking_budget_tokens, max_tokens - 1_024)
            kwargs["thinking"] = {"type": "enabled", "budget_tokens": budget}
            # Anthropic forbids temperature when thinking is enabled
        else:
            kwargs["temperature"] = _EFFORT_TEMPERATURE.get(effort, self.cfg.temperature)

        return kwargs, use_thinking

    def _anthropic(self, messages: list[AgentMessage], tools: list[ToolDef] | None) -> LLMResponse:
        import anthropic

        client = anthropic.Anthropic(api_key=self.cfg.api_key or None)
        system = next((m.content for m in messages if m.role == "system"), "")
        chat_msgs = _to_anthropic_messages(messages)

        kwargs, _ = self._anthropic_kwargs()
        kwargs["messages"] = chat_msgs
        if system:
            kwargs["system"] = system
        if tools:
            kwargs["tools"] = _to_anthropic_tools(tools)

        resp = client.messages.create(**kwargs)

        text_content = ""
        thinking_text = ""
        tool_calls: list[ToolCallRequest] = []
        for block in resp.content:
            if block.type == "text":
                text_content += block.text
            elif block.type == "thinking":
                thinking_text += block.thinking
            elif block.type == "tool_use":
                tool_calls.append(ToolCallRequest(
                    id=block.id,
                    name=block.name,
                    args=block.input,
                ))

        return LLMResponse(
            content=text_content,
            tool_calls=tool_calls,
            thinking=thinking_text,
            input_tokens=resp.usage.input_tokens,
            output_tokens=resp.usage.output_tokens,
            model=self.cfg.model,
            provider="anthropic",
        )

    async def _anthropic_stream(
        self,
        messages: list[AgentMessage],
        tools: list[ToolDef] | None = None,
    ) -> AsyncIterator[str]:
        import anthropic

        client = anthropic.AsyncAnthropic(api_key=self.cfg.api_key or None)
        system = next((m.content for m in messages if m.role == "system"), "")
        chat_msgs = _to_anthropic_messages(messages)

        kwargs, use_thinking = self._anthropic_kwargs()
        kwargs["messages"] = chat_msgs
        if system:
            kwargs["system"] = system
        if tools:
            kwargs["tools"] = _to_anthropic_tools(tools)

        if use_thinking:
            # Stream raw events so we can surface thinking blocks with markers
            async with client.messages.stream(**kwargs) as stream:
                in_thinking = False
                async for event in stream:
                    etype = getattr(event, "type", "")
                    if etype == "content_block_start":
                        block = getattr(event, "content_block", None)
                        if block and getattr(block, "type", "") == "thinking":
                            in_thinking = True
                            yield "<thinking>\n"
                    elif etype == "content_block_stop":
                        if in_thinking:
                            in_thinking = False
                            yield "\n</thinking>\n"
                    elif etype == "content_block_delta":
                        delta = getattr(event, "delta", None)
                        if delta:
                            dtype = getattr(delta, "type", "")
                            if dtype == "thinking_delta":
                                yield getattr(delta, "thinking", "")
                            elif dtype == "text_delta":
                                yield getattr(delta, "text", "")
        else:
            async with client.messages.stream(**kwargs) as stream:
                async for text in stream.text_stream:
                    yield text

    # ------------------------------------------------------------------
    # Gemini (no tool calling yet -- text only)
    # ------------------------------------------------------------------

    def _gemini(self, messages: list[AgentMessage]) -> LLMResponse:
        import google.generativeai as genai

        genai.configure(api_key=self.cfg.api_key)
        model = genai.GenerativeModel(self.cfg.model)
        prompt = "\n".join(
            f"{m.role}: {m.content}"
            for m in messages
            if m.role != "system"
        )
        resp = model.generate_content(prompt)
        return LLMResponse(
            content=resp.text,
            model=self.cfg.model,
            provider="gemini",
        )


# ---------------------------------------------------------------------------
# Factory helpers
# ---------------------------------------------------------------------------

def get_llm(config: DevAgentConfig) -> LLMClient:
    """Return an LLMClient for the primary configured provider."""
    return LLMClient(config.llm)


def get_llm_for_task(config: DevAgentConfig, task: str) -> LLMClient:
    """Return an LLMClient routed by task type using RouterConfig.

    task: "planning" | "coding" | "reviewing" | "cheap"
    """
    router_entry = getattr(config.router, task, None) or config.router.fallback
    routed_cfg = LLMConfig(
        provider=router_entry.get("provider", config.llm.provider),
        model=router_entry.get("model", config.llm.model),
        base_url=config.llm.base_url,
        temperature=config.llm.temperature,
        api_key=config.llm.api_key,
    )
    return LLMClient(routed_cfg)
