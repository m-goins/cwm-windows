from __future__ import annotations

import http.server
import json
import logging
import socket
import time
import urllib.parse
import webbrowser
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import httpx

logger = logging.getLogger("cwm.oauth")

TOKEN_DIR = Path.home() / ".local" / "state" / "cwm"
TOKEN_FILE = TOKEN_DIR / "token.json"


@dataclass(slots=True)
class OAuthConfig:
    auth_url: str
    token_url: str
    client_id: str
    client_secret: str
    scopes: str


@dataclass(slots=True)
class TokenData:
    access_token: str
    refresh_token: str | None
    expires_at: float
    token_type: str


def load_stored_token() -> TokenData | None:
    if not TOKEN_FILE.exists():
        return None
    try:
        data = json.loads(TOKEN_FILE.read_text())
        return TokenData(
            access_token=data["access_token"],
            refresh_token=data.get("refresh_token"),
            expires_at=float(data.get("expires_at", 0)),
            token_type=data.get("token_type", "Bearer"),
        )
    except (json.JSONDecodeError, KeyError, ValueError) as exc:
        logger.warning("Failed to load stored token: %s", exc)
        return None


def save_token(token: TokenData) -> None:
    TOKEN_DIR.mkdir(parents=True, exist_ok=True)
    TOKEN_FILE.write_text(json.dumps({
        "access_token": token.access_token,
        "refresh_token": token.refresh_token,
        "expires_at": token.expires_at,
        "token_type": token.token_type,
    }))
    TOKEN_FILE.chmod(0o600)
    logger.info("Token saved to %s", TOKEN_FILE)


def is_token_expired(token: TokenData, buffer_seconds: int = 60) -> bool:
    return time.time() >= (token.expires_at - buffer_seconds)


def _parse_token_response(result: dict[str, Any]) -> TokenData:
    expires_in = int(result.get("expires_in", 3600))
    return TokenData(
        access_token=result["access_token"],
        refresh_token=result.get("refresh_token"),
        expires_at=time.time() + expires_in,
        token_type=result.get("token_type", "Bearer"),
    )


class _CallbackHandler(http.server.BaseHTTPRequestHandler):
    auth_code: str | None = None
    error: str | None = None

    def do_GET(self) -> None:
        parsed = urllib.parse.urlparse(self.path)
        params = urllib.parse.parse_qs(parsed.query)

        if "code" in params:
            _CallbackHandler.auth_code = params["code"][0]
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.end_headers()
            self.wfile.write(b"<h2>Authentication successful</h2><p>You can close this tab and return to the terminal.</p>")
        elif "error" in params:
            desc = params.get("error_description", params["error"])
            _CallbackHandler.error = desc[0] if isinstance(desc, list) else str(desc)
            self.send_response(400)
            self.send_header("Content-Type", "text/html")
            self.end_headers()
            self.wfile.write(f"<h2>Authentication failed</h2><p>{_CallbackHandler.error}</p>".encode())
        else:
            self.send_response(400)
            self.send_header("Content-Type", "text/html")
            self.end_headers()
            self.wfile.write(b"<h2>Missing authorization code</h2>")

    def log_message(self, format: str, *args: Any) -> None:
        logger.debug(format, *args)


def _find_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def browser_login(config: OAuthConfig) -> TokenData:
    """Launch browser for OAuth authorization code flow."""
    port = _find_free_port()
    redirect_uri = f"http://localhost:{port}/callback"

    auth_params: dict[str, str] = {
        "response_type": "code",
        "client_id": config.client_id,
        "redirect_uri": redirect_uri,
    }
    if config.scopes:
        auth_params["scope"] = config.scopes

    auth_url = f"{config.auth_url}?{urllib.parse.urlencode(auth_params)}"

    _CallbackHandler.auth_code = None
    _CallbackHandler.error = None

    server = http.server.HTTPServer(("127.0.0.1", port), _CallbackHandler)
    server.timeout = 120

    print(f"Opening browser for authentication...")
    print(f"Listening on http://localhost:{port}/callback")
    print(f"\nIf the browser doesn't open, visit:\n{auth_url}\n")
    webbrowser.open(auth_url)

    while _CallbackHandler.auth_code is None and _CallbackHandler.error is None:
        server.handle_request()

    server.server_close()

    if _CallbackHandler.error:
        raise RuntimeError(f"OAuth authentication failed: {_CallbackHandler.error}")

    if not _CallbackHandler.auth_code:
        raise RuntimeError("No authorization code received")

    logger.info("Authorization code received, exchanging for token")
    token_data: dict[str, str] = {
        "grant_type": "authorization_code",
        "code": _CallbackHandler.auth_code,
        "redirect_uri": redirect_uri,
        "client_id": config.client_id,
    }
    if config.client_secret:
        token_data["client_secret"] = config.client_secret

    with httpx.Client(timeout=30) as client:
        response = client.post(config.token_url, data=token_data)
        if response.status_code >= 400:
            logger.error("Token exchange failed: %s", response.text)
            raise RuntimeError(f"Token exchange failed (HTTP {response.status_code}): {response.text}")
        result = response.json()

    token = _parse_token_response(result)
    save_token(token)
    print("Authentication successful. Token saved.")
    return token


async def refresh_token_async(config: OAuthConfig, token: TokenData) -> TokenData:
    """Refresh an expired access token."""
    if not token.refresh_token:
        raise RuntimeError("No refresh token available. Run 'cwm --login' to re-authenticate.")

    token_data: dict[str, str] = {
        "grant_type": "refresh_token",
        "refresh_token": token.refresh_token,
        "client_id": config.client_id,
    }
    if config.client_secret:
        token_data["client_secret"] = config.client_secret

    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.post(config.token_url, data=token_data)
        if response.status_code >= 400:
            logger.error("Token refresh failed: %s", response.text)
            raise RuntimeError(f"Token refresh failed (HTTP {response.status_code}). Run 'cwm --login' to re-authenticate.")
        result = response.json()

    new_token = _parse_token_response(result)
    if not new_token.refresh_token:
        new_token.refresh_token = token.refresh_token
    save_token(new_token)
    logger.info("Token refreshed successfully")
    return new_token
