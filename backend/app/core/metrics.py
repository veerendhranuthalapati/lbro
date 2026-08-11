"""Shared helpers for metric display — no fabricated percentages."""
from __future__ import annotations

from typing import Optional


def compliance_percentage(met: int, total: int) -> Optional[float]:
    """Return compliance % when total > 0; otherwise None (no data)."""
    if total <= 0:
        return None
    return round(met / total * 100, 2)


def format_compliance_pct(met: int, total: int) -> str:
    pct = compliance_percentage(met, total)
    if pct is None:
        return "N/A"
    return f"{pct:.0f}%"
