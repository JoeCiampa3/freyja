"""landmarks.json (`landmarks/1`): vertex picks on the 13,380-vertex MakeHuman body, written by tools/landmark-picker."""
from __future__ import annotations

SCHEMA = "landmarks/1"
TOPOLOGY = 13380
# ASIS_R/ASIS_L: right and left anterior superior iliac spine. SACRAL_MID: midline skin point at PSIS level (stands in for MPSIS).
# EPI_MED_R/EPI_LAT_R: right medial and lateral femoral epicondyle (skin).
REQUIRED = ("ASIS_R", "ASIS_L", "SACRAL_MID", "EPI_MED_R", "EPI_LAT_R")


def validate(doc) -> list[str]:
    """Every problem with a landmarks document, as text; an empty list means valid."""
    if not isinstance(doc, dict):
        return ["document is not an object"]
    out = []
    if doc.get("schema") != SCHEMA:
        out.append(f"schema is {doc.get('schema')!r}, expected {SCHEMA!r}")
    if doc.get("topology") != TOPOLOGY or isinstance(doc.get("topology"), bool):
        out.append(f"topology is {doc.get('topology')!r}, expected {TOPOLOGY}")
    lm = doc.get("landmarks")
    if not isinstance(lm, dict):
        return out + ["landmarks is missing or not an object"]
    for name in REQUIRED:
        if name not in lm:
            out.append(f"{name}: missing")
            continue
        v = lm[name].get("vertex") if isinstance(lm[name], dict) else None
        if not isinstance(v, int) or isinstance(v, bool) or not 0 <= v < TOPOLOGY:
            out.append(f"{name}: vertex {v!r} is not an integer in [0, {TOPOLOGY})")
    return out
