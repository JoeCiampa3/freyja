"""
Stage 2g T8 (report only): how much of the change in B's centre-of-pressure-outside-the-polygon rate comes from the foot box and how much from everything else.

    python sim/scripts/old_box_diag.py [--speeds 0.5 1.4 1.6] [--workers 6] [--json OUT]

The retargeted kinematics of every subject-stride (the rolling cycle B uses, rigid trunk, the spec's frame offset) are solved twice by method B, once on the model
and once on a copy of it whose foot box is the Stage 2 one (41.25 mm behind the ankle, 165 mm ahead, no toe box) and everything else identical: bodies, masses,
inertias, joints. The copy is built in memory from sim/models/freyja.xml and written nowhere. For each decile of the stride it prints the share of stance frames whose
CoP lies outside the support polygon (single support: the foot's polygon; double support: the hull of the two), the rule `gait.run_stride` applies, so the new-box column
is the record's `cop_outside_by_phase_bin`. The retargeting is not redone for the old box: this is the same motion against a different box.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import tempfile
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import mujoco
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import dynamics  # noqa: E402
import gait  # noqa: E402
import gaitloads  # noqa: E402
import retarget  # noqa: E402

OLD_HEEL_M, OLD_TIP_M = 0.04125, 0.165  # the Stage 2 template's foot box: 41.25 mm behind the ankle (a fraction of the 165 mm foot) and 165 mm ahead
N_BINS = gait.N_BINS
_CACHE = {}


def old_box_xml(xml: str, heel_m=OLD_HEEL_M, tip_m=OLD_TIP_M) -> str:
    """The model text with the foot's box replaced by the Stage 2 box (same height, same width) and the toe's box removed (the toe bodies stay, with their mass)."""
    foot = re.compile(r'(<body name="foot_(?:right|left)".*?<geom type="box" pos=")([^ ]+)( 0 [^"]+" size=")([^ ]+)( )', re.S)
    out, n = foot.subn(lambda m: f"{m.group(1)}{(tip_m - heel_m) / 2:.12g}{m.group(3)}{(tip_m + heel_m) / 2:.12g}{m.group(5)}", xml)
    if n != 2:
        raise ValueError(f"expected two foot boxes, found {n}")
    out, n = re.subn(r'(<body name="toe_(?:right|left)".*?)\s*<geom type="box"[^>]*/>', r"\1", out, flags=re.S)
    if n != 2:
        raise ValueError(f"expected two toe boxes, found {n}")
    return out


def _models(model_path: str):
    if model_path not in _CACHE:
        new = mujoco.MjModel.from_xml_path(model_path)
        old = mujoco.MjModel.from_xml_string(old_box_xml(Path(model_path).read_text(encoding="utf-8")))
        _CACHE[model_path] = (new, old)
    return _CACHE[model_path]


def outside_flags(model, q, qd, qdd, stance):
    """B's outside-the-polygon distance for one support frame (None when there is no stance foot)."""
    if not stance:
        return None
    r = dynamics.solve_frame(model, q, qd, qdd, stance=stance, sweep=False)
    if len(stance) == 1:
        return float(-r.cop_margin_m[stance[0]])
    return float(r.ds_outside_m) if r.ds_outside_m == r.ds_outside_m else float("inf")


def stride(task: dict) -> dict:
    c = gait._ctx(task["model_path"])
    new, old = _models(task["model_path"])
    z = gait._subject_arrays(task["processed"], task["subject"])
    sp, i = task["speed"], task["index"]
    ik, fp = z[f"{sp}_ik"][i], z[f"{sp}_fp"][i]
    T, sub = float(z[f"{sp}_duration_s"][i]), task["subject_info"]
    hip = sub.get("hip_in_pelvis_os_m")
    ref = task["root_reference"] if hip is not None else "pelvis_origin"
    stance_mask = fp[:, :, 6] >= gaitloads.STANCE_FLAG
    cyc = retarget.Cycle(c.model, c.mapping, c.stand, ik, T, retarget.leg_length_ratio(c.model, sub["height_m"]), cutoff_hz=task["cutoff_hz"],
                         pitch_offset_deg=task["pitch_offset_deg"], root_rule=task["root_rule"], hip_in_pelvis_os=hip, root_ref=ref, pitch_mean=task["pitch_mean"],
                         trunk=task["trunk"], pelvis_frame_offset_deg=gait.frame_offset_deg(task.get("pelvis_frame_offset", "none"), sub), toe="rolling", stance=stance_mask)
    q, qd, qdd = cyc.grid()
    n = np.zeros((2, N_BINS))
    out = np.zeros((2, N_BINS))
    for k in range(gait.N_FRAMES):
        stance = tuple(f for j, f in enumerate(gait.FEET) if stance_mask[j, k])
        b = min(k * N_BINS // gait.N_FRAMES, N_BINS - 1)
        for m, model in enumerate((new, old)):
            dist = outside_flags(model, q[k], qd[k], qdd[k], stance)
            if dist is not None:
                n[m, b] += 1
                out[m, b] += dist > 0
    return {"speed": sp, "n": n.tolist(), "out": out.tolist()}


def main(argv=None):
    ap = argparse.ArgumentParser(prog="old_box_diag")
    ap.add_argument("--speeds", nargs="*", type=float)
    ap.add_argument("--workers", type=int, default=6)
    ap.add_argument("--json")
    args = ap.parse_args(argv)
    spec = gait.load_spec("walk_treadmill")
    manifest = json.loads((gait.REPO / spec["dataset"]["manifest"]).read_text(encoding="utf-8"))
    processed = gait.REPO / spec["dataset"]["processed"]
    spec = dict(spec, speeds_mps=[float(s) for s in (args.speeds or spec["speeds_mps"])])
    tasks = gait._tasks(spec, manifest, gait.simrun.MODEL_FILE, processed, ["B"], float(spec["smoothing"]["cutoff_hz"]), float(spec["pelvis_pitch_offset_deg"]),
                        spec.get("stride_cap_per_subject"), False, False, False, trunk="rigid")
    with ProcessPoolExecutor(max_workers=args.workers) as ex:
        rows = list(ex.map(stride, tasks, chunksize=4))
    res = {}
    for sp in sorted({r["speed"] for r in rows}, key=float):
        n = sum(np.array(r["n"]) for r in rows if r["speed"] == sp)
        o = sum(np.array(r["out"]) for r in rows if r["speed"] == sp)
        res[sp] = {"frames": n[0].tolist(), "new_box_outside": (o[0] / n[0]).tolist(), "old_box_outside": (o[1] / n[1]).tolist(),
                   "new_box_all": float(o[0].sum() / n[0].sum()), "old_box_all": float(o[1].sum() / n[1].sum())}
        print(f"== {sp} m/s: stance frames {int(n[0].sum())}; outside the polygon, all deciles: new box {100 * res[sp]['new_box_all']:.1f}%, Stage 2 box {100 * res[sp]['old_box_all']:.1f}%")
        print("   decile      " + " ".join(f"{d + 1:5d}" for d in range(N_BINS)))
        print("   new box %   " + " ".join(f"{100 * x:5.1f}" for x in res[sp]["new_box_outside"]))
        print("   old box %   " + " ".join(f"{100 * x:5.1f}" for x in res[sp]["old_box_outside"]))
    if args.json:
        Path(args.json).write_text(json.dumps(res, indent=1, sort_keys=True), encoding="utf-8", newline="\n")


if __name__ == "__main__":
    main()
