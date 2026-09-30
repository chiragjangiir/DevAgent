"""Keyring-based token cache for MCP OAuth credentials.

Stores { access_token, refresh_token, expires_at } as JSON in the platform
keyring under service "devagent-mcp" with the MCP server name as the username.

Falls back gracefully when keyring is unavailable (e.g. CI, headless envs).
"""

from __future__ import annotations

import json
import time
from typing import Any

_SERVICE = "devagent-mcp"
# Buffer: refresh 60 s before expiry so callers always get a valid token
_EXPIRY_BUFFER = 60


def _keyring():  # type: ignore[return]
    try:
        import keyring
        return keyring
    except ImportError:
        return None


def save_token(
    server_name: str,
    access_token: str,
    refresh_token: str = "",
    expires_in: int = 3600,
) -> None:
    """Persist OAuth tokens to the platform keyring."""
    kr = _keyring()
    if kr is None:
        return
    payload = json.dumps({
        "access_token": access_token,
        "refresh_token": refresh_token,
        "expires_at": time.time() + expires_in,
    })
    kr.set_password(_SERVICE, server_name, payload)


def get_token(server_name: str) -> str | None:
    """Return a valid (non-expired) access token, or None if absent/expired."""
    kr = _keyring()
    if kr is None:
        return None
    raw = kr.get_password(_SERVICE, server_name)
    if not raw:
        return None
    try:
        data: dict[str, Any] = json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return None
    expires_at = data.get("expires_at", 0)
    if time.time() >= expires_at - _EXPIRY_BUFFER:
        return None
    return data.get("access_token") or None


def get_refresh_token(server_name: str) -> str | None:
    """Return the stored refresh token, or None."""
    kr = _keyring()
    if kr is None:
        return None
    raw = kr.get_password(_SERVICE, server_name)
    if not raw:
        return None
    try:
        data: dict[str, Any] = json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return None
    return data.get("refresh_token") or None


def clear_token(server_name: str) -> None:
    """Remove stored tokens for a server from the keyring."""
    kr = _keyring()
    if kr is None:
        return
    try:
        kr.delete_password(_SERVICE, server_name)
    except Exception:
        pass
