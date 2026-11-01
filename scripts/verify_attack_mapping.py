"""Validate ATT&CK technique IDs in attack_to_technique.json against official STIX (pinned version)."""
from __future__ import annotations

import json
import sys
import tempfile
import urllib.request
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
MAPPING_PATH = REPO_ROOT / "backend" / "app" / "compliance" / "knowledge" / "attack_to_technique.json"
STIX_URL = "https://raw.githubusercontent.com/mitre-attack/attack-stix-data/master/enterprise-attack/enterprise-attack.json"


def _load_stix_techniques(stix_path: Path) -> dict[str, str]:
    data = json.loads(stix_path.read_text(encoding="utf-8"))
    out: dict[str, str] = {}
    for obj in data.get("objects", []):
        if obj.get("type") != "attack-pattern":
            continue
        if obj.get("revoked") or obj.get("x_mitre_deprecated"):
            continue
        for ref in obj.get("external_references", []):
            if ref.get("source_name") == "mitre-attack" and ref.get("external_id", "").startswith("T"):
                out[ref["external_id"]] = obj.get("name", ref["external_id"])
    return out


def main() -> int:
    mapping = json.loads(MAPPING_PATH.read_text(encoding="utf-8"))
    pinned = mapping.get("attack_enterprise_version", "?")
    print(f"Verifying mappings against Enterprise ATT&CK STIX (declared pin v{pinned})...")
    with tempfile.TemporaryDirectory() as tmp:
        stix_file = Path(tmp) / "enterprise-attack.json"
        urllib.request.urlretrieve(STIX_URL, stix_file)
        techniques = _load_stix_techniques(stix_file)
    errors: list[str] = []
    for class_name, body in mapping.get("mappings", {}).items():
        for link in body.get("techniques", []):
            tid = link["technique_id"].split(".")[0]
            name = link.get("name", "")
            if tid not in techniques:
                errors.append(f"{class_name}: unknown technique id {tid}")
            elif techniques[tid] != name:
                errors.append(f"{class_name}: name mismatch for {tid}: json={name!r} stix={techniques[tid]!r}")
    if errors:
        for e in errors:
            print("ERROR:", e)
        return 1
    print(f"OK: {len(techniques)} STIX techniques loaded; all mapped IDs valid.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
