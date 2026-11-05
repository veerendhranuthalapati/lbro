"""
app/core/logging.py — compatibility shim.

Provides configure_logging() for the API and the workers in app/workers/
without changes.  Delegates to the standard logging module.
"""
from __future__ import annotations

import logging
import sys


def configure_logging(level: str = "INFO", fmt: str = "json") -> None:
    """Configure root logging.  Called once at worker startup."""
    log_level = getattr(logging, level.upper(), logging.INFO)
    handler = logging.StreamHandler(sys.stdout)

    if fmt == "json":
        formatter = logging.Formatter(
            '{"time":"%(asctime)s","level":"%(levelname)s",'
            '"name":"%(name)s","message":"%(message)s"}'
        )
    else:
        formatter = logging.Formatter(
            "%(asctime)s  %(levelname)-8s  %(name)s  %(message)s"
        )

    handler.setFormatter(formatter)
    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(log_level)


__all__ = ["configure_logging"]
