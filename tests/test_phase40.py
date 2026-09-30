"""Tests for Phase 40 — OAuth 2.0 PKCE MCP authentication."""

from __future__ import annotations

import base64
import hashlib
import json
import time
from pathlib import Path
from unittest.mock import patch

# ---------------------------------------------------------------------------
# PKCE primitives
# ---------------------------------------------------------------------------

class TestPKCEPrimitives:
    def test_verifier_length_default(self) -> None:
        from devagent.mcp.auth.pkce import generate_code_verifier
        v = generate_code_verifier()
        assert len(v) == 64

    def test_verifier_length_custom(self) -> None:
        from devagent.mcp.auth.pkce import generate_code_verifier
        v = generate_code_verifier(length=43)
        assert len(v) == 43

    def test_verifier_invalid_length_raises(self) -> None:
        from devagent.mcp.auth.pkce import generate_code_verifier
        try:
            generate_code_verifier(length=10)
            assert False, "should raise"
        except ValueError:
            pass

    def test_verifier_uniqueness(self) -> None:
        from devagent.mcp.auth.pkce import generate_code_verifier
        assert generate_code_verifier() != generate_code_verifier()

    def test_challenge_is_base64url_sha256(self) -> None:
        from devagent.mcp.auth.pkce import compute_code_challenge
        verifier = "dBjftJeZ4CVP-mB92K27uhbUJU1p1r_wW1gFWFOEjXk"
        challenge = compute_code_challenge(verifier)
        expected = base64.urlsafe_b64encode(
            hashlib.sha256(verifier.encode()).digest()
        ).rstrip(b"=").decode()
        assert challenge == expected

    def test_challenge_no_padding(self) -> None:
        from devagent.mcp.auth.pkce import compute_code_challenge, generate_code_verifier
        challenge = compute_code_challenge(generate_code_verifier())
        assert "=" not in challenge

    def test_challenge_url_safe(self) -> None:
        from devagent.mcp.auth.pkce import compute_code_challenge, generate_code_verifier
        challenge = compute_code_challenge(generate_code_verifier())
        import re
        assert re.fullmatch(r"[A-Za-z0-9_\-]+", challenge)


# ---------------------------------------------------------------------------
# Token cache
# ---------------------------------------------------------------------------

class TestTokenCache:
    def test_save_and_get_token(self) -> None:
        from devagent.mcp.auth import token_cache

        with patch("keyring.set_password") as mock_set, \
             patch("keyring.get_password") as mock_get:
            token_cache.save_token("my-srv", "access123", "refresh456", expires_in=3600)
            # Capture what was saved
            saved_payload = mock_set.call_args[0][2]

            # Simulate get_password returning it
            mock_get.return_value = saved_payload
            token = token_cache.get_token("my-srv")
            assert token == "access123"

    def test_expired_token_returns_none(self) -> None:
        from devagent.mcp.auth import token_cache

        payload = json.dumps({
            "access_token": "old",
            "refresh_token": "",
            "expires_at": time.time() - 10,  # already expired
        })
        with patch("keyring.get_password", return_value=payload):
            token = token_cache.get_token("srv")
            assert token is None

    def test_missing_token_returns_none(self) -> None:
        from devagent.mcp.auth import token_cache

        with patch("keyring.get_password", return_value=None):
            assert token_cache.get_token("srv") is None

    def test_clear_token(self) -> None:
        from devagent.mcp.auth import token_cache

        with patch("keyring.delete_password") as mock_del:
            token_cache.clear_token("srv")
            mock_del.assert_called_once_with("devagent-mcp", "srv")

    def test_get_refresh_token(self) -> None:
        from devagent.mcp.auth import token_cache

        payload = json.dumps({
            "access_token": "acc",
            "refresh_token": "ref123",
            "expires_at": time.time() + 3600,
        })
        with patch("keyring.get_password", return_value=payload):
            rt = token_cache.get_refresh_token("srv")
            assert rt == "ref123"

    def test_malformed_payload_returns_none(self) -> None:
        from devagent.mcp.auth import token_cache

        with patch("keyring.get_password", return_value="not-json"):
            assert token_cache.get_token("srv") is None

    def test_no_keyring_returns_none(self) -> None:
        """When keyring import fails, all ops return None silently."""
        from devagent.mcp.auth import token_cache

        with patch.object(token_cache, "_keyring", return_value=None):
            assert token_cache.get_token("x") is None
            token_cache.save_token("x", "a", "b", 3600)  # no error
            token_cache.clear_token("x")  # no error


# ---------------------------------------------------------------------------
# OAuthConfig dataclass
# ---------------------------------------------------------------------------

class TestOAuthConfig:
    def test_basic_fields(self) -> None:
        from devagent.mcp.project_config import OAuthConfig
        cfg = OAuthConfig(
            authorization_url="https://auth.example.com/authorize",
            token_url="https://auth.example.com/token",
            client_id="devagent",
            scopes=["mcp.read"],
        )
        assert cfg.type == "oauth2"
        assert cfg.scopes == ["mcp.read"]

    def test_to_dict(self) -> None:
        from devagent.mcp.project_config import OAuthConfig
        cfg = OAuthConfig(
            authorization_url="https://a.com/auth",
            token_url="https://a.com/token",
            client_id="cli",
            scopes=["read", "write"],
        )
        d = cfg.to_dict()
        assert d["authorization_url"] == "https://a.com/auth"
        assert d["scopes"] == ["read", "write"]
        assert d["type"] == "oauth2"


# ---------------------------------------------------------------------------
# MCPServerEntry.auth field
# ---------------------------------------------------------------------------

class TestMCPServerEntryAuth:
    def test_default_auth_is_none(self) -> None:
        from devagent.mcp.project_config import MCPServerEntry
        e = MCPServerEntry(name="x", command="python")
        assert e.auth is None

    def test_to_dict_includes_auth(self) -> None:
        from devagent.mcp.project_config import MCPServerEntry, OAuthConfig
        e = MCPServerEntry(
            name="x",
            command="python",
            auth=OAuthConfig(
                authorization_url="https://a.com/auth",
                token_url="https://a.com/token",
                client_id="cli",
            ),
        )
        d = e.to_dict()
        assert "auth" in d
        assert d["auth"]["client_id"] == "cli"

    def test_to_dict_omits_auth_when_none(self) -> None:
        from devagent.mcp.project_config import MCPServerEntry
        e = MCPServerEntry(name="x", command="python")
        assert "auth" not in e.to_dict()


# ---------------------------------------------------------------------------
# load_mcp_json — parsing auth section
# ---------------------------------------------------------------------------

class TestLoadMcpJsonAuth:
    def _write(self, tmp_path: Path, data: dict) -> None:
        (tmp_path / ".mcp.json").write_text(json.dumps(data), encoding="utf-8")

    def test_parses_oauth_section(self, tmp_path) -> None:
        from devagent.mcp.project_config import load_mcp_json
        self._write(tmp_path, {"mcpServers": {
            "srv": {
                "command": "python",
                "auth": {
                    "type": "oauth2",
                    "authorization_url": "https://auth.example.com/authorize",
                    "token_url": "https://auth.example.com/token",
                    "client_id": "devagent",
                    "scopes": ["mcp.read"],
                },
            }
        }})
        entries = load_mcp_json(tmp_path)
        assert len(entries) == 1
        assert entries[0].auth is not None
        assert entries[0].auth.client_id == "devagent"
        assert entries[0].auth.scopes == ["mcp.read"]

    def test_no_auth_section_gives_none(self, tmp_path) -> None:
        from devagent.mcp.project_config import load_mcp_json
        self._write(tmp_path, {"mcpServers": {
            "srv": {"command": "python"}
        }})
        entries = load_mcp_json(tmp_path)
        assert entries[0].auth is None

    def test_incomplete_auth_section_ignored(self, tmp_path) -> None:
        from devagent.mcp.project_config import load_mcp_json
        self._write(tmp_path, {"mcpServers": {
            "srv": {
                "command": "python",
                "auth": {"type": "oauth2", "client_id": "no-urls"},
            }
        }})
        entries = load_mcp_json(tmp_path)
        # missing authorization_url and token_url → auth not parsed
        assert entries[0].auth is None

    def test_round_trip_auth(self, tmp_path) -> None:
        from devagent.mcp.project_config import (
            MCPServerEntry,
            OAuthConfig,
            load_mcp_json,
            save_mcp_json,
        )
        entry = MCPServerEntry(
            name="srv",
            command="python",
            auth=OAuthConfig(
                authorization_url="https://a.com/auth",
                token_url="https://a.com/token",
                client_id="cli",
                scopes=["read"],
            ),
        )
        save_mcp_json(tmp_path, [entry])
        loaded = load_mcp_json(tmp_path)
        assert loaded[0].auth is not None
        assert loaded[0].auth.authorization_url == "https://a.com/auth"
        assert loaded[0].auth.scopes == ["read"]
