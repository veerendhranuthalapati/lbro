import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GUIDES = ROOT / "backend" / "app" / "knowledge" / "attack_guides.json"


def flesch(text: str) -> float:
    words = re.findall(r"[A-Za-z']+", text)
    sentences = max(1, len(re.split(r"[.!?]+", text)) - 1)
    syllables = sum(max(1, len(re.findall(r"[aeiouyAEIOUY]+", w))) for w in words)
    if not words:
        return 0.0
    return 206.835 - 1.015 * (len(words) / sentences) - 84.6 * (syllables / len(words))


def main() -> None:
    data = json.loads(GUIDES.read_text(encoding="utf-8"))
    for k, v in data["guides"].items():
        t = v.get("summary_plain", "")
        print(f"{k}\t{round(flesch(t), 1)}")


if __name__ == "__main__":
    main()
