from __future__ import annotations

import argparse
import sys

from .app import CWMApp
from .config import ConfigError, load_settings
from .logging_setup import configure_logging
from .oauth import OAuthConfig, browser_login, load_stored_token


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="ConnectWise Manage Textual TUI")
    parser.add_argument("--config", help="Path to JSON config file", default=None)
    parser.add_argument("--login", action="store_true", help="Launch browser for OAuth SSO login")
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    try:
        settings = load_settings(args.config)
    except ConfigError as exc:
        print(str(exc), file=sys.stderr)
        return 2

    log_path = configure_logging(settings)
    print(f"cwm log: {log_path}", file=sys.stderr)

    if args.login:
        if not settings.has_oauth:
            print(
                "OAuth not configured. Set CWM_OAUTH_AUTH_URL, CWM_OAUTH_TOKEN_URL, "
                "and CWM_OAUTH_CLIENT_ID.",
                file=sys.stderr,
            )
            return 2
        oauth_config = OAuthConfig(
            auth_url=settings.oauth_auth_url,
            token_url=settings.oauth_token_url,
            client_id=settings.oauth_client_id,
            client_secret=settings.oauth_client_secret,
            scopes=settings.oauth_scopes,
        )
        try:
            browser_login(oauth_config)
            return 0
        except RuntimeError as exc:
            print(f"Login failed: {exc}", file=sys.stderr)
            return 1

    token = None
    if settings.has_oauth:
        token = load_stored_token()
        if token is None:
            print(
                "OAuth configured but no token found. Run 'cwm --login' first.",
                file=sys.stderr,
            )
            return 2

    app = CWMApp(settings, token=token)
    app.run()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
