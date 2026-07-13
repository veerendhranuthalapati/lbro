"""
app/core/config.py — compatibility shim.

All files have been updated to import directly from app.config.
This shim is retained in case any third-party or legacy code still
imports from app.core.config.
"""
from app.config import Settings, get_settings, settings  # noqa: F401

__all__ = ["settings", "Settings", "get_settings"]
