"""Demo endpoint production protection."""
from __future__ import annotations

from app.config import Settings


def test_demo_endpoints_disabled_by_default_in_settings():
    """Production default: demo routes must not be enabled unless explicitly configured."""
    from app.config import Settings

    assert Settings.model_fields["DEMO_ENDPOINTS_ENABLED"].default is False
