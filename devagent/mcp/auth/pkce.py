"""OAuth 2.0 PKCE flow for MCP server authentication.

Implements the full PKCE authorization code flow:
  1. Generate code_verifier + code_challenge
  2. Start a local redirect-capture server
  3. Open the browser at the authorization URL
  4. Wait for the redirect callback containing ?code=...
  5. Exchange the code for access + refresh tokens via POST
  6. Return the token response dict

Usage:
    from devagent.mcp.auth.pkce import pkce_authorize
    tokens = pkce_authorize(
        authorization_url="https://auth.example.com/authorize",
        token_url="https://auth.example.com/token",
        client_id="devagent",
        scopes=["mcp.read"],
    )
    access_token = tokens["access_token"]
"""

from __future__ import annotations

import base64
import hashlib
import http.server
import json
import secrets
import threading
import urllib.parse
import urllib.request
import webbrowser
from dataclasses import dataclass, field
from typing import Any

_REDIRECT_HTML = b"""<!doctype html>
<html><body>
<p>Authorization complete. You can close this window.</p>
<script>window.close();</script>
</body></html>"""


# ---------------------------------------------------------------------------
# PKCE primitives
# ---------------------------------------------------------------------------

def generate_code_verifier(length: int = 64) -> str:
    """Generate a cryptographically random PKCE code_verifier (43-128 chars)."""
    if not 43 <= length <= 128:
        raise ValueError(f"code_verifier length must be 43-128, got {length}")
    return secrets.token_urlsafe(length)[:length]


def compute_code_challenge(verifier: str) -> str:
    """Compute SHA-256 code_challenge from code_verifier (base64url, no padding)."""
    digest = hashlib.sha256(verifier.encode()).digest()
    return base64.urlsafe_b64encode(digest).rstrip(b"=").decode()


# ---------------------------------------------------------------------------
# Local redirect capture server
# ---------------------------------------------------------------------------

@dataclass
class _CallbackResult:
    code: str = ""
    error: str = ""
    done: threading.Event = field(default_factory=threading.Event)


def _make_handler(result: _CallbackResult):  # type: ignore[return]
    class _Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            parsed = urllib.parse.urlparse(self.path)
            params = dict(urllib.parse.parse_qsl(parsed.query))
            result.code = params.get("code", "")
            result.error = params.get("error", "")
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.end_headers()
            self.wfile.write(_REDIRECT_HTML)
            result.done.set()

        def log_message(self, fmt: str, *args: object) -> None:
            pass  # suppress request logs

    return _Handler


def _start_callback_server(port: int) -> tuple[http.server.HTTPServer, _CallbackResult]:
    result = _CallbackResult()
    server = http.server.HTTPServer(("127.0.0.1", port), _make_handler(result))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server, result


def _find_free_port() -> int:
    import socket
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


# ---------------------------------------------------------------------------
# Token exchange
# ---------------------------------------------------------------------------

def _exchange_code(
    token_url: str,
    client_id: str,
    code: str,
    verifier: str,
    redirect_uri: str,
) -> dict[str, Any]:
    """POST code + verifier to the token endpoint; return the JSON response."""
    payload = urllib.parse.urlencode({
        "grant_type": "authorization_code",
        "client_id": client_id,
        "code": code,
        "code_verifier": verifier,
        "redirect_uri": redirect_uri,
    }).encode()
    req = urllib.request.Request(
        token_url,
        data=payload,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode())


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def pkce_authorize(
    authorization_url: str,
    token_url: str,
    client_id: str,
    scopes: list[str],
    timeout: float = 120.0,
) -> dict[str, Any]:
    """Run the full PKCE authorization-code flow.

    Opens the system browser at the authorization URL, waits for the redirect
    callback (up to *timeout* seconds), exchanges the code for tokens, and
    returns the raw token endpoint response.

    Raises RuntimeError on timeout, OAuth error, or token exchange failure.
    """
    verifier = generate_code_verifier()
    challenge = compute_code_challenge(verifier)
    port = _find_free_port()
    redirect_uri = f"http://127.0.0.1:{port}/callback"

    params = {
        "response_type": "code",
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "scope": " ".join(scopes),
        "code_challenge": challenge,
        "code_challenge_method": "S256",
        "state": secrets.token_urlsafe(16),
    }
    auth_url = f"{authorization_url}?{urllib.parse.urlencode(params)}"

    server, result = _start_callback_server(port)
    try:
        webbrowser.open(auth_url)
        if not result.done.wait(timeout=timeout):
            raise RuntimeError(f"OAuth flow timed out after {timeout}s")
        if result.error:
            raise RuntimeError(f"OAuth authorization error: {result.error}")
        return _exchange_code(token_url, client_id, result.code, verifier, redirect_uri)
    finally:
        server.shutdown()


def refresh_token_flow(
    token_url: str,
    client_id: str,
    refresh_token: str,
) -> dict[str, Any]:
    """Exchange a refresh token for a new access token."""
    payload = urllib.parse.urlencode({
        "grant_type": "refresh_token",
        "client_id": client_id,
        "refresh_token": refresh_token,
    }).encode()
    req = urllib.request.Request(
        token_url,
        data=payload,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode())
