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


def force_report(args):
    """Step 1: vertical, fore-aft and mediolateral total force against the measured one, like for like (measured filtered the same
    way), for both root references. Model y is the subject's left; the measured lab x is the right, so the sign is checked too."""
    import mujoco
    import gait_force_report as gfr
    import leanpose
    import retarget
    c = gait._ctx(str(gait.simrun.MODEL_FILE))
    manifest = json.loads((REPO / "data/camargo2021/manifest.json").read_text(encoding="utf-8"))
    for speed in (args.speed,):
        for ref in ("pelvis_origin", "hip_midpoint"):
            rows, mean_lat = [], {"meas": [], "model": []}
            for s, d in manifest["subjects"].items():
                z = np.load(REPO / f"data/camargo2021/processed/{s}.npz")
                ratio = retarget.leg_length_ratio(c.model, d["height_m"])
                for i in range(min(args.cap, d["strides"][speed])):
                    T = float(z[f"{speed}_duration_s"][i])
                    cyc = retarget.Cycle(c.model, c.mapping, c.stand, z[f"{speed}_ik"][i], T, ratio, hip_in_pelvis_os=d["hip_in_pelvis_os_m"], root_ref=ref,
                                         trunk_compensation=args.trunk_compensation)
                    q, qd, qdd = cyc.grid()
                    fb = np.array([gait.dynamics.inverse_frame(c.model, q[k], qd[k], qdd[k])[:3] for k in range(q.shape[0])])
                    fm = gfr.measured_force_model(z[f"{speed}_fp"][i], c.mass / d["mass_kg"])
                    fmf = retarget.filter_cycle(fm, T, 6.0)
                    rows.append(gfr.compare(fb, fmf))
            m = {k: float(np.mean([r[k] for r in rows])) for k in rows[0]}
            print(f"{speed} m/s, root reference {ref}, {len(rows)} strides, like for like at 6 Hz:")
            print("   vertical peak ratio {peak_ratio:.3f} corr {corr:.3f} | fore-aft ptp ratio {ap_ptp_ratio:.3f} corr {ap_corr:.3f} | "
                  "lateral ptp ratio {lat_ptp_ratio:.3f} corr {lat_corr:.3f}, rms {lat_rms_n:.1f} N, mean diff {lat_mean_diff_n:.1f} N".format(**m))


GROUPS = {"legs": ["thigh_right", "shank_right", "foot_right", "thigh_left", "shank_left", "foot_left"], "pelvis": ["pelvis"],
          "trunk": ["abdomen", "thorax", "head_and_neck"],
          "arms": ["upper_arm_right", "forearm_right", "hand_right", "upper_arm_left", "forearm_left", "hand_left"]}


def lateral(args):
    """Which body group carries the mediolateral CoM force: m a_y of each group's centre of mass (second derivative of the
    mass-weighted position of its segments), against the measured lateral force filtered like the kinematics."""
    import mujoco
    import gait_force_report as gfr
    import retarget
    c = gait._ctx(str(gait.simrun.MODEL_FILE))
    m = c.model
    manifest = json.loads((REPO / "data/camargo2021/manifest.json").read_text(encoding="utf-8"))
    ids = {g: [mujoco.mj_name2id(m, mujoco.mjtObj.mjOBJ_BODY, n) for n in v] for g, v in GROUPS.items()}
    for ref in ("pelvis_origin", "hip_midpoint"):
        res, tot, meas = {g: [] for g in GROUPS}, [], []
        for s, d in list(manifest["subjects"].items())[:args.subjects]:
            z = np.load(REPO / f"data/camargo2021/processed/{s}.npz")
            ratio = retarget.leg_length_ratio(m, d["height_m"])
            for i in range(args.cap):
                T = float(z[f"{args.speed}_duration_s"][i])
                cyc = retarget.Cycle(m, c.mapping, c.stand, z[f"{args.speed}_ik"][i], T, ratio, hip_in_pelvis_os=d["hip_in_pelvis_os_m"],
                                     root_ref=ref, trunk_compensation=args.trunk_compensation)

                def moment_y(t):
                    dd = mujoco.MjData(m)
                    dd.qpos[:] = cyc.eval(t)[0]
                    mujoco.mj_kinematics(m, dd)
                    return {g: sum(m.body_mass[b] * dd.xipos[b][1] for b in ids[g]) for g in ids}
                eps, ts = 1e-4, np.linspace(0, T, 100, endpoint=False)
                acc = {g: np.array([(moment_y(t + eps)[g] - 2 * moment_y(t)[g] + moment_y(t - eps)[g]) / eps ** 2 for t in ts]) for g in ids}
                for g in ids:
                    res[g].append(acc[g])
                tot.append(sum(acc.values()))
                meas.append(retarget.filter_cycle(gfr.measured_force_model(z[f"{args.speed}_fp"][i], c.mass / d["mass_kg"]), T, 6.0)[:100, 1])
        tot, meas = np.array(tot), np.array(meas)
        cc = lambda a: np.mean([np.corrcoef(x, y)[0, 1] for x, y in zip(a, meas)])
        print(f"root reference {ref}, trunk compensation {args.trunk_compensation}: lateral force peak-to-peak, N (corr with the measured one)")
        print(f"   measured {np.mean(np.ptp(meas, axis=1)):6.1f}   model total {np.mean(np.ptp(tot, axis=1)):6.1f} ({cc(tot):+.2f})")
        for g in GROUPS:
            a = np.array(res[g])
            print(f"   {g:8s} {np.mean(np.ptp(a, axis=1)):6.1f} ({cc(a):+.2f})")


BINS_MM = (10, 30, 100)


def _bin_counts(distances_m):
    d = 1000 * np.asarray(distances_m)
    return np.array([np.sum(d < BINS_MM[0]), np.sum((d >= BINS_MM[0]) & (d < BINS_MM[1])), np.sum((d >= BINS_MM[1]) & (d < BINS_MM[2])), np.sum(d >= BINS_MM[2])])


def cop_steps(args):
    """Steps 2 to 4: (2) B's whole-body CoP split into the point-mass and angular-momentum terms against the measured CoP;
    (3) double support with the measured force share, and whether the measured share lies inside the feasible bracket;
    (4) the polygon test applied to the measured CoP mapped onto Freyja's foot, with distances and a segment tolerance."""
    import gaitloads
    import retarget
    dyn = gait.dynamics
    c = gait._ctx(str(gait.simrun.MODEL_FILE))
    m = c.model
    manifest = json.loads((REPO / "data/camargo2021/manifest.json").read_text(encoding="utf-8"))
    tol = dyn.SEGMENT_TOL_M
    e_full, e_pm, am = {"single": [], "double": []}, {"single": [], "double": []}, {"single": [], "double": []}
    share = {"n": 0, "bracket": 0, "inside": 0, "nominal_err": [], "meas_share": []}
    poly = {k: {"single": [0, 0, []], "double": [0, 0, []]} for k in ("measured", "B_nominal", "B_measured_share", "measured_tol", "B_nominal_tol", "B_measured_share_tol")}
    for s, d in manifest["subjects"].items():
        z = np.load(REPO / f"data/camargo2021/processed/{s}.npz")
        ratio = retarget.leg_length_ratio(m, d["height_m"])
        hip = d["hip_in_pelvis_os_m"]
        for i in range(min(args.cap, d["strides"][args.speed])):
            T = float(z[f"{args.speed}_duration_s"][i])
            ik, fp = z[f"{args.speed}_ik"][i], z[f"{args.speed}_fp"][i]
            cyc = retarget.Cycle(m, c.mapping, c.stand, ik, T, ratio, hip_in_pelvis_os=hip, trunk_compensation=args.trunk_compensation)
            q, qd, qdd = cyc.grid()
            ref_lab = retarget.dataset_hip_mid_lab(ik, hip)
            for k in range(100):
                stance = tuple(f for j, f in enumerate(gait.FEET) if fp[j, k, 6] >= gaitloads.STANCE_FLAG)
                if not stance:
                    continue
                key = "single" if len(stance) == 1 else "double"
                qfrc = dyn.inverse_frame(m, q[k], qd[k], qdd[k])
                mf, mc = gaitloads.measured_to_model(fp[:, k, :], ref_lab[k], retarget.model_hip_mid(m, q[k])[:2], c.mass / d["mass_kg"], ratio)
                fz = np.array([mf[f][2] for f in stance])
                meas = sum(w * mc[f][:2] for w, f in zip(fz, stance)) / fz.sum()
                full, pm, amt = dyn.cop_decomposition(m, q[k], qfrc)
                e_full[key].append(full[:2] - meas); e_pm[key].append(pm[:2] - meas); am[key].append(amt[:2])
                r = dyn.solve_frame(m, q[k], qd[k], qdd[k], stance=stance, sweep=True, qfrc=qfrc)
                variants = {"B_nominal": r}
                if key == "double" and len(mf) == 2:
                    sm = mf["foot_right"][2] / (mf["foot_right"][2] + mf["foot_left"][2])
                    share["n"] += 1
                    share["nominal_err"].append(r.split_right - sm); share["meas_share"].append(sm)
                    if r.feasible_split is not None:
                        share["bracket"] += 1
                        share["inside"] += r.feasible_split[0] - 0.026 <= sm <= r.feasible_split[1] + 0.026  # the sweep step is 0.05
                    variants["B_measured_share"] = dyn.solve_frame(m, q[k], qd[k], qdd[k], stance=stance, qfrc=qfrc, split_right_override=sm)
                for f in stance:
                    for name, tl in (("", 0.0), ("_tol", tol)):
                        mg, _ = dyn.foot_polygon_margin(m, q[k], f, mc[f][:2], segment_tol_m=tl)
                        poly["measured" + name][key][0] += 1; poly["measured" + name][key][1] += not mg >= 0
                        if not mg >= 0:
                            poly["measured" + name][key][2].append(-mg)
                        for vname, rr in variants.items():
                            mg, _ = dyn.foot_polygon_margin(m, q[k], f, rr.cop[f][:2], segment_tol_m=tl)
                            poly[vname + name][key][0] += 1; poly[vname + name][key][1] += not mg >= 0
                            if not mg >= 0:
                                poly[vname + name][key][2].append(-mg)
    print(f"=== {args.speed} m/s, {args.cap} strides per subject, trunk compensation {args.trunk_compensation} ===")
    print("Step 2: whole-body CoP against the measured one (model axes: x fore-aft, y lateral), rms mm over stance frames")
    for key in ("single", "double"):
        ef, ep, a = (np.array(x[key]) for x in (e_full, e_pm, am))
        rms = lambda x: np.sqrt((x ** 2).mean(axis=0)) * 1000
        print(f"   {key:6s} {len(ef):6d} frames | B full error x {rms(ef)[0]:5.0f} y {rms(ef)[1]:5.0f} | point-mass-only error x {rms(ep)[0]:5.0f} y {rms(ep)[1]:5.0f} | angular-momentum term rms x {rms(a)[0]:5.0f} y {rms(a)[1]:5.0f}")
    print(f"Step 3: double support frames {share['n']}; nominal-rule share minus measured: mean {np.mean(share['nominal_err']):+.2f} rms {np.sqrt(np.mean(np.square(share['nominal_err']))):.2f}; "
          f"measured share mean {np.mean(share['meas_share']):.2f}")
    print(f"   a feasible bracket exists in {share['bracket']} frames ({100 * share['bracket'] / share['n']:.1f}%); the measured share is inside it in {share['inside']} ({100 * share['inside'] / share['n']:.1f}% of all double-support frames)")
    print("Step 4: CoP outside the foot's contact polygon (hull within 25 mm of the lowest vertex); strict, then with a 25 mm band for segment polygons")
    print("   source                         support   frames  outside %   median dist mm   <10 / 10-30 / 30-100 / >100 mm (% of frames)")
    for name in poly:
        for key in ("single", "double"):
            n, o, dist = poly[name][key]
            if not n:
                continue
            b = 100 * _bin_counts(dist) / n if dist else np.zeros(4)
            med = 1000 * np.median(dist) if dist else 0.0
            print(f"   {name:30s} {key:7s} {n:7d} {100 * o / n:9.1f} {med:15.0f}   " + " / ".join(f"{x:5.1f}" for x in b))


def main(argv=None):
    ap = argparse.ArgumentParser(prog="gait_diag")
    sub = ap.add_subparsers(dest="cmd", required=True)
    a = sub.add_parser("a-agreement")
    a.add_argument("--root-reference", default="hip_midpoint", choices=["hip_midpoint", "pelvis_origin"])
    a.add_argument("--cap", type=int, default=3)
    a.add_argument("--speed", default="1.4")
    a.add_argument("--workers", type=int, default=5)
    f = sub.add_parser("force")
    f.add_argument("--cap", type=int, default=5)
    f.add_argument("--speed", default="1.4")
    f.add_argument("--trunk-compensation", action="store_true")
    cp = sub.add_parser("cop")
    cp.add_argument("--cap", type=int, default=4)
    cp.add_argument("--speed", default="1.4")
    cp.add_argument("--trunk-compensation", action="store_true")
    la = sub.add_parser("lateral")
    la.add_argument("--cap", type=int, default=3)
    la.add_argument("--subjects", type=int, default=6)
    la.add_argument("--speed", default="1.4")
    la.add_argument("--trunk-compensation", action="store_true")
    args = ap.parse_args(argv)
    {"a-agreement": a_agreement, "force": force_report, "lateral": lateral, "cop": cop_steps}[args.cmd](args)


if __name__ == "__main__":
    main()
