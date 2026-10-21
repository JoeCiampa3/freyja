"""
Memo 26 carry-forward items (report only; nothing here changes a model, a retargeting, a tolerance or a tracked output).

    python sim/scripts/followup_diag.py first-stride [--subject AB23] [--index 0] [--speed 0.5] [--workers N]
    python sim/scripts/followup_diag.py profile      [--strides 2]
    python sim/scripts/followup_diag.py ankle-ie     [--speed 1.4]

first-stride: whether a stride is the first of its trial in time (the processed arrays hold each stride's start time and trial), and the trunk's angular acceleration at the
  lumbosacral lateral joint's peak torque, against the other strides of the speed.
profile: where one gait stride spends its time, by function (cProfile), and the sensitivity runs' share of the three-speed run.
ankle-ie: the dataset's subtalar angle against the sheet's inversion/eversion limits: the subtalar axis of the dataset's OpenSim model is oblique (it has a vertical component), the
  model's ankle_ie hinge is the pure long axis.
"""
from __future__ import annotations

import argparse
import cProfile
import json
import pstats
import sys
import zipfile
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "analysis"))
import gait  # noqa: E402

REPO = gait.REPO

# the functions whose cumulative time the profile reports, by stage (file stem, function) -> label
STAGES = {("retarget", "__init__"): "retargeting", ("retarget", "grid"): "retargeting", ("dynamics", "inverse_frame"): "inverse dynamics",
          ("dynamics", "solve_frame"): "B: solve_frame", ("dynamics", "solve_given"): "A and H: solve_given", ("dynamics", "polygon_outside_m"): "polygon test",
          ("retarget", "foot_metrics"): "foot metrics (kinematics report)", ("gaitloads", "measured_to_model_foot"): "measured CoP on the foot",
          ("gait", "agreement"): "agreement with the dataset", ("retarget", "wrap_gap_deg"): "wrap gaps"}


# ------------------------------------------------------------------------------ pure helpers

def trial_position(t0, trial, i) -> dict:
    """Where stride i sits among the strides of its own trial: its rank by start time (0 = the first), the number of strides in the trial and the seconds from the trial's first
    accepted stride to this one."""
    t0, trial = np.asarray(t0, float), np.asarray(trial)
    idx = np.flatnonzero(trial == trial[i])
    order = np.argsort(t0[idx])
    rank = int(np.flatnonzero(idx[order] == i)[0])
    return {"trial": int(trial[i]), "rank": rank, "first_in_trial": rank == 0, "strides_in_trial": int(len(idx)), "start_s": float(t0[i]),
            "s_since_first_stride": float(t0[i] - t0[idx].min())}


def twist_about_x_deg(axis, angle_deg: float) -> float:
    """The twist about the x axis of the rotation by `angle_deg` about `axis` (swing-twist decomposition: 2 atan2(q_x, q_w) of the quaternion): the part of an oblique-axis rotation
    that is a pure rotation about the long axis."""
    a = np.asarray(axis, float)
    a = a / np.linalg.norm(a)
    h = np.radians(angle_deg) / 2.0
    qw, qx = np.cos(h), np.sin(h) * a[0]
    return float(np.degrees(2.0 * np.arctan2(qx, qw)))


def stage_table(stats: dict) -> dict:
    """{stage label: cumulative seconds} from a pstats `stats` dict ({(file, line, name): (cc, nc, tt, ct, callers)}), over the functions in STAGES."""
    out: dict = {}
    for (fname, _, name), (_, _, _, ct, _) in stats.items():
        label = STAGES.get((Path(fname).stem, name))
        if label:
            out[label] = out.get(label, 0.0) + ct
    return out


# ------------------------------------------------------------------------------ first-stride

def _trunk_task(task: dict) -> dict:
    """The rigid trunk's lumbosacral lateral torque row of one stride, its peak, and the root's angular acceleration (body frame, rad/s^2) at that frame."""
    import dynamics
    import gait_extract
    import retarget
    c = gait._ctx(task["model_path"])
    z = gait._subject_arrays(task["processed"], task["subject"])
    sp, i = task["speed"], task["index"]
    sub = task["subject_info"]
    hip = sub.get("hip_in_pelvis_os_m")
    cyc = retarget.Cycle(c.model, c.mapping, c.stand, z[f"{sp}_ik"][i], float(z[f"{sp}_duration_s"][i]), retarget.leg_length_ratio(c.model, sub["height_m"]),
                         cutoff_hz=retarget.CUTOFF_HZ, root_rule="pelvis_dataset", hip_in_pelvis_os=hip, root_ref="hip_midpoint" if hip is not None else "pelvis_origin",
                         pitch_mean="measured", pelvis_frame_offset_deg=gait.frame_offset_deg(task["pelvis_frame_offset"], sub), **gait_extract._variant_kwargs("rigid", sp))
    q, qd, qdd = cyc.grid()
    dof = c.hinge["lsj_lat"][1]
    tau = np.array([dynamics.inverse_frame(c.model, q[k], qd[k], qdd[k])[dof] for k in range(gait.N_FRAMES)])
    k = int(np.argmax(np.abs(tau)))
    return {"subject": task["subject"], "index": i, "peak": float(abs(tau[k])), "frame": k, "alpha": np.abs(qdd[k, 3:6]).tolist(), "alpha_norm": float(np.linalg.norm(qdd[k, 3:6])),
            "omega_norm": float(np.linalg.norm(qd[k, 3:6])), "tau_series": tau.tolist() if task.get("series") else None}


def first_stride(args):
    man = json.loads((REPO / "data/camargo2021/manifest.json").read_text(encoding="utf-8"))
    z = np.load(REPO / f"data/camargo2021/processed/{args.subject}.npz")
    sp = args.speed
    pos = trial_position(z[f"{sp}_t0"], z[f"{sp}_trial"], args.index)
    print(f"{args.subject} stride {args.index} at {sp} m/s: trial {pos['trial']}, rank {pos['rank']} of {pos['strides_in_trial']} by start time (first in trial: {pos['first_in_trial']}), "
          f"starts {pos['start_s']:.3f} s into the trial file, {pos['s_since_first_stride']:.3f} s after the trial's first accepted stride")
    mode = gait.load_spec("walk_treadmill").get("pelvis_frame_offset", "none")
    tasks = [{"model_path": str(gait.simrun.MODEL_FILE), "processed": str(REPO / "data/camargo2021/processed"), "subject": s, "speed": sp, "index": i, "subject_info": info,
              "pelvis_frame_offset": mode} for s, info in man["subjects"].items() for i in range(info["strides"][sp])]
    with ProcessPoolExecutor(max_workers=args.workers) as ex:
        rows = list(ex.map(_trunk_task, tasks, chunksize=8))
    me = next(r for r in rows if r["subject"] == args.subject and r["index"] == args.index)
    peaks = np.array([r["peak"] for r in rows])
    an = np.array([r["alpha_norm"] for r in rows])
    print(f"lsj_lat peak {me['peak']:.1f} N m at frame {me['frame']} (p95 of all strides {np.percentile(peaks, 95):.1f}, median {np.median(peaks):.1f})")
    print(f"trunk (root) angular acceleration at that frame: |alpha| {me['alpha_norm']:.1f} rad/s^2, components (x, y, z) {np.round(me['alpha'], 1).tolist()}; |omega| {me['omega_norm']:.2f} rad/s")
    print(f"  all strides at their own peak frame: |alpha| median {np.median(an):.1f}, p95 {np.percentile(an, 95):.1f}, max {an.max():.1f} rad/s^2; this stride's rank {int((an > me['alpha_norm']).sum()) + 1} of {len(an)}")
    big = sorted(rows, key=lambda r: -r["alpha_norm"])[:5]
    print("  largest |alpha| at a peak: " + ", ".join(f"{r['subject']} {r['index']} ({r['alpha_norm']:.0f})" for r in big))


# ------------------------------------------------------------------------------ profile

def profile(args):
    man = json.loads((REPO / "data/camargo2021/manifest.json").read_text(encoding="utf-8"))
    spec = gait.load_spec("walk_treadmill")
    proc = REPO / spec["dataset"]["processed"]
    full = [t for t in gait._tasks(dict(spec, speeds_mps=[1.4], subjects=["AB06"]), man, gait.simrun.MODEL_FILE, proc, list(spec["methods"]), 6.0, 0.0, None, True, True, True, trunk="rigid")
            if t["index"] < args.strides]
    sens = [dict(t, methods=["B"], sweep=False, agreement=False, kinematics=False) for t in full]
    gait.run_stride(dict(full[0]))  # warm: the context and the arrays are cached per process
    out = {}
    for name, tasks in (("full stride (all methods, sweep, agreement, kinematics)", full), ("sensitivity stride (B only)", sens)):
        pr = cProfile.Profile()
        pr.enable()
        for t in tasks:
            gait.run_stride(dict(t))
        pr.disable()
        st = pstats.Stats(pr)
        total = sum(v[2] for v in st.stats.values())
        out[name] = (total / len(tasks), {k: v / len(tasks) for k, v in stage_table(st.stats).items()})
        print(f"== {name}: {total / len(tasks):.2f} s per stride (profiled, one process)")
        for k, v in sorted(out[name][1].items(), key=lambda kv: -kv[1]):
            print(f"   {k:34s} {v / len(tasks) * len(tasks):6.2f} s")
    n = {sp: sum(i["strides"][sp] for i in man["subjects"].values()) for sp in ("0.5", "1.4", "1.6")}
    total_strides = sum(n.values())
    modes = len(gait.trunk_modes(spec))
    t_full, t_sens = out["full stride (all methods, sweep, agreement, kinematics)"][0], out["sensitivity stride (B only)"][0]
    cap = spec["sensitivity"]["stride_cap_per_subject"]
    sens_strides = sum(min(cap, i["strides"][sp]) for i in man["subjects"].values() for sp in ("0.5", "1.4", "1.6"))
    runs = len(spec["sensitivity"]["cutoffs_hz"]) + len(spec["sensitivity"]["pitch_offsets_deg"])
    main_s, sens_s = total_strides * modes * t_full, sens_strides * runs * modes * t_sens
    print(f"strides {n}, trunk modes {modes}: main run {total_strides * modes} stride-runs x {t_full:.2f} s = {main_s / 60:.0f} CPU min; "
          f"sensitivity {sens_strides} strides x {runs} variants x {modes} modes = {sens_strides * runs * modes} runs x {t_sens:.2f} s = {sens_s / 60:.0f} CPU min; "
          f"sensitivity share {100 * sens_s / (main_s + sens_s):.0f}%; on 6 workers {(main_s + sens_s) / 6 / 60:.0f} min if the scaling were perfect")


# ------------------------------------------------------------------------------ ankle-ie

def subtalar_axes(subject: str) -> dict:
    import xml.etree.ElementTree as ET
    import ingest_camargo as ic
    zf = zipfile.ZipFile(ic.raw_dir() / f"{subject}.zip")
    name = next(n for n in zf.namelist() if n.lower() == f"osimxml/{subject.lower()}.osim")
    root = ET.fromstring(zf.read(name))
    return {j.get("name"): [float(v) for v in j.find(".//TransformAxis/axis").text.split()] for j in root.iter("CustomJoint") if j.get("name", "").startswith("subtalar")}


def ankle_ie(args):
    import ingest_camargo as ic
    man = json.loads((REPO / "data/camargo2021/manifest.json").read_text(encoding="utf-8"))
    axes = subtalar_axes("AB06")
    ax = np.array(axes["subtalar_r"])
    print(f"dataset subtalar axis (OpenSim talus frame; x forward, y up, z right): right {np.round(axes['subtalar_r'], 4).tolist()}, left {np.round(axes['subtalar_l'], 4).tolist()}; "
          f"{np.degrees(np.arccos(abs(ax[0]) / np.linalg.norm(ax))):.1f} degrees from the long axis, vertical component {abs(ax[1]) / np.linalg.norm(ax):.2f}")
    print(f"the model's ankle_ie hinge is the foot's long axis (1 0 0); the twist about it of a 20 degree subtalar rotation is {twist_about_x_deg(ax, 20.0):.1f} degrees, of -20: {twist_about_x_deg(ax, -20.0):.1f}")
    lo = -float(next(float(r.split(",")[1]) for r in (REPO / "params/snapshot.csv").read_text(encoding="utf-8").splitlines() if r.startswith("ankle_eversion,")))
    hi = float(next(float(r.split(",")[1]) for r in (REPO / "params/snapshot.csv").read_text(encoding="utf-8").splitlines() if r.startswith("ankle_inversion,")))
    print(f"sheet limits: eversion {-lo:.1f}, inversion {hi:.1f} degrees (model range {lo:.1f} to {hi:.1f})")
    ch = {side: ic.IK_CHANNELS.index(f"subtalar_angle_{side[0]}") for side in ("right", "left")}
    print(f"{args.speed} m/s, every stride, the dataset's subtalar angle as the model uses it (sign +1): per subject median and share of frames below {lo:.1f}, and after the twist projection")
    tot = {"frames": 0, "below": 0, "below_twist": 0}
    rows = []
    for s in man["subjects"]:
        z = np.load(REPO / f"data/camargo2021/processed/{s}.npz")
        ik = z[f"{args.speed}_ik"]
        for side, c in ch.items():
            a = ik[:, :gait.N_FRAMES, c].ravel()
            tw = np.array([twist_about_x_deg(ax, v) for v in a])  # the left foot is the mirror image (axis and positive direction both mirrored), so the right foot's axis serves both
            rows.append((s, side, float(np.median(a)), float(np.mean(a < lo)), float(np.mean(tw < lo)), float(a.min())))
            tot["frames"] += a.size
            tot["below"] += int((a < lo).sum())
            tot["below_twist"] += int((tw < lo).sum())
    print(f"all subjects: {tot['frames']} frames; below {lo:.1f}: {100 * tot['below'] / tot['frames']:.2f}% as used, {100 * tot['below_twist'] / tot['frames']:.2f}% as the twist about the long axis")
    for r in sorted(rows, key=lambda r: -r[3])[:8]:
        print(f"  {r[0]} {r[1]:5s}: median {r[2]:6.1f} deg, minimum {r[5]:6.1f}, below the limit {100 * r[3]:5.1f}% as used, {100 * r[4]:5.1f}% as twist")
    med = np.array([r[2] for r in rows])
    print(f"  median over subject-sides of the median angle {np.median(med):.1f} deg (range {med.min():.1f} to {med.max():.1f})")


def main(argv=None):
    ap = argparse.ArgumentParser(prog="followup_diag")
    sub = ap.add_subparsers(dest="cmd", required=True)
    f = sub.add_parser("first-stride")
    f.add_argument("--subject", default="AB23")
    f.add_argument("--index", type=int, default=0)
    f.add_argument("--speed", default="0.5")
    f.add_argument("--workers", type=int, default=6)
    p = sub.add_parser("profile")
    p.add_argument("--strides", type=int, default=2)
    a = sub.add_parser("ankle-ie")
    a.add_argument("--speed", default="1.4")
    args = ap.parse_args(argv)
    {"first-stride": first_stride, "profile": profile, "ankle-ie": ankle_ie}[args.cmd](args)


if __name__ == "__main__":
    main()
