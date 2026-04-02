from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


class ConfigError(RuntimeError):
    """Raised when required config is missing or invalid."""


@dataclass(slots=True)
class Settings:
    base_url: str
    company_id: str
    public_key: str
    private_key: str
    client_id: str
    member_identifier: str | None = None
    verify_ssl: bool = True
    timeout_seconds: float = 30.0
    log_path: str = str(Path.home() / ".local" / "state" / "cwm" / "cwm.log")
    log_level: str = "DEBUG"
    refresh_interval_seconds: int = 0
    columns: list[str] = field(default_factory=lambda: [
        "opened", "id", "pri", "age", "status", "company", "summary", "tech", "contact", "sla", "updated",
    ])
    oauth_auth_url: str = ""
    oauth_token_url: str = ""
    oauth_client_id: str = ""
    oauth_client_secret: str = ""
    oauth_scopes: str = ""

    @property
    def has_oauth(self) -> bool:
        return bool(self.oauth_auth_url and self.oauth_token_url and self.oauth_client_id)

    @property
    def has_api_keys(self) -> bool:
        return bool(self.public_key and self.private_key)

    @property
    def masked_summary(self) -> str:
        auth_mode = "oauth" if self.has_oauth else "api-keys"
        return f"{self.base_url} as {self.company_id} ({auth_mode})"


def _read_json_config(path: Path | None) -> dict[str, Any]:
    if path is None or not path.exists():
        return {}
    try:
        return json.loads(path.read_text())
    except json.JSONDecodeError as exc:
        raise ConfigError(f"Invalid JSON config at {path}: {exc}") from exc


def _first_nonempty(*values: Any) -> str | None:
    for value in values:
        if value is None:
            continue
        text = str(value).strip()
        if text:
            return text
    return None


def _parse_bool(value: Any, default: bool = True) -> bool:
    if value is None:
        return default
    text = str(value).strip().lower()
    if text in {"1", "true", "yes", "on"}:
        return True
    if text in {"0", "false", "no", "off"}:
        return False
    return default


def _company_from_auth_prefix(prefix: str | None) -> str | None:
    if not prefix:
        return None
    cleaned = prefix.strip()
    if cleaned.endswith("+"):
        cleaned = cleaned[:-1]
    return cleaned or None


def load_settings(config_path: str | None = None) -> Settings:
    path = Path(config_path).expanduser() if config_path else None
    file_config = _read_json_config(path)

    env = os.environ
    auth_prefix = _first_nonempty(
        env.get("CONNECTWISE_AUTH_PREFIX"),
        file_config.get("CONNECTWISE_AUTH_PREFIX"),
    )

    base_url = _first_nonempty(
        env.get("CWM_BASE_URL"),
        env.get("CW_BASE_URL"),
        env.get("CW_URL"),
        env.get("CONNECTWISE_API_URL"),
        file_config.get("CWM_BASE_URL"),
        file_config.get("CW_BASE_URL"),
        file_config.get("CW_URL"),
        file_config.get("CONNECTWISE_API_URL"),
        file_config.get("base_url"),
        file_config.get("url"),
    )
    company_id = _first_nonempty(
        env.get("CWM_COMPANY_ID"),
        env.get("CW_COMPANY_ID"),
        file_config.get("CWM_COMPANY_ID"),
        file_config.get("CW_COMPANY_ID"),
        file_config.get("company_id"),
        _company_from_auth_prefix(auth_prefix),
        env.get("CONNECTWISE_COMPANY_ID"),
        file_config.get("CONNECTWISE_COMPANY_ID"),
    )
    public_key = _first_nonempty(
        env.get("CWM_PUBLIC_KEY"),
        env.get("CW_PUBLIC_KEY"),
        env.get("CONNECTWISE_PUBLIC_KEY"),
        file_config.get("CWM_PUBLIC_KEY"),
        file_config.get("CW_PUBLIC_KEY"),
        file_config.get("CONNECTWISE_PUBLIC_KEY"),
        file_config.get("public_key"),
    )
    private_key = _first_nonempty(
        env.get("CWM_PRIVATE_KEY"),
        env.get("CW_PRIVATE_KEY"),
        env.get("CONNECTWISE_PRIVATE_KEY"),
        file_config.get("CWM_PRIVATE_KEY"),
        file_config.get("CW_PRIVATE_KEY"),
        file_config.get("CONNECTWISE_PRIVATE_KEY"),
        file_config.get("private_key"),
    )
    client_id = _first_nonempty(
        env.get("CWM_CLIENT_ID"),
        env.get("CW_CLIENT_ID"),
        env.get("CONNECTWISE_CLIENT_ID"),
        file_config.get("CWM_CLIENT_ID"),
        file_config.get("CW_CLIENT_ID"),
        file_config.get("CONNECTWISE_CLIENT_ID"),
        file_config.get("client_id"),
    )
    member_identifier = _first_nonempty(
        env.get("CWM_MEMBER_IDENTIFIER"),
        env.get("CW_MEMBER_IDENTIFIER"),
        file_config.get("CWM_MEMBER_IDENTIFIER"),
        file_config.get("CW_MEMBER_IDENTIFIER"),
        file_config.get("member_identifier"),
    )
    verify_ssl = _parse_bool(
        _first_nonempty(
            env.get("CWM_VERIFY_SSL"),
            env.get("CW_VERIFY_SSL"),
            file_config.get("CWM_VERIFY_SSL"),
            file_config.get("CW_VERIFY_SSL"),
            file_config.get("verify_ssl"),
        ),
        default=True,
    )
    log_path = _first_nonempty(
        env.get("CWM_LOG_PATH"),
        file_config.get("CWM_LOG_PATH"),
        file_config.get("log_path"),
    ) or str(Path.home() / ".local" / "state" / "cwm" / "cwm.log")
    log_level = _first_nonempty(
        env.get("CWM_LOG_LEVEL"),
        file_config.get("CWM_LOG_LEVEL"),
        file_config.get("log_level"),
    ) or "DEBUG"
    refresh_interval_text = _first_nonempty(
        env.get("CWM_REFRESH_INTERVAL"),
        file_config.get("CWM_REFRESH_INTERVAL"),
        file_config.get("refresh_interval"),
    ) or "0"
    try:
        refresh_interval = max(0, int(refresh_interval_text))
    except ValueError:
        refresh_interval = 0

    default_columns = ["opened", "id", "pri", "age", "status", "company", "summary", "tech", "contact", "sla", "updated"]
    valid_columns = set(default_columns)
    columns_raw = _first_nonempty(
        env.get("CWM_COLUMNS"),
        file_config.get("CWM_COLUMNS"),
        file_config.get("columns"),
    )
    if columns_raw:
        parsed = [col.strip().lower() for col in columns_raw.split(",") if col.strip()]
        columns = [col for col in parsed if col in valid_columns] or list(default_columns)
    else:
        columns = list(default_columns)

    oauth_auth_url = _first_nonempty(
        env.get("CWM_OAUTH_AUTH_URL"),
        file_config.get("CWM_OAUTH_AUTH_URL"),
        file_config.get("oauth_auth_url"),
    ) or ""
    oauth_token_url = _first_nonempty(
        env.get("CWM_OAUTH_TOKEN_URL"),
        file_config.get("CWM_OAUTH_TOKEN_URL"),
        file_config.get("oauth_token_url"),
    ) or ""
    oauth_client_id = _first_nonempty(
        env.get("CWM_OAUTH_CLIENT_ID"),
        file_config.get("CWM_OAUTH_CLIENT_ID"),
        file_config.get("oauth_client_id"),
    ) or ""
    oauth_client_secret = _first_nonempty(
        env.get("CWM_OAUTH_CLIENT_SECRET"),
        file_config.get("CWM_OAUTH_CLIENT_SECRET"),
        file_config.get("oauth_client_secret"),
    ) or ""
    oauth_scopes = _first_nonempty(
        env.get("CWM_OAUTH_SCOPES"),
        file_config.get("CWM_OAUTH_SCOPES"),
        file_config.get("oauth_scopes"),
    ) or ""

    has_oauth = bool(oauth_auth_url and oauth_token_url and oauth_client_id)
    has_api_keys = bool(public_key and private_key)

    always_required = [
        name
        for name, value in [
            ("base_url", base_url),
            ("company_id", company_id),
            ("client_id", client_id),
        ]
        if not value
    ]
    if always_required:
        raise ConfigError(
            "Missing required ConnectWise config values: "
            + ", ".join(always_required)
            + ". Set CWM_* env vars or use --config."
        )
    if not has_oauth and not has_api_keys:
        raise ConfigError(
            "No authentication configured. Provide CWM_PUBLIC_KEY/CWM_PRIVATE_KEY "
            "for API key auth, or CWM_OAUTH_AUTH_URL/CWM_OAUTH_TOKEN_URL/CWM_OAUTH_CLIENT_ID "
            "for OAuth."
        )

    return Settings(
        base_url=base_url.rstrip("/"),
        company_id=company_id,
        public_key=public_key or "",
        private_key=private_key or "",
        client_id=client_id,
        member_identifier=member_identifier,
        verify_ssl=verify_ssl,
        log_path=log_path,
        log_level=log_level,
        refresh_interval_seconds=refresh_interval,
        columns=columns,
        oauth_auth_url=oauth_auth_url,
        oauth_token_url=oauth_token_url,
        oauth_client_id=oauth_client_id,
        oauth_client_secret=oauth_client_secret,
        oauth_scopes=oauth_scopes,
    )
