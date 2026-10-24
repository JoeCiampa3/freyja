"""Sheet inputs of the envelope trial. Dimensions come from the sheet pull (params/snapshot.csv and the B1 pull), never from code.

The B1 table (Dumas 2007, ISB pelvis frame, mm) is not in the snapshot: `pre_processor` pulls only named ranges. The pipeline reads it
from a pull file (`--b1 FILE`, JSON `{"rows": {"RASIS": [x, y, z], ...}, "pelvis_ref_length_mm": 107, "source": "..."}`) and asserts it
equals the values the brief names before anything else runs.
"""
from __future__ import annotations

import csv
import json
from pathlib import Path

# What the brief says the sheet's B1 table holds (ISB, mm); a guard, not an input.
EXPECTED_B1 = {"RASIS": (87.0, -13.0, 119.0), "MPSIS": (-108.0, -13.0, 0.0), "HJC (Dumas)": (54.0, -93.0, 88.0)}
REQUIRED_ROWS = ("RASIS", "LASIS", "MPSIS", "HJC (Dumas)")
B1_TOL_MM = 1e-6   # the guard is for transcription changes, not for numerical noise


class StopAndAsk(Exception):
    """A needed sheet value is missing or changed: the brief says stop and tell Joe which one."""


def load_b1(path) -> dict:
    d = json.loads(Path(path).read_text(encoding="utf-8"))
    assert_b1(d)
    return d


def assert_b1(d) -> None:
    rows = d.get("rows", {})
    for name in REQUIRED_ROWS:
        if name not in rows:
            raise StopAndAsk(f"B1 row {name!r} is missing from the sheet pull")
    for name, want in EXPECTED_B1.items():
        got = tuple(float(x) for x in rows[name])
        if any(abs(a - b) > B1_TOL_MM for a, b in zip(got, want)):
            raise StopAndAsk(f"B1 row {name!r} is {got}, the brief expects {want}")
    if "pelvis_ref_length_mm" not in d:
        raise StopAndAsk("pelvis_ref_length_mm (Dumas pelvis length, the denominator of the sheet's pelvis factor) is missing from the sheet pull")


def read_snapshot(path) -> dict:
    with open(path, newline="", encoding="utf-8") as fh:
        return {r["placeholder"]: float(r["value"]) for r in csv.DictReader(fh)}


def thigh_inputs(snapshot_path, side: str) -> dict:
    """Thigh length (mm) and mass (kg) from the snapshot."""
    snap = read_snapshot(snapshot_path)
    out = {}
    for key, name, scale in ((f"thigh_{side}_length", "length_mm", 1000.0), (f"thigh_{side}_mass", "mass_kg", 1.0)):
        if key not in snap:
            raise StopAndAsk(f"snapshot key {key} is missing")
        out[name] = snap[key] * scale
    return out


def sheet_pelvis_factor(snapshot_path, b1) -> float:
    """The sheet's pelvis factor k: the snapshot's pelvis length over Dumas's reference pelvis length."""
    snap = read_snapshot(snapshot_path)
    if "pelvis_length" not in snap:
        raise StopAndAsk("snapshot key pelvis_length is missing")
    return snap["pelvis_length"] * 1000.0 / float(b1["pelvis_ref_length_mm"])
