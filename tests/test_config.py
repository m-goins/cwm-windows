from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from cwm.config import ConfigError, Settings, _company_from_auth_prefix, _first_nonempty, _parse_bool, load_settings


class TestFirstNonempty:
    def test_returns_first_value(self) -> None:
        assert _first_nonempty("a", "b") == "a"

    def test_skips_none(self) -> None:
        assert _first_nonempty(None, "b") == "b"

    def test_skips_empty(self) -> None:
        assert _first_nonempty("", "  ", "c") == "c"

    def test_all_none(self) -> None:
        assert _first_nonempty(None, None) is None

    def test_strips_whitespace(self) -> None:
        assert _first_nonempty("  hello  ") == "hello"


class TestParseBool:
    @pytest.mark.parametrize("value", ["1", "true", "True", "yes", "on"])
    def test_truthy(self, value: str) -> None:
        assert _parse_bool(value) is True

    @pytest.mark.parametrize("value", ["0", "false", "False", "no", "off"])
    def test_falsy(self, value: str) -> None:
        assert _parse_bool(value) is False

    def test_none_returns_default(self) -> None:
        assert _parse_bool(None, default=False) is False
        assert _parse_bool(None, default=True) is True

    def test_unknown_returns_default(self) -> None:
        assert _parse_bool("maybe", default=False) is False


class TestCompanyFromAuthPrefix:
    def test_none(self) -> None:
        assert _company_from_auth_prefix(None) is None

    def test_with_plus(self) -> None:
        assert _company_from_auth_prefix("acme+") == "acme"

    def test_without_plus(self) -> None:
        assert _company_from_auth_prefix("acme") == "acme"

    def test_empty(self) -> None:
        assert _company_from_auth_prefix("") is None

    def test_just_plus(self) -> None:
        assert _company_from_auth_prefix("+") is None


class TestLoadSettings:
    REQUIRED_ENV = {
        "CWM_BASE_URL": "https://api.example.com",
        "CWM_COMPANY_ID": "testco",
        "CWM_PUBLIC_KEY": "pub123",
        "CWM_PRIVATE_KEY": "priv456",
        "CWM_CLIENT_ID": "client789",
    }

    def test_from_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        for key, value in self.REQUIRED_ENV.items():
            monkeypatch.setenv(key, value)
        settings = load_settings()
        assert settings.base_url == "https://api.example.com"
        assert settings.company_id == "testco"
        assert settings.public_key == "pub123"
        assert settings.private_key == "priv456"
        assert settings.client_id == "client789"

    def test_missing_required_raises(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("CWM_BASE_URL", "https://api.example.com")
        for key in self.REQUIRED_ENV:
            monkeypatch.delenv(key, raising=False)
        monkeypatch.setenv("CWM_BASE_URL", "https://api.example.com")
        with pytest.raises(ConfigError, match="Missing required"):
            load_settings()

    def test_from_json_config(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        for key in self.REQUIRED_ENV:
            monkeypatch.delenv(key, raising=False)
        config = {
            "CWM_BASE_URL": "https://json.example.com",
            "CWM_COMPANY_ID": "jsonco",
            "CWM_PUBLIC_KEY": "jpub",
            "CWM_PRIVATE_KEY": "jpriv",
            "CWM_CLIENT_ID": "jclient",
        }
        config_file = tmp_path / "config.json"
        config_file.write_text(json.dumps(config))
        settings = load_settings(str(config_file))
        assert settings.base_url == "https://json.example.com"
        assert settings.company_id == "jsonco"

    def test_env_overrides_json(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        config = {
            "CWM_BASE_URL": "https://json.example.com",
            "CWM_COMPANY_ID": "jsonco",
            "CWM_PUBLIC_KEY": "jpub",
            "CWM_PRIVATE_KEY": "jpriv",
            "CWM_CLIENT_ID": "jclient",
        }
        config_file = tmp_path / "config.json"
        config_file.write_text(json.dumps(config))
        for key in self.REQUIRED_ENV:
            monkeypatch.delenv(key, raising=False)
        monkeypatch.setenv("CWM_BASE_URL", "https://env.example.com")
        settings = load_settings(str(config_file))
        assert settings.base_url == "https://env.example.com"

    def test_trailing_slash_stripped(self, monkeypatch: pytest.MonkeyPatch) -> None:
        for key, value in self.REQUIRED_ENV.items():
            monkeypatch.setenv(key, value)
        monkeypatch.setenv("CWM_BASE_URL", "https://api.example.com/")
        settings = load_settings()
        assert settings.base_url == "https://api.example.com"

    def test_legacy_cw_vars(self, monkeypatch: pytest.MonkeyPatch) -> None:
        for key in self.REQUIRED_ENV:
            monkeypatch.delenv(key, raising=False)
        monkeypatch.setenv("CW_BASE_URL", "https://cw.example.com")
        monkeypatch.setenv("CW_COMPANY_ID", "cwco")
        monkeypatch.setenv("CW_PUBLIC_KEY", "cwpub")
        monkeypatch.setenv("CW_PRIVATE_KEY", "cwpriv")
        monkeypatch.setenv("CW_CLIENT_ID", "cwclient")
        settings = load_settings()
        assert settings.base_url == "https://cw.example.com"
        assert settings.company_id == "cwco"

    def test_invalid_json_raises(self, tmp_path: Path) -> None:
        config_file = tmp_path / "bad.json"
        config_file.write_text("{invalid")
        with pytest.raises(ConfigError, match="Invalid JSON"):
            load_settings(str(config_file))

    def test_verify_ssl_default_true(self, monkeypatch: pytest.MonkeyPatch) -> None:
        for key, value in self.REQUIRED_ENV.items():
            monkeypatch.setenv(key, value)
        settings = load_settings()
        assert settings.verify_ssl is True

    def test_verify_ssl_false(self, monkeypatch: pytest.MonkeyPatch) -> None:
        for key, value in self.REQUIRED_ENV.items():
            monkeypatch.setenv(key, value)
        monkeypatch.setenv("CWM_VERIFY_SSL", "false")
        settings = load_settings()
        assert settings.verify_ssl is False

    def test_refresh_interval_default_zero(self, monkeypatch: pytest.MonkeyPatch) -> None:
        for key, value in self.REQUIRED_ENV.items():
            monkeypatch.setenv(key, value)
        settings = load_settings()
        assert settings.refresh_interval_seconds == 0

    def test_refresh_interval_from_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        for key, value in self.REQUIRED_ENV.items():
            monkeypatch.setenv(key, value)
        monkeypatch.setenv("CWM_REFRESH_INTERVAL", "120")
        settings = load_settings()
        assert settings.refresh_interval_seconds == 120

    def test_refresh_interval_invalid_defaults_zero(self, monkeypatch: pytest.MonkeyPatch) -> None:
        for key, value in self.REQUIRED_ENV.items():
            monkeypatch.setenv(key, value)
        monkeypatch.setenv("CWM_REFRESH_INTERVAL", "abc")
        settings = load_settings()
        assert settings.refresh_interval_seconds == 0

    def test_columns_default(self, monkeypatch: pytest.MonkeyPatch) -> None:
        for key, value in self.REQUIRED_ENV.items():
            monkeypatch.setenv(key, value)
        settings = load_settings()
        assert settings.columns == [
            "opened", "id", "pri", "age", "status", "company", "summary", "tech", "contact", "sla", "updated",
        ]

    def test_columns_custom_order(self, monkeypatch: pytest.MonkeyPatch) -> None:
        for key, value in self.REQUIRED_ENV.items():
            monkeypatch.setenv(key, value)
        monkeypatch.setenv("CWM_COLUMNS", "id,company,summary,status,tech")
        settings = load_settings()
        assert settings.columns == ["id", "company", "summary", "status", "tech"]

    def test_columns_invalid_ignored(self, monkeypatch: pytest.MonkeyPatch) -> None:
        for key, value in self.REQUIRED_ENV.items():
            monkeypatch.setenv(key, value)
        monkeypatch.setenv("CWM_COLUMNS", "id,bogus,summary,fake")
        settings = load_settings()
        assert settings.columns == ["id", "summary"]

    def test_columns_all_invalid_falls_back_to_default(self, monkeypatch: pytest.MonkeyPatch) -> None:
        for key, value in self.REQUIRED_ENV.items():
            monkeypatch.setenv(key, value)
        monkeypatch.setenv("CWM_COLUMNS", "bogus,fake")
        settings = load_settings()
        assert len(settings.columns) == 11

    def test_connectwise_auth_prefix_extracts_company(self, monkeypatch: pytest.MonkeyPatch) -> None:
        for key in self.REQUIRED_ENV:
            monkeypatch.delenv(key, raising=False)
        monkeypatch.setenv("CONNECTWISE_AUTH_PREFIX", "prefixco+")
        monkeypatch.setenv("CWM_BASE_URL", "https://api.example.com")
        monkeypatch.setenv("CWM_PUBLIC_KEY", "pub")
        monkeypatch.setenv("CWM_PRIVATE_KEY", "priv")
        monkeypatch.setenv("CWM_CLIENT_ID", "client")
        settings = load_settings()
        assert settings.company_id == "prefixco"
