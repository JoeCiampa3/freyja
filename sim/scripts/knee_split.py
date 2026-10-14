"""
Stage 2e T7 (report only): how far A's knee moment depends on the thigh to shank split.

    python sim/scripts/gait_diag.py knee-split [--ratios 0.883 0.935 0.977 1.0] [--speeds 1.4 1.6] [--workers 5] --scratch DIR

A throwaway copy of the generated MJCF is written to DIR (outside the repository) with the knee moved along the hip to ankle line so that thigh plus shank
is fixed and the thigh to shank ratio takes each requested value. The thigh and the shank each keep their mass; the centre-of-mass offset of a segment
is scaled by its new length over its old one (all three components: a uniform stretch of the segment), and the inertia tensor about the centre of mass
by the square of that factor; the capsule geoms follow the new lengths. Nothing else changes: the sheet, the template, the tracked model and the snapshot
are untouched. A_filtered is then run over every stride of each speed on the copy (the repository's own pipeline, the model path being the only change).
"""
from __future__ import annotations

import sys
import xml.etree.ElementTree as ET
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))


# ------------------------------------------------------------------------------ the transform

def _vec(text):
    return np.array([float(v) for v in text.split()])


def _fmt(a):
    return " ".join(repr(float(v)) for v in a)


def _legs(root):
    out = {}
    for side in ("right", "left"):
        thigh = next(b for b in root.iter("body") if b.get("name") == f"thigh_{side}")
        shank = next(b for b in thigh.iter("body") if b.get("name") == f"shank_{side}")
        foot = next(b for b in shank.iter("body") if b.get("name") == f"foot_{side}")
        out[side] = (thigh, shank, foot)
    return out


def _lengths(root, side="right"):
    _, shank, foot = _legs(root)[side]
    return -_vec(shank.get("pos"))[2], -_vec(foot.get("pos"))[2]


def current_ratio(xml_text: str) -> float:
    l1, l2 = _lengths(ET.fromstring(xml_text))
    return float(l1 / l2)


def length_factor(xml_text: str, ratio: float, which: str) -> float:
    """New over old length of the thigh or the shank for the requested ratio at fixed sum."""
    l1, l2 = _lengths(ET.fromstring(xml_text))
    n1 = (l1 + l2) * ratio / (1.0 + ratio)
    return float(n1 / l1) if which == "thigh" else float((l1 + l2 - n1) / l2)


def with_thigh_to_shank_ratio(xml_text: str, ratio: float) -> str:
    """The model text with the knee moved so that thigh / shank = ratio and thigh + shank is unchanged (both legs)."""
    if not ratio > 0:
        raise ValueError("the thigh to shank ratio must be positive")
    root = ET.fromstring(xml_text)
    l1, l2 = _lengths(root)
    total = l1 + l2
    n1 = total * ratio / (1.0 + ratio)
    n2 = total - n1
    for side, (thigh, shank, foot) in _legs(root).items():
        for body, f in ((thigh, n1 / l1), (shank, n2 / l2)):
            ine = body.find("inertial")
            ine.set("pos", _fmt(f * _vec(ine.get("pos"))))
            ine.set("fullinertia", _fmt(f * f * _vec(ine.get("fullinertia"))))
        p = _vec(shank.get("pos"))
        p[2] = -n1
        shank.set("pos", _fmt(p))
        p = _vec(foot.get("pos"))
        p[2] = -n2
        foot.set("pos", _fmt(p))
        for body, n, end in ((thigh, n1, 0.05), (shank, n2, 0.04)):
            for g in body.findall("geom"):
                if g.get("type") == "capsule" and g.get("fromto"):
                    ft = _vec(g.get("fromto"))
                    ft[5] = -(n - end)
                    g.set("fromto", _fmt(ft))
    return ET.tostring(root, encoding="unicode")


# ------------------------------------------------------------------------------ the report

def report(args):
    import gait
    import gait_extract
    from knee_tails import extension_peak, tail_row
    src = (gait.REPO / "sim" / "models" / "freyja.xml").read_text(encoding="utf-8")
    scratch = Path(args.scratch).resolve()
    if gait.REPO in scratch.parents or scratch == gait.REPO:
        raise SystemExit("--scratch must be outside the repository")
    scratch.mkdir(parents=True, exist_ok=True)
    spec = gait.load_spec("walk_treadmill")
    print(f"thigh to shank ratio of the repository model: {current_ratio(src):.4f}; thigh plus shank {1000 * sum(_lengths(ET.fromstring(src))):.1f} mm")
    keep = gait.simrun.MODEL_FILE
    try:
        for r in args.ratios:
            path = scratch / f"freyja_ratio_{r:.3f}.xml"
            path.write_text(with_thigh_to_shank_ratio(src, r), encoding="utf-8")
            gait.simrun.MODEL_FILE = path
            l1 = 1000 * sum(_lengths(ET.fromstring(src))) * r / (1 + r)
            for speed in args.speeds:
                S, mass, _ = gait_extract.a_filtered_strides(speed, args.workers)
                rows = gait_extract.a_sagittal_rows(S, mass)["knee"]
                peaks = np.array([extension_peak(s["tau"][f"knee_{side}"]) for s in S for side in ("right", "left")])
                off = np.array([s["subject"] in set(spec["offset_subjects"]) for s in S for _ in range(2)])
                t_all, t_off = tail_row(peaks), tail_row(peaks[~off])
                sc = rows["scaled_peak_nm"]
                print(f"ratio {r:.3f} (thigh {l1:.1f} mm), {speed} m/s: A knee extension p95 {t_all['p95']:.1f} max {t_all['max']:.1f} (without offset subjects p95 {t_off['p95']:.1f} max {t_off['max']:.1f}); "
                      f"dataset scaled p95 {sc['p95']:.1f} max {sc['max']:.1f}; OLS slope on the dataset per kg {rows['ols_slope']:.3f}; peak ratio {rows['peak_ratio']:.3f}; "
                      f"A p95 over dataset p95 {t_all['p95'] / sc['p95']:.3f}")
    finally:
        gait.simrun.MODEL_FILE = keep
