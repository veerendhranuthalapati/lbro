"""Match incidents to project assets using normalised identifiers (no DB I/O)."""
from __future__ import annotations

import ipaddress
import re
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlparse

MatchConfidence = str  # high | medium | low


@dataclass(frozen=True)
class MatchCandidate:
    asset_id: str
    asset_name: str
    match_reason: str
    match_confidence: MatchConfidence
    auto_accept: bool


def _norm_host(value: str) -> str:
    host = value.strip().lower().rstrip(".")
    return host


def _norm_identifier(value: str) -> str:
    return value.strip().lower()


def collect_incident_match_values(
    *,
    source_ip: str | None,
    destination_ip: str | None,
    title: str | None,
    description: str | None,
    network_features: dict[str, Any] | None,
) -> list[tuple[str, str]]:
    """Return (kind, normalised_value) pairs extracted from incident context."""
    out: list[tuple[str, str]] = []
    for ip in (source_ip, destination_ip):
        if ip:
            out.append(("ip", ip.strip()))
    nf = network_features or {}
    for key in ("source_ip", "destination_ip", "Destination IP", "Source IP"):
        v = nf.get(key)
        if v and isinstance(v, str):
            out.append(("ip", v.strip()))
    if title:
        out.append(("text", title.strip()))
    if description:
        out.append(("text", description.strip()))
    return out


def identifier_matches(
    identifier: dict[str, Any],
    values: Iterable[tuple[str, str]],
) -> MatchCandidate | None:
    """
    Compare one asset identifier entry against incident values.

    Identifier shape: {"type": "hostname"|"ip"|"cidr"|"arn"|"url_host"|"tag"|"application", "value": "..."}
    """
    id_type = str(identifier.get("type", "")).lower()
    raw = str(identifier.get("value", "")).strip()
    if not raw:
        return None

    if id_type in ("hostname", "fqdn", "application"):
        needle = _norm_host(raw)
        for kind, val in values:
            if kind == "text" and needle in _norm_host(val):
                conf = "high" if id_type in ("hostname", "fqdn") else "low"
                return MatchCandidate(
                    asset_id="",
                    asset_name="",
                    match_reason=f"{id_type} substring match: {raw!r} in incident text",
                    match_confidence=conf,
                    auto_accept=conf == "high",
                )
            if kind == "text" and _norm_host(val) == needle:
                return MatchCandidate(
                    asset_id="",
                    asset_name="",
                    match_reason=f"exact host match: {raw!r}",
                    match_confidence="high",
                    auto_accept=True,
                )
        return None

    if id_type == "ip":
        try:
            needle_ip = ipaddress.ip_address(raw)
        except ValueError:
            return None
        for kind, val in values:
            if kind != "ip":
                continue
            try:
                if ipaddress.ip_address(val) == needle_ip:
                    return MatchCandidate(
                        asset_id="",
                        asset_name="",
                        match_reason=f"exact IP match: {raw}",
                        match_confidence="high",
                        auto_accept=True,
                    )
            except ValueError:
                continue
        return None

    if id_type == "cidr":
        try:
            network = ipaddress.ip_network(raw, strict=False)
        except ValueError:
            return None
        for kind, val in values:
            if kind != "ip":
                continue
            try:
                if ipaddress.ip_address(val) in network:
                    return MatchCandidate(
                        asset_id="",
                        asset_name="",
                        match_reason=f"IP {val} within CIDR {raw}",
                        match_confidence="medium",
                        auto_accept=False,
                    )
            except ValueError:
                continue
        return None

    if id_type == "arn":
        pattern = re.escape(raw)
        for kind, val in values:
            if kind == "text" and re.search(pattern, val, re.IGNORECASE):
                return MatchCandidate(
                    asset_id="",
                    asset_name="",
                    match_reason=f"ARN/resource id match: {raw}",
                    match_confidence="high",
                    auto_accept=True,
                )
        return None

    if id_type == "url_host":
        host = _norm_host(urlparse(raw if "://" in raw else f"https://{raw}").hostname or raw)
        for kind, val in values:
            if kind == "text" and host in _norm_host(val):
                return MatchCandidate(
                    asset_id="",
                    asset_name="",
                    match_reason=f"URL host {host} found in incident text",
                    match_confidence="high",
                    auto_accept=True,
                )
        return None

    if id_type == "tag":
        tag = raw.lower()
        for kind, val in values:
            if kind == "text" and tag in val.lower():
                return MatchCandidate(
                    asset_id="",
                    asset_name="",
                    match_reason=f"tag {raw!r} matched incident text",
                    match_confidence="low",
                    auto_accept=False,
                )
        return None

    return None


def match_assets_for_incident(
    assets: list[dict[str, Any]],
    incident_values: list[tuple[str, str]],
) -> list[MatchCandidate]:
    """Return best match per asset (first winning identifier)."""
    results: list[MatchCandidate] = []
    for asset in assets:
        aid = str(asset["id"])
        name = str(asset.get("name", ""))
        for ident in asset.get("identifiers") or []:
            hit = identifier_matches(ident, incident_values)
            if hit:
                results.append(
                    MatchCandidate(
                        asset_id=aid,
                        asset_name=name,
                        match_reason=hit.match_reason,
                        match_confidence=hit.match_confidence,
                        auto_accept=hit.auto_accept,
                    )
                )
                break
    return results
