from __future__ import annotations

import argparse
import sys

from .app import CWMApp
from .config import ConfigError, load_settings
from .logging_setup import configure_logging


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="ConnectWise Manage Textual TUI")
    parser.add_argument("--config", help="Path to JSON config file", default=None)
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
    app = CWMApp(settings)
    app.run()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
