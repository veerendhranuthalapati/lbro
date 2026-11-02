#!/usr/bin/env python3
"""Build attack_guides.json from incident_explainer + compliance MITRE mappings."""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.compliance.knowledge.loader import load_knowledge_bundle  # noqa: E402
from app.ml.features import ATTACK_CLASSES, SEVERITY_MAP  # noqa: E402
from app.services.incident_explainer import _EXPLANATIONS  # noqa: E402

OUT = ROOT / "backend" / "app" / "knowledge" / "attack_guides.json"

MITRE_NOTICE = (
    "MITRE ATT&CK is a registered trademark of The MITRE Corporation. "
    "This content maps to MITRE ATT&CK Enterprise techniques for defensive awareness only."
)


def _prevention_from_fixes(fixes: list[str]) -> dict:
    return {
        "people": ["Brief security champions on expected traffic patterns and escalation paths."],
        "process": fixes[:3] if fixes else ["Document and test incident response playbooks."],
        "technology": fixes[3:6] if len(fixes) > 3 else fixes,
    }


def main() -> int:
    bundle = load_knowledge_bundle()
    guides: dict = {}
    for class_id in ATTACK_CLASSES:
        exp = _EXPLANATIONS.get(class_id)
        if not exp:
            raise SystemExit(f"No incident_explainer entry for {class_id}")
        mapping = bundle.attack_to_technique.mappings.get(class_id)
        techniques = []
        if mapping:
            for t in mapping.techniques:
                techniques.append({"technique_id": t.technique_id, "name": t.name})
        sev = SEVERITY_MAP.get(class_id, "medium")
        guides[class_id] = {
            "class_id": class_id,
            "title": class_id if class_id != "BENIGN" else "Benign / normal traffic",
            "summary_plain": exp.plain_english.split(".")[0] + ".",
            "how_it_works": exp.plain_english + " " + exp.technical_impact,
            "why_it_matters": exp.business_impact,
            "typical_indicators": [
                "Unusual flow duration or packet rates in network telemetry",
                "Repeated connections to sensitive ports from unfamiliar sources",
            ],
            "immediate_actions": [
                "Preserve logs, flow captures, and LBRO evidence before changes.",
                *exp.recommended_fixes[:2],
            ],
            "containment": exp.recommended_fixes[2:4] if len(exp.recommended_fixes) > 2 else exp.recommended_fixes,
            "recovery": [
                "Validate services from known-good backups after containment.",
                "Monitor for repeat patterns from the same sources.",
            ],
            "prevention": _prevention_from_fixes(exp.recommended_fixes),
            "detection_tips": [
                "Correlate LBRO alerts with firewall, WAF, and application logs.",
                f"Severity hint from model mapping: {sev}.",
            ],
            "mitre_techniques": techniques,
            "data_at_risk_hint": (
                "Depends on affected systems; review compliance exposure results when available."
            ),
            "references": [
                "https://attack.mitre.org/",
                "https://www.cisa.gov/",
                "https://www.nist.gov/cyberframework",
            ],
            "content_version": "2026-11-02",
            "last_reviewed": "2026-11-02",
            "review_status": "unreviewed",
        }

    payload = {
        "schema_version": "1.0",
        "content_version": "2026-11-02",
        "last_reviewed": "2026-11-02",
        "attack_enterprise_version": bundle.attack_to_technique.attack_enterprise_version,
        "disclaimer": DECISION_SUPPORT_DISCLAIMER,
        "mitre_attribution": MITRE_NOTICE,
        "guides": guides,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(f"Wrote {OUT} ({len(guides)} guides)")
    return 0


DECISION_SUPPORT_DISCLAIMER = (
    "LBRO detections are leads based on network-flow statistics and heuristics, not proof of compromise."
)


if __name__ == "__main__":
    raise SystemExit(main())
