"""Verify attack guide MITRE IDs and reference URLs (scratch artifact). Run from repo root."""
from __future__ import annotations

import json
import re
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRATCH = ROOT.parent / "lbro-run-scratch"
GUIDES = ROOT / "backend" / "app" / "knowledge" / "attack_guides.json"
OUT = SCRATCH / "attack_guides_verify.json"
STIX = SCRATCH / "enterprise-attack.json"

TECH_RE = re.compile(r"^T\d{4}(?:\.\d{3})?$")
SUBTECH_RE = re.compile(r"^T\d{4}\.\d{3}$")


def flesch_reading_ease(text: str) -> float:
    words = re.findall(r"[A-Za-z']+", text)
    sentences = max(1, len(re.split(r"[.!?]+", text)) - 1)
    syllables = sum(max(1, len(re.findall(r"[aeiouyAEIOUY]+", w))) for w in words)
    if not words:
        return 0.0
    return 206.835 - 1.015 * (len(words) / sentences) - 84.6 * (syllables / len(words))


def main() -> None:
    data = json.loads(GUIDES.read_text(encoding="utf-8"))
    stix_status = "NOT RUN — enterprise-attack.json missing in lbro-run-scratch"
    stix_ids: set[str] = set()
    if STIX.is_file():
        stix_status = "LOADED"
        blob = STIX.read_text(encoding="utf-8", errors="ignore")
        stix_ids = set(re.findall(r'"external_id"\s*:\s*"(T\d{4}(?:\.\d{3})?)"', blob))

    rows = []
    url_results = []
    texts = []
    guides = data.get("guides", {})
    entries = guides.values() if isinstance(guides, dict) else guides
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        cid = entry.get("class_id", "?")
        for tid in entry.get("mitre_techniques", []) or []:
            ok_fmt = bool(TECH_RE.match(str(tid)))
            in_stix = None if not stix_ids else str(tid).split(".")[0] in {s.split(".")[0] for s in stix_ids} or str(tid) in stix_ids
            rows.append({"class_id": cid, "technique": tid, "format_ok": ok_fmt, "in_pinned_stix": in_stix})
        texts.append(entry.get("summary_plain", ""))
        for url in entry.get("references", []) or []:
            url = str(url)
            status = "skipped"
            code = None
            if url.startswith("http"):
                try:
                    req = urllib.request.Request(url, method="HEAD", headers={"User-Agent": "lbro-verify/1.0"})
                    with urllib.request.urlopen(req, timeout=15) as resp:
                        code = resp.status
                        status = "ok" if code < 400 else "fail"
                except urllib.error.HTTPError as e:
                    code = e.code
                    status = "ok" if code in (405, 403) else "fail"
                except Exception as e:
                    status = f"error:{type(e).__name__}"
            url_results.append({"class_id": cid, "url": url, "status": status, "code": code})

    sample = " ".join(texts[:5])
    report = {
        "stix_check": stix_status,
        "technique_rows": rows,
        "url_checks": url_results,
        "readability_flesch_sample": round(flesch_reading_ease(sample), 1),
        "readability_note": "Higher = easier; sample = first 5 guide summaries",
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(OUT)
    print("stix:", stix_status)
    print("urls ok:", sum(1 for u in url_results if u["status"] == "ok"), "/", len(url_results))


if __name__ == "__main__":
    main()
