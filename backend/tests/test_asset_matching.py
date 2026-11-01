"""Asset identifier matching unit tests."""
from __future__ import annotations

import time

from app.compliance.matching import (
    collect_incident_match_values,
    identifier_matches,
    match_assets_for_incident,
)


def test_exact_ip_match_high_confidence_auto_accept():
    values = [("ip", "10.0.0.5")]
    hit = identifier_matches({"type": "ip", "value": "10.0.0.5"}, values)
    assert hit and hit.match_confidence == "high" and hit.auto_accept


def test_cidr_containment_medium_not_auto_accept():
    values = [("ip", "192.168.1.44")]
    hit = identifier_matches({"type": "cidr", "value": "192.168.1.0/24"}, values)
    assert hit and hit.match_confidence == "medium" and not hit.auto_accept


def test_fqdn_trailing_dot_normalisation():
    values = collect_incident_match_values(
        source_ip=None,
        destination_ip=None,
        title="Alert on APP.EXAMPLE.COM.",
        description=None,
        network_features=None,
    )
    hit = identifier_matches({"type": "hostname", "value": "app.example.com"}, values)
    assert hit and hit.match_confidence == "high"


def test_low_confidence_name_match_not_auto_accept():
    values = [("text", "marketing portal outage")]
    hit = identifier_matches({"type": "application", "value": "market"}, values)
    assert hit and hit.match_confidence == "low" and not hit.auto_accept


def test_ipv6_equality():
    values = [("ip", "2001:db8::1")]
    hit = identifier_matches({"type": "ip", "value": "2001:db8::1"}, values)
    assert hit and hit.auto_accept


def test_arn_match():
    values = [("text", "arn:aws:s3:::bucket/key")]
    hit = identifier_matches({"type": "arn", "value": "arn:aws:s3:::bucket"}, values)
    assert hit and hit.match_confidence == "high"


def test_url_host_match():
    values = [("text", "exfil to cdn.example.com done")]
    hit = identifier_matches({"type": "url_host", "value": "cdn.example.com"}, values)
    assert hit


def test_tag_low_confidence():
    values = [("text", "env:production tier:web")]
    hit = identifier_matches({"type": "tag", "value": "production"}, values)
    assert hit and not hit.auto_accept


def test_invalid_cidr_returns_none():
    hit = identifier_matches({"type": "cidr", "value": "not-a-cidr"}, [("ip", "10.0.0.1")])
    assert hit is None


def test_collect_incident_network_feature_ips():
    vals = collect_incident_match_values(
        source_ip="1.1.1.1",
        destination_ip=None,
        title=None,
        description=None,
        network_features={"destination_ip": "8.8.8.8"},
    )
    ips = [v for k, v in vals if k == "ip"]
    assert "1.1.1.1" in ips and "8.8.8.8" in ips


def test_match_assets_performance_10k():
    assets = [
        {
            "id": str(i),
            "name": f"asset-{i}",
            "identifiers": [{"type": "ip", "value": f"10.0.{i // 256}.{i % 256}"}],
        }
        for i in range(10_000)
    ]
    assets.append(
        {
            "id": "target",
            "name": "target",
            "identifiers": [{"type": "ip", "value": "203.0.113.50"}],
        }
    )
    values = [("ip", "203.0.113.50")]
    start = time.perf_counter()
    hits = match_assets_for_incident(assets, values)
    elapsed = time.perf_counter() - start
    assert len(hits) == 1
    assert hits[0].asset_id == "target"
    assert elapsed < 2.0, f"matching took {elapsed:.2f}s"
