"""
Stage 2 T3b diagnostics (brief section T3b): one subcommand per step. Each prints a summary and writes nothing. Run from a clean
commit so the numbers can be reproduced.

    python sim/scripts/gait_diag.py a-agreement [--root-reference hip_midpoint|pelvis_origin] [--cap 3] [--speed 1.4]
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import gait  # noqa: E402

REPO = gait.REPO
SAGITTAL = ("hip_fe", "knee", "ankle_pdflex")
TARGET_CORR, TARGET_RMS_PCT = 0.9, 15.0  # review targets from the brief, not acceptance limits


def _rows(spec, methods, cap, speed, workers, **overrides):
    spec = dict(spec)
    spec.update({"speeds_mps": [speed], "stride_cap_per_subject": cap, **overrides})
    manifest = json.loads((REPO / spec["dataset"]["manifest"]).read_text(encoding="utf-8"))
    tasks = gait._tasks(spec, manifest, gait.simrun.MODEL_FILE, REPO / spec["dataset"]["processed"], methods,
                        float(spec["smoothing"]["cutoff_hz"]), float(spec["pelvis_tilt_offset_deg"]), cap, True, True, False)
    return gait._run_tasks(tasks, workers)


def a_agreement(args):
    spec = gait.load_spec("walk_treadmill")
    spec["root_reference"] = args.root_reference
    rows = _rows(spec, ["A_native", "A_filtered"], args.cap, args.speed, args.workers)
    print(f"A agreement with the dataset moments; root reference {args.root_reference}; {len(rows)} strides at {args.speed} m/s")
    print("joint (both limbs pooled)   method       corr   rms % ptp   peak diff N m/kg")
    for stem in SAGITTAL:
        for m in ("A_native", "A_filtered"):
            vals = {k: np.mean([r["agree"][m][f"{stem}_{s}"][k] for r in rows for s in ("right", "left")]) for k in ("corr", "rms_pct_ptp", "peak_diff")}
            ok = "ok" if vals["corr"] >= TARGET_CORR and vals["rms_pct_ptp"] <= TARGET_RMS_PCT else "below target"
            print(f"{stem:26s} {m:11s} {vals['corr']:6.3f} {vals['rms_pct_ptp']:9.1f} {vals['peak_diff']:12.3f}   {ok}")


def main(argv=None):
    ap = argparse.ArgumentParser(prog="gait_diag")
    sub = ap.add_subparsers(dest="cmd", required=True)
    a = sub.add_parser("a-agreement")
    a.add_argument("--root-reference", default="hip_midpoint", choices=["hip_midpoint", "pelvis_origin"])
    a.add_argument("--cap", type=int, default=3)
    a.add_argument("--speed", default="1.4")
    a.add_argument("--workers", type=int, default=5)
    args = ap.parse_args(argv)
    {"a-agreement": a_agreement}[args.cmd](args)


if __name__ == "__main__":
    main()
