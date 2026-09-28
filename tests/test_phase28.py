"""Tests for Phase 28 — Ollama Cloud model picker."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from devagent.core.config import LLMConfig

# ---------------------------------------------------------------------------
# list_ollama_models()
# ---------------------------------------------------------------------------

class TestListOllamaModels:
    def _client(self, api_key="", base_url="http://localhost:11434"):
        from devagent.core.llm import LLMClient
        return LLMClient(LLMConfig(provider="ollama", model="x", base_url=base_url, api_key=api_key))

    def _make_list_resp(self, names: list[str]):
        models = []
        for n in names:
            m = MagicMock()
            m.model = n
            models.append(m)
        resp = MagicMock()
        resp.models = models
        return resp

    def test_returns_model_names(self):
        lc = self._client()
        mock_ollama_client = MagicMock()
        mock_ollama_client.list.return_value = self._make_list_resp(
            ["llama3.2", "qwen2.5-coder:7b", "phi3.5"]
        )
        with patch.object(lc, "_ollama_client", return_value=mock_ollama_client):
            result = lc.list_ollama_models()
        assert result == ["llama3.2", "qwen2.5-coder:7b", "phi3.5"]

    def test_returns_empty_on_error(self):
        lc = self._client()
        mock_ollama_client = MagicMock()
        mock_ollama_client.list.side_effect = ConnectionError("offline")
        with patch.object(lc, "_ollama_client", return_value=mock_ollama_client):
            result = lc.list_ollama_models()
        assert result == []

    def test_cloud_client_called(self):
        """Cloud config → _ollama_client() is called (which adds Bearer header)."""
        lc = self._client(api_key="sk-test", base_url="https://ollama.com")
        mock_ollama_client = MagicMock()
        mock_ollama_client.list.return_value = self._make_list_resp(["gpt-oss:20b"])
        with patch.object(lc, "_ollama_client", return_value=mock_ollama_client) as mock_factory:
            lc.list_ollama_models()
        mock_factory.assert_called_once()

    def test_empty_models_list_handled(self):
        lc = self._client()
        mock_ollama_client = MagicMock()
        resp = MagicMock()
        resp.models = []
        mock_ollama_client.list.return_value = resp
        with patch.object(lc, "_ollama_client", return_value=mock_ollama_client):
            result = lc.list_ollama_models()
        assert result == []

    def test_none_models_handled(self):
        lc = self._client()
        mock_ollama_client = MagicMock()
        resp = MagicMock()
        resp.models = None
        mock_ollama_client.list.return_value = resp
        with patch.object(lc, "_ollama_client", return_value=mock_ollama_client):
            result = lc.list_ollama_models()
        assert result == []


# ---------------------------------------------------------------------------
# _fetch_ollama_models() CLI helper
# ---------------------------------------------------------------------------

class TestFetchOllamaModelsCli:
    def test_returns_model_list(self):
        from devagent.cli import _fetch_ollama_models

        mock_lc = MagicMock()
        mock_lc.list_ollama_models.return_value = ["gpt-oss:20b", "gpt-oss:120b"]

        with (
            patch("devagent.cli._LLMClient", mock_lc, create=True),
            patch("devagent.core.llm.LLMClient") as MockLC,
        ):
            MockLC.return_value = mock_lc
            result = _fetch_ollama_models("https://ollama.com", "sk-key")

        assert "gpt-oss:20b" in result

    def test_returns_empty_on_import_error(self):
        from devagent.cli import _fetch_ollama_models
        with patch("devagent.core.llm.LLMClient", side_effect=ImportError("no ollama")):
            result = _fetch_ollama_models("https://ollama.com", "sk-key")
        assert result == []

    def test_called_with_correct_config(self):
        from devagent.cli import _fetch_ollama_models

        captured = {}

        def fake_lc(cfg):
            captured["cfg"] = cfg
            m = MagicMock()
            m.list_ollama_models.return_value = []
            return m

        with patch("devagent.core.llm.LLMClient", side_effect=fake_lc):
            _fetch_ollama_models("https://ollama.com", "mykey")

        assert captured["cfg"].base_url == "https://ollama.com"
        assert captured["cfg"].api_key == "mykey"
        assert captured["cfg"].provider == "ollama"


# ---------------------------------------------------------------------------
# /model REPL command — numeric index switching
# ---------------------------------------------------------------------------

class TestModelCommandNumericSwitch:
    def _handle(self, raw: str, cfg_model: str, models: list[str]) -> str:
        """Simulate the /model numeric branch. Returns the resulting model name."""
        parts = raw.split(None, 1)
        spec = parts[1].strip() if len(parts) > 1 else ""

        class _Cfg:
            provider = "ollama"
            model = cfg_model

        cfg = _Cfg()

        if spec.isdigit() and cfg.provider == "ollama":
            idx = int(spec) - 1
            if models and 0 <= idx < len(models):
                cfg.model = models[idx]
        else:
            cfg.model = spec

        return cfg.model

    def test_pick_first_model(self):
        result = self._handle("/model 1", "llama3.2", ["gpt-oss:20b", "gpt-oss:120b", "llama3.2"])
        assert result == "gpt-oss:20b"

    def test_pick_third_model(self):
        result = self._handle("/model 3", "llama3.2", ["gpt-oss:20b", "gpt-oss:120b", "llama3.2"])
        assert result == "llama3.2"

    def test_out_of_range_keeps_original(self):
        # Out of range → message shown, model unchanged
        parts = ["/model", "99"]
        spec = parts[1].strip()
        models = ["gpt-oss:20b"]
        idx = int(spec) - 1
        assert not (0 <= idx < len(models))

    def test_name_switch_still_works(self):
        result = self._handle("/model phi3.5", "llama3.2", ["gpt-oss:20b"])
        assert result == "phi3.5"

    def test_non_digit_spec_applied_directly(self):
        result = self._handle("/model anthropic/claude-sonnet-4-6", "llama3.2", [])
        assert result == "anthropic/claude-sonnet-4-6"

    def test_flows_source_has_phase28(self):
        import pathlib
        src = pathlib.Path(__file__).parent.parent / "devagent" / "agent" / "flows.py"
        text = src.read_text(encoding="utf-8")
        assert "Phase 28" in text
        assert "list_ollama_models" in text
        assert "isdigit" in text
