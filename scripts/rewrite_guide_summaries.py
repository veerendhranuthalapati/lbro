"""Rewrite attack guide summary_plain to Flesch >= 50 (defensive-only)."""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GUIDES = ROOT / "backend" / "app" / "knowledge" / "attack_guides.json"


def flesch(text: str) -> float:
    import re

    words = re.findall(r"[A-Za-z']+", text)
    sentences = max(1, len(re.split(r"[.!?]+", text)) - 1)
    syllables = sum(max(1, len(re.findall(r"[aeiouyAEIOUY]+", w))) for w in words)
    if not words:
        return 0.0
    return 206.835 - 1.015 * (len(words) / sentences) - 84.6 * (syllables / len(words))

REWRITES = {
    "BENIGN": (
        "LBRO flagged unusual traffic stats. This is often normal app traffic. "
        "Check your logs before you treat it as an attack."
    ),
    "PortScan": (
        "A host probed many ports on your server to find open services. "
        "Review firewall logs and close ports you do not need."
    ),
    "DDoS": (
        "Many sources sent traffic at once to overload your app. "
        "LBRO saw a volume spike; confirm with network logs before you act."
    ),
    "DoS GoldenEye": (
        "GoldenEye sends slow HTTP requests to tie up web server connections. "
        "Watch connection counts and rate limits if this pattern continues."
    ),
    "FTP-Patator": (
        "A tool tried many FTP username and password pairs. "
        "Lock out repeated failures and use strong credentials on FTP."
    ),
    "SSH-Patator": (
        "A tool tried many SSH login pairs on your server. "
        "Use keys instead of passwords and limit who can reach SSH."
    ),
    "DoS slowloris": (
        "Slowloris opens many HTTP connections and sends headers very slowly. "
        "Your web tier may run out of slots; check idle connections."
    ),
    "DoS Slowhttptest": (
        "Slow HTTP bodies keep connections open to exhaust the web server. "
        "Tune timeouts and front-door rate limits if you see this often."
    ),
    "Bot": (
        "Traffic looks like a compromised host talking to command servers. "
        "Verify the source host and scan it for malware if the alert repeats."
    ),
    "Web Attack - Brute Force": (
        "Many login tries hit your web app in a short time. "
        "Enable lockouts or MFA on exposed login pages."
    ),
    "Web Attack - XSS": (
        "Input may include script meant to run in a user's browser. "
        "Sanitize output and review the flagged request in your WAF or app logs."
    ),
    "Infiltration": (
        "LBRO saw signs that someone may already be inside your network. "
        "Save logs now and follow your incident runbook."
    ),
    "Web Attack - Sql Injection": (
        "A request may have carried SQL meant to harm your database. "
        "Use bound parameters and check the flagged field in app logs."
    ),
}


def main() -> None:
    data = json.loads(GUIDES.read_text(encoding="utf-8"))
    for class_id, text in REWRITES.items():
        if class_id in data["guides"]:
            data["guides"][class_id]["summary_plain"] = text
    GUIDES.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    for k, v in data["guides"].items():
        score = flesch(v.get("summary_plain", ""))
        flag = "OK" if score >= 50 else "LOW"
        print(f"{k}\t{round(score, 1)}\t{flag}")


if __name__ == "__main__":
    main()
