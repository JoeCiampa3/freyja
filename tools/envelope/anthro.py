"""ANSUR II female reference heights: each landmark's height as a fraction of stature, mean and SD over the 1,986 subjects.

The raw CSV stays outside git (`data/ansur2/raw/`, gitignored); `fy envelope ratios` writes the tracked, generated summary
`data/ansur2/ratios.json`, which is what the trial reads.
"""
from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path

import numpy as np

# landmark -> ANSUR column (heights above the floor, mm)
COLUMNS = {
    "crotch": "crotchheight",
    "trochanterion": "trochanterionheight",
    "lateral_femoral_epicondyle": "lateralfemoralepicondyleheight",
    "lateral_malleolus": "lateralmalleolusheight",
    "iliocristale": "iliocristaleheight",
    "tenth_rib": "tenthribheight",
    "midpatella": "kneeheightmidpatella",
    "cervicale": "cervicaleheight",             # brief 5: the C7 cross-check of the trunk registration
    "suprasternale": "suprasternaleheight",     # the sternal notch; Dumas's SUP, an extra CJC cross-check
}
# pose-invariant arm lengths (mm, surface landmarks, not joint centres): volume-extractor brief 8, item 3; context cross-checks of the arm registration only
ARM_COLUMNS = {
    "shoulder_elbow": "shoulderelbowlength",
    "radiale_stylion": "radialestylionlength",
    "forearm_hand": "forearmhandlength",
    "hand_length": "handlength",
}
RAW = "data/ansur2/raw/ANSUR_II_FEMALE_Public.csv"
SUMMARY = "data/ansur2/ratios.json"


def summarise(csv_path) -> dict:
    with open(csv_path, newline="", encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    stature = np.array([float(r["stature"]) for r in rows])
    out = {"n": len(rows), "stature_mm": {"mean": float(stature.mean()), "sd": float(stature.std(ddof=1))}, "landmarks": {}}
    heights = {}
    for name, col in COLUMNS.items():
        h = np.array([float(r[col]) for r in rows])
        heights[name] = h
        q = h / stature
        out["landmarks"][name] = {"column": col, "height_mm": {"mean": float(h.mean()), "sd": float(h.std(ddof=1))},
                                  "ratio": {"mean": float(q.mean()), "sd": float(q.std(ddof=1))}}
    d = (heights["trochanterion"] - heights["crotch"]) / stature
    out["trochanterion_minus_crotch_ratio"] = {"mean": float(d.mean()), "sd": float(d.std(ddof=1))}
    # per-subject offsets between landmarks, as a fraction of stature and in mm (the Ruler knee loop is taken to sit at the midpatella)
    e = heights["lateral_femoral_epicondyle"] - heights["midpatella"]
    out["epicondyle_minus_midpatella"] = {"ratio": {"mean": float((e / stature).mean()), "sd": float((e / stature).std(ddof=1))},
                                          "mm": {"mean": float(e.mean()), "sd": float(e.std(ddof=1))}}
    out["circumferences_mm"] = {}
    for name, col in (("thigh_gluteal_furrow", "thighcircumference"), ("lower_thigh_suprapatella", "lowerthighcircumference"),
                      ("calf_maximum", "calfcircumference"), ("ankle_minimum", "anklecircumference")):
        c = np.array([float(r[col]) for r in rows])
        out["circumferences_mm"][name] = {"column": col, "mean": float(c.mean()), "sd": float(c.std(ddof=1))}
    out["arm_lengths"] = {}
    for name, col in ARM_COLUMNS.items():
        if col not in rows[0]:               # a reduced CSV without the arm columns (the real ANSUR II file has them): the arm cross-check then stops with a message in `arms.ansur_check`
            continue
        a = np.array([float(r[col]) for r in rows])
        q = a / stature
        out["arm_lengths"][name] = {"column": col, "length_mm": {"mean": float(a.mean()), "sd": float(a.std(ddof=1))}, "ratio": {"mean": float(q.mean()), "sd": float(q.std(ddof=1))}}
    out["source_sha256_12"] = hashlib.sha256(Path(csv_path).read_bytes()).hexdigest()[:12]
    return out


def write_summary(root: Path) -> Path:
    s = summarise(root / RAW)
    s = {"generated_by": "fy envelope ratios", "inputs": f"ANSUR II female public CSV sha256:{s['source_sha256_12']}", **s}
    p = root / SUMMARY
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(s, indent=1, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    return p


def load_summary(root: Path) -> dict:
    from .sheet import StopAndAsk
    p = root / SUMMARY
    if not p.exists():
        if (root / RAW).exists():
            write_summary(root)
        else:
            raise StopAndAsk(f"{SUMMARY} is missing and so is the raw CSV {RAW}; place the ANSUR II female public CSV there")
    return json.loads(p.read_text(encoding="utf-8"))
