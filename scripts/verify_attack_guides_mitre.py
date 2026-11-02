"""Verify attack guides + compliance MITRE mapping against pinned STIX (scratch only)."""
from __future__ import annotations

import json
import re
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRATCH = ROOT.parent / "lbro-run-scratch"
GUIDES = ROOT / "backend" / "app" / "knowledge" / "attack_guides.json"
COMPLIANCE_MAP = ROOT / "backend" / "app" / "compliance" / "knowledge" / "attack_to_technique.json"
OUT = SCRATCH / "attack_guides_verify.json"
STIX = SCRATCH / "enterprise-attack.json"

TECH_RE = re.compile(r"^T\d{4}(?:\.\d{3})?$")


def flesch_reading_ease(text: str) -> float:
    words = re.findall(r"[A-Za-z']+", text)
    sentences = max(1, len(re.split(r"[.!?]+", text)) - 1)
    syllables = sum(max(1, len(re.findall(r"[aeiouyAEIOUY]+", w))) for w in words)
    if not words:
        return 0.0
    return 206.835 - 1.015 * (len(words) / sentences) - 84.6 * (syllables / len(words))


def load_stix_index(blob: str) -> dict[str, dict]:
    data = json.loads(blob)
    idx: dict[str, dict] = {}
    for obj in data.get("objects", []):
        if obj.get("type") != "attack-pattern":
            continue
        for ref in obj.get("external_references", []) or []:
            if ref.get("source_name") == "mitre-attack" and ref.get("external_id"):
                tid = ref["external_id"]
                idx[tid] = {
                    "name": obj.get("name"),
                    "revoked": obj.get("revoked", False),
                    "deprecated": obj.get("x_mitre_deprecated", False),
                }
    return idx


def fetch_url(url: str) -> tuple[str, int | None]:
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "lbro-verify/1.0"})
        with urllib.request.urlopen(req, timeout=20) as resp:
            body = resp.read(8000).decode("utf-8", errors="ignore")
            return body[:2000], resp.status
    except urllib.error.HTTPError as e:
        return "", e.code
    except Exception:
        return "", None


def main() -> None:
    guides = json.loads(GUIDES.read_text(encoding="utf-8"))
    stix_status = "MISSING"
    stix_idx: dict[str, dict] = {}
    if STIX.is_file():
        stix_status = f"LOADED bytes={STIX.stat().st_size}"
        stix_idx = load_stix_index(STIX.read_text(encoding="utf-8"))

    technique_rows = []
    readability: dict[str, float] = {}
    deprecated_hits: list[dict] = []
    guides_map = guides.get("guides", {})
    for entry in guides_map.values():
        if not isinstance(entry, dict):
            continue
        cid = entry.get("class_id", "?")
        summary = entry.get("summary_plain", "")
        readability[cid] = round(flesch_reading_ease(summary), 1)
        for tid in entry.get("mitre_techniques", []) or []:
            meta = stix_idx.get(str(tid), {})
            technique_rows.append(
                {
                    "class_id": cid,
                    "technique": tid,
                    "format_ok": bool(TECH_RE.match(str(tid))),
                    "in_stix": str(tid) in stix_idx or str(tid).split(".")[0] in stix_idx,
                    "stix_name": meta.get("name"),
                    "revoked": meta.get("revoked"),
                    "deprecated": meta.get("deprecated"),
                }
            )
            if meta.get("revoked") or meta.get("deprecated"):
                deprecated_hits.append({"class_id": cid, "technique": tid, **meta})

    compliance_rows = []
    if COMPLIANCE_MAP.is_file():
        cmap = json.loads(COMPLIANCE_MAP.read_text(encoding="utf-8"))
        for attack, block in (cmap.get("mappings") or {}).items():
            for m in block.get("techniques", []) or []:
                tid = m.get("technique_id")
                meta = stix_idx.get(str(tid), {})
                compliance_rows.append(
                    {
                        "attack_class": attack,
                        "technique_id": tid,
                        "in_stix": str(tid) in stix_idx,
                        "stix_name": meta.get("name"),
                        "deprecated": meta.get("deprecated"),
                    }
                )

    url_checks = []
    for entry in guides_map.values():
        if not isinstance(entry, dict):
            continue
        cid = entry.get("class_id", "?")
        for url in entry.get("references", []) or []:
            url = str(url)
            snippet, code = fetch_url(url) if url.startswith("http") else ("", None)
            relevant = "attack.mitre.org" in url or "cwe.mitre.org" in url or "owasp.org" in url
            if relevant and snippet:
                relevant = len(snippet) > 100
            url_checks.append(
                {
                    "class_id": cid,
                    "url": url,
                    "http_code": code,
                    "content_relevant": relevant,
                }
            )

    report = {
        "stix_check": stix_status,
        "technique_rows": technique_rows,
        "compliance_technique_rows": compliance_rows,
        "deprecated_or_revoked": deprecated_hits,
        "readability_flesch_all": readability,
        "readability_min": min(readability.values()) if readability else None,
        "url_checks": url_checks,
    }
    OUT.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(OUT)
    print("stix:", stix_status)
    print("deprecated_hits:", len(deprecated_hits))
    print("readability_min:", report["readability_min"])


if __name__ == "__main__":
    main()
