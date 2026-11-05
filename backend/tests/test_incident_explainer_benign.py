"""BENIGN verdicts must not describe an attack source, port or duration."""

from app.services.incident_explainer import explain_incident


def test_benign_explanation_has_no_attack_context():
    out = explain_incident(
        "BENIGN", "any title", "high",
        source_ip="127.0.0.1", destination_port=80, flow_duration_ms=5000,
    )
    assert out["context"] is None
    assert "No real attack" in out["plain_english"]


def test_attack_explanation_keeps_context():
    out = explain_incident("PortScan", "t", "high", source_ip="10.0.0.5")
    assert out["context"] and "10.0.0.5" in out["context"]
