"""Map security event payloads to canonical CICIDS2017 feature dictionaries."""
from __future__ import annotations

from typing import Any

from app.ml.features import CICIDS2017_FEATURES

# Aliases used by agents, log shippers, or shorthand JSON keys.
FEATURE_ALIASES: dict[str, str] = {
    "dst_port": "destination_port",
    "dest_port": "destination_port",
    "dport": "destination_port",
    "src_port": "source_port",  # not in CICIDS vector but kept for future enrichment
    "flow_duration_us": "flow_duration",
    "packets_per_sec": "flow_packets_per_sec",
    "bytes_per_sec": "flow_bytes_per_sec",
    "syn_count": "syn_flag_count",
    "ack_count": "ack_flag_count",
    "fwd_packets": "total_fwd_packets",
    "bwd_packets": "total_bwd_packets",
}

# Nested payload keys some integrations use.
NESTED_KEYS = ("network_features", "flow_features", "cicids_features", "features")


def extract_network_features(payload: dict[str, Any] | None) -> dict[str, float]:
    """
    Flatten event payload into canonical feature names.

    Only keys that map to ``CICIDS2017_FEATURES`` are returned; unknown keys are ignored
    so extra metadata does not break ingestion.
    """
    if not payload:
        return {}

    merged: dict[str, Any] = {}
    for nest in NESTED_KEYS:
        block = payload.get(nest)
        if isinstance(block, dict):
            merged.update(block)
    merged.update(payload)

    canonical = set(CICIDS2017_FEATURES)
    out: dict[str, float] = {}
    for key, value in merged.items():
        target = FEATURE_ALIASES.get(key, key)
        if target not in canonical:
            continue
        if value is None:
            continue
        try:
            out[target] = float(value)
        except (TypeError, ValueError):
            continue
    return out
