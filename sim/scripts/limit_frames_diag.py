"""
Stage 2g Part B (T7, T8), report only: every retargeted frame of the dataset against every model limit, and the free toe's angle.

    python sim/scripts/limit_frames_diag.py [--spec walk_treadmill] [--speeds 0.5 1.4 1.6] [--json OUT]

For each speed and trunk mode of the spec, builds the same retargeted cycles as `gait.run_stride` (the welded one for the legs, the rolling one for the toe) and
counts, per limited hinge, the frames below and above its range, the strides that have one, and the worst excess in degrees. It then summarises the toe (peak angle,
share of frames at the flat stop and at the extension stop, over all frames and over stance) with `gait.toe_stats`. It clips nothing, writes no record and changes
nothing tracked. The toe is kinematic in B and H (the rolling rule), so this is also the toe's angle in those methods.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import mujoco
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import gait  # noqa: E402
import gaitloads  # noqa: E402
import retarget  # noqa: E402

toe_summary = gait.toe_stats
TOL_DEG = 0.1  # degrees. A reporting threshold (the toe stops use the same, gait.TOE_STOP_TOL_DEG); nothing is computed from it


def outside(model, qpos_frames) -> dict:
    """{limited hinge: {below, above (frame counts), below_max_deg, above_max_deg (worst excess, 0 when none)}}. A frame exactly on a limit is inside."""
    out = {}
    for j in range(model.njnt):
        if model.jnt_type[j] == mujoco.mjtJoint.mjJNT_HINGE and model.jnt_limited[j]:
            lo, hi = model.jnt_range[j]
            x = qpos_frames[:, model.jnt_qposadr[j]]
            low, high = x < lo, x > hi
            out[mujoco.mj_id2name(model, mujoco.mjtObj.mjOBJ_JOINT, j)] = {
                "below": int(low.sum()), "above": int(high.sum()),
                "below_gt_tol": int((x < lo - np.radians(TOL_DEG)).sum()), "above_gt_tol": int((x > hi + np.radians(TOL_DEG)).sum()),
                "below_max_deg": float(np.degrees(lo - x[low].min())) if low.any() else 0.0,
                "above_max_deg": float(np.degrees(x[high].max() - hi)) if high.any() else 0.0}
    return out


def stride_cycles(task: dict):
    """The (welded, rolling) retargeted frames of one stride task, built as gait.run_stride builds them."""
    c = gait._ctx(task["model_path"])
    z = gait._subject_arrays(task["processed"], task["subject"])
    sp, i = task["speed"], task["index"]
    ik, fp = z[f"{sp}_ik"][i], z[f"{sp}_fp"][i]
    T, sub = float(z[f"{sp}_duration_s"][i]), task["subject_info"]
    hip = sub.get("hip_in_pelvis_os_m")
    ref = task["root_reference"] if hip is not None else "pelvis_origin"
    stance = fp[:, :, 6] >= gaitloads.STANCE_FLAG

    def cycle(toe):
        return retarget.Cycle(c.model, c.mapping, c.stand, ik, T, retarget.leg_length_ratio(c.model, sub["height_m"]), cutoff_hz=task["cutoff_hz"],
                              pitch_offset_deg=task["pitch_offset_deg"], root_rule=task["root_rule"], hip_in_pelvis_os=hip, root_ref=ref, pitch_mean=task["pitch_mean"],
                              trunk=task["trunk"], pelvis_frame_offset_deg=gait.frame_offset_deg(task.get("pelvis_frame_offset", "none"), sub), toe=toe, stance=stance)
    return c.model, cycle("welded").grid()[0][:gait.N_FRAMES], cycle("rolling").grid()[0][:gait.N_FRAMES], stance[:, :gait.N_FRAMES]


def scan(spec: dict, speeds=None) -> dict:
    manifest = json.loads((gait.REPO / spec["dataset"]["manifest"]).read_text(encoding="utf-8"))
    processed = gait.REPO / spec["dataset"]["processed"]
    spec = dict(spec, speeds_mps=[float(s) for s in (speeds or spec["speeds_mps"])])
    result = {}
    for mode in gait.trunk_modes(spec):
        tasks = gait._tasks(spec, manifest, gait.simrun.MODEL_FILE, processed, ["A_filtered"], float(spec["smoothing"]["cutoff_hz"]), float(spec["pelvis_pitch_offset_deg"]),
                            spec.get("stride_cap_per_subject"), False, False, False, trunk=mode)
        for t in tasks:
            model, qw, qr, stance = stride_cycles(t)
            slot = result.setdefault(t["speed"], {}).setdefault(mode, {"strides": 0, "joints": {}, "toe": {"right": [], "left": []}, "worst": {}})
            slot["strides"] += 1
            for name, o in outside(model, qr).items():
                j = slot["joints"].setdefault(name, {"frames_below": 0, "frames_above": 0, "below_gt_tol": 0, "above_gt_tol": 0, "strides_with": 0, "below_max_deg": 0.0, "above_max_deg": 0.0, "subjects": {}})
                j["frames_below"] += o["below"]
                j["frames_above"] += o["above"]
                j["below_gt_tol"] += o["below_gt_tol"]
                j["above_gt_tol"] += o["above_gt_tol"]
                j["below_max_deg"] = max(j["below_max_deg"], o["below_max_deg"])
                j["above_max_deg"] = max(j["above_max_deg"], o["above_max_deg"])
                if o["below"] or o["above"]:
                    j["strides_with"] += 1
                    j["subjects"][t["subject"]] = j["subjects"].get(t["subject"], 0) + o["below"] + o["above"]
            for side, s in toe_summary(model, qr, stance).items():
                slot["toe"][side].append(s)
    return result


def summarise_toe(rows: list) -> dict:
    """Over the strides of one side: the peak angle (median, 95th percentile, maximum), the mean share of frames at each stop and of stance frames at each stop."""
    def col(k):
        return np.array([r[k] for r in rows if r[k] is not None], float)
    out = {"strides": len(rows)}
    peak = col("peak_deg")
    out.update(peak_median_deg=float(np.median(peak)), peak_p95_deg=float(np.percentile(peak, 95)), peak_max_deg=float(peak.max()))
    for k in ("at_flexion_stop", "at_extension_stop", "stance_at_flexion_stop", "stance_at_extension_stop"):
        out[k + "_mean"] = float(col(k).mean())
    sp = col("stance_peak_deg")
    out["stance_peak_median_deg"], out["stance_peak_max_deg"] = float(np.median(sp)), float(sp.max())
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(prog="limit_frames_diag")
    ap.add_argument("--spec", default="walk_treadmill")
    ap.add_argument("--speeds", nargs="*", type=float)
    ap.add_argument("--json", help="write the numbers here (outside the repository)")
    args = ap.parse_args(argv)
    spec = gait.load_spec(args.spec)
    res = scan(spec, args.speeds)
    for sp, modes in res.items():
        for mode, slot in modes.items():
            print(f"== {sp} m/s, trunk {mode}: {slot['strides']} strides, pelvis_frame_offset {spec.get('pelvis_frame_offset', 'none')}")
            for name, j in sorted(slot["joints"].items()):
                if j["frames_below"] or j["frames_above"]:
                    top = ", ".join(f"{s} {n}" for s, n in sorted(j["subjects"].items(), key=lambda kv: -kv[1])[:3])
                    print(f"  {name:20s} [{j['below_gt_tol']} + {j['above_gt_tol']} past by > {TOL_DEG} deg] below {j['frames_below']:6d} (max {j['below_max_deg']:6.2f} deg) above {j['frames_above']:6d} (max {j['above_max_deg']:6.2f} deg) "
                          f"in {j['strides_with']} strides; most: {top}")
            for side in ("right", "left"):
                print(f"  toe {side}: " + json.dumps({k: round(v, 4) for k, v in summarise_toe(slot["toe"][side]).items()}))
    if args.json:
        slim = {sp: {m: {**s, "toe": {side: summarise_toe(rows) for side, rows in s["toe"].items()}} for m, s in modes.items()} for sp, modes in res.items()}
        Path(args.json).write_text(json.dumps(slim, indent=1, sort_keys=True), encoding="utf-8", newline="\n")


if __name__ == "__main__":
    main()
