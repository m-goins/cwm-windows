from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

from .config import Settings


def configure_logging(settings: Settings) -> Path:
    log_path = Path(settings.log_path).expanduser()
    log_path.parent.mkdir(parents=True, exist_ok=True)

    logger = logging.getLogger("cwm")
    logger.handlers.clear()
    logger.setLevel(getattr(logging, settings.log_level.upper(), logging.DEBUG))
    logger.propagate = False

    handler = RotatingFileHandler(log_path, maxBytes=5_000_000, backupCount=3)
    handler.setFormatter(
        logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s")
    )
    logger.addHandler(handler)

    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)

    logger.debug("Logging initialized at %s level=%s", log_path, settings.log_level)
    return log_path
