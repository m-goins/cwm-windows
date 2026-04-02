from __future__ import annotations

import json
import os
from dataclasses import dataclass
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

    @property
    def masked_summary(self) -> str:
        return f"{self.base_url} as {self.company_id}"


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

    missing = [
        name
        for name, value in [
            ("base_url", base_url),
            ("company_id", company_id),
            ("public_key", public_key),
            ("private_key", private_key),
            ("client_id", client_id),
        ]
        if not value
    ]
    if missing:
        raise ConfigError(
            "Missing required ConnectWise config values: "
            + ", ".join(missing)
            + ". Set CWM_* env vars or use --config."
        )

    return Settings(
        base_url=base_url.rstrip("/"),
        company_id=company_id,
        public_key=public_key,
        private_key=private_key,
        client_id=client_id,
        member_identifier=member_identifier,
        verify_ssl=verify_ssl,
        log_path=log_path,
        log_level=log_level,
        refresh_interval_seconds=refresh_interval,
    )
