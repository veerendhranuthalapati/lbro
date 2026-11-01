"""Label normalization and rare-class policy for CICIDS2017 training."""
from __future__ import annotations

import re

from app.ml.features import ATTACK_CLASSES

# Public CSV labels sometimes contain odd whitespace or unicode dashes.
_LABEL_CLEAN_RE = re.compile(r"\s+")

# Classes with historically very few samples — merged into related taxonomy at train time.
RARE_LABEL_MERGE: dict[str, str] = {
    "Heartbleed": "Web Attack - Brute Force",
    "Infiltration": "Bot",
    "Web Attack � Brute Force": "Web Attack - Brute Force",
    "Web Attack � XSS": "Web Attack - XSS",
    "Web Attack � Sql Injection": "Web Attack - Sql Injection",
}

MIN_TEST_SUPPORT_FOR_REPORTING = 30


def normalize_label(raw: str) -> str | None:
    """Map a raw CSV label to one of ATTACK_CLASSES, or None to drop the row."""
    if raw is None or (isinstance(raw, float) and str(raw) == "nan"):
        return None
    label = _LABEL_CLEAN_RE.sub(" ", str(raw).strip())
    label = RARE_LABEL_MERGE.get(label, label)
    # Fix common mojibake dash variants
    label = label.replace("\ufffd", "-").replace("–", "-").replace("—", "-")
    if label in ATTACK_CLASSES:
        return label
    for canonical in ATTACK_CLASSES:
        if canonical.lower() == label.lower():
            return canonical
    return None
