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
import gait_extract  # noqa: E402
from gait_extract import (LSJ, VARIANTS, _lsj_task, _pool, _variant_kwargs, distribution, joint_metrics, ols, peak_extension_deg, peak_stats,  # noqa: E402,F401
                          quartile_corners, thigh_world_deg)

REPO = gait.REPO
SAGITTAL = ("hip_fe", "knee", "ankle_pdflex")
TARGET_CORR, TARGET_RMS_PCT = 0.9, 15.0  # review targets from the brief, not acceptance limits


def _pitch(v):
    """--pitch-mean: "measured" or a number of degrees."""
    return v if v == "measured" else float(v)


def _rows(spec, methods, cap, speed, workers, **overrides):
    spec = dict(spec)
    spec.update({"speeds_mps": [speed], "stride_cap_per_subject": cap, **overrides})
    manifest = json.loads((REPO / spec["dataset"]["manifest"]).read_text(encoding="utf-8"))
    tasks = gait._tasks(spec, manifest, gait.simrun.MODEL_FILE, REPO / spec["dataset"]["processed"], methods,
                        float(spec["smoothing"]["cutoff_hz"]), float(spec["pelvis_pitch_offset_deg"]), cap, True, True, False)
    return gait._run_tasks(tasks, workers)


def a_agreement(args):
    spec = gait.load_spec("walk_treadmill")
    spec["root_reference"] = args.root_reference
    rows = _rows(spec, ["A_native", "A_filtered"], args.cap, args.speed, args.workers, cop_mode=args.cop_mode, pitch_mean=_pitch(args.pitch_mean))
    print(f"A agreement with the dataset moments; root reference {args.root_reference}; CoP mode {args.cop_mode}; pelvis pitch mean {args.pitch_mean}; {len(rows)} strides at {args.speed} m/s")
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
                                         trunk=args.trunk)
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
                                     root_ref=ref, trunk=args.trunk)

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
        print(f"root reference {ref}, trunk {args.trunk}: lateral force peak-to-peak, N (corr with the measured one)")
        print(f"   measured {np.mean(np.ptp(meas, axis=1)):6.1f}   model total {np.mean(np.ptp(tot, axis=1)):6.1f} ({cc(tot):+.2f})")
        for g in GROUPS:
            a = np.array(res[g])
            print(f"   {g:8s} {np.mean(np.ptp(a, axis=1)):6.1f} ({cc(a):+.2f})")


def foot_report(args):
    """T3c.0(c): the retargeted root's stance float, penetration, swing clearance and slip, with the root referenced to the
    pelvis origin and to the midpoint of the hip joint centres. The same statistic as GAIT.md's kinematics diagnostics: the mean
    over subject-strides of each stride's maximum float / maximum penetration / minimum clearance / rms slip."""
    import retarget
    c = gait._ctx(str(gait.simrun.MODEL_FILE))
    manifest = json.loads((REPO / "data/camargo2021/manifest.json").read_text(encoding="utf-8"))
    for ref in ("pelvis_origin", "hip_midpoint"):
        met = {}
        for s, d in manifest["subjects"].items():
            z = np.load(REPO / f"data/camargo2021/processed/{s}.npz")
            ratio = retarget.leg_length_ratio(c.model, d["height_m"])
            for i in range(min(args.cap, d["strides"][args.speed])):
                cyc = retarget.Cycle(c.model, c.mapping, c.stand, z[f"{args.speed}_ik"][i], float(z[f"{args.speed}_duration_s"][i]), ratio,
                                     hip_in_pelvis_os=d["hip_in_pelvis_os_m"], root_ref=ref, trunk=args.trunk, pitch_mean=_pitch(args.pitch_mean))
                m = retarget.foot_metrics(c.model, cyc, z[f"{args.speed}_fp"][i][:, :, 6] >= 0.5, float(args.speed))
                for k, v in m.items():
                    met.setdefault(k, []).append(v)
        print(f"{args.speed} m/s, root reference {ref}, trunk {args.trunk}, pitch mean {args.pitch_mean}, {len(met['stance_float_max_m'])} strides: "
              f"stance float {1000 * np.mean(met['stance_float_max_m']):.1f} mm (mean of per-stride maxima), penetration {1000 * np.mean(met['stance_penetration_max_m']):.1f} mm, "
              f"swing clearance minimum {1000 * np.mean(met['swing_clearance_min_m']):.1f} mm, stance slip rms {np.mean(met['stance_slip_rms_mps']):.2f} m/s")


def trunk_report(args):
    """T3c.1: the two trunk modes side by side for B, H and A: total lateral force (like for like), agreement with the dataset's moments
    for hip ab/adduction, hip rotation and ankle inversion, A's root-row residual, and the lumbosacral lateral and axial joints' loads."""
    spec = gait.load_spec("walk_treadmill")
    c = gait._ctx(str(gait.simrun.MODEL_FILE))
    for speed in args.speeds:
        for trunk in ("rigid", "counter_rotate"):
            rows = _rows(spec, ["B", "A_native", "A_filtered", "H"], args.cap, speed, args.workers, trunk=trunk, pitch_mean="measured")
            res = gait.build_results(rows, c, {**spec, "speeds_mps": [float(speed)]})[speed]
            mean = lambda stat: stat["all"]["mean"]
            f = res["force"]
            print(f"=== {speed} m/s, trunk {trunk}, {len(rows)} strides, pitch mean measured ===")
            print("Freyja's total force (B and H use it; A uses the measured one), like for like: vertical peak ratio {:.2f} corr {:.2f} | fore-aft ptp ratio {:.2f} corr {:.2f} | "
                  "lateral ptp ratio {:.2f} corr {:.2f}".format(*(mean(f[k]) for k in ("vert_peak_ratio", "vert_corr", "ap_ptp_ratio", "ap_corr", "lat_ptp_ratio", "lat_corr"))))
            print("A root-row residual (mean over strides): " + "; ".join(
                f"{m}: force {mean(res['residual'][m]['force_rms_pct_bw']):.1f}% BW rms, horizontal moment {mean(res['residual'][m]['moment_h_rms_nm']):.1f} N m rms, vertical moment {mean(res['residual'][m]['yaw_rms_nm']):.1f}"
                for m in ("A_native", "A_filtered", "H", "B")))
            print("agreement with the dataset's moments (both limbs pooled): joint, method, corr, rms % of ptp, peak diff N m/kg")
            for stem in ("hip_aa", "hip_ier", "ankle_ie"):
                for m in ("B", "H", "A_native", "A_filtered"):
                    a = [res["agreement"][m][f"{stem}_{s}"] for s in ("right", "left")]
                    print(f"   {stem:9s} {m:10s} {np.mean([x['corr'] for x in a]):+.2f} {np.mean([x['rms_pct_ptp'] for x in a]):6.1f} {np.mean([x['peak_diff'] for x in a]):+.2f}")
            for j in gait.TRUNK_ANGLE_JOINTS:
                ang = np.array([r["trunk_peak_deg"][j] for r in rows])
                jd = res["joints"][j]["B"]
                print(f"   {j}: peak angle deg median {np.median(ang):.2f} p95 {np.percentile(ang, 95):.2f} max {ang.max():.2f} | peak torque N m mean/p95/max "
                      f"{jd['peak_torque_nm']['all']['mean']:.1f}/{jd['peak_torque_nm']['all']['p95']:.1f}/{jd['peak_torque_nm']['all']['max']:.1f} | peak speed rad/s p95 {jd['peak_speed_rad_s']['all']['p95']:.2f} "
                      f"| power W p95 {jd['peak_power_pos_w']['all']['p95']:.0f} / regen {jd['peak_regeneration_w']['all']['p95']:.0f}")


def trunk_imu_report(args):
    """T3c.2: the trunk's roll and yaw relative to the pelvis's from the trunk IMU (no shoulder markers exist), per speed: amplitude
    ratio, phase lag and cancelled fraction, median and spread across subjects (each subject's value is the median over its strides)."""
    import retarget
    import trunkimu
    manifest = json.loads((REPO / "data/camargo2021/manifest.json").read_text(encoding="utf-8"))
    names = ["roll", "yaw", "pitch"]  # pelvis axes x forward, y up, z right -> columns 0, 1, 2 of the body-frame vectors
    axis_col = {"roll": 0, "yaw": 1, "pitch": 2}
    prep = {}
    for s in manifest["subjects"]:
        z = np.load(REPO / f"data/camargo2021/processed/{s}.npz")
        prep[s] = {}
        for sp in args.speeds:
            rows = []
            for i in range(len(z[f"{sp}_duration_s"])):
                ik = z[f"{sp}_ik"][i]
                T = float(z[f"{sp}_duration_s"][i])
                drift = lambda x: (x - np.outer(np.linspace(0, 1, 101), x[-1] - x[0]))[:100]  # periodic: the stride's linear drift removed
                ang = np.deg2rad(drift(ik[:, :3]))  # tilt, list, rotation
                pos = drift(ik[:, 3:6])
                lp = lambda x: retarget.filter_cycle(np.vstack([x, x[:1]]), T, 6.0)[:100]  # the same zero-lag 6 Hz as the kinematics, on both sides
                rows.append({"T": T, "ang": ang, "w_p": trunkimu.pelvis_body_omega(ang, T), "f_p": lp(trunkimu.pelvis_specific_force(pos, ang, T)),
                             "acc": lp(z[f"{sp}_trunk_imu"][i][:100, :3]), "gyro": z[f"{sp}_trunk_imu"][i][:100, 3:6]})
            prep[s][sp] = rows
    summary = {sp: {a: {"amplitude_ratio": [], "phase_lag_deg": [], "cancelled_fraction": [], "pelvis_amp_deg": [], "trunk_amp_deg": []} for a in names} for sp in args.speeds}
    quality, gains = [], {a: [] for a in names}
    within = {sp: {a: {k: [] for k in ("amplitude_ratio", "phase_lag_deg")} for a in names} for sp in args.speeds}  # stride-to-stride IQR inside each kept subject
    kept = []
    for s in manifest["subjects"]:
        allrows = [r for sp in args.speeds for r in prep[s][sp]]
        R, q = trunkimu.align_sensor_to_pelvis(np.concatenate([r["acc"] for r in allrows]), np.concatenate([r["f_p"] for r in allrows]))
        quality.append(q)
        if q.min() < args.min_quality:
            continue  # the IMU could not be aligned to the pelvis frame well enough for this subject
        kept.append((s, q))
        for sp in args.speeds:
            per = {a: {k: [] for k in summary[sp][a]} for a in names}
            for r in prep[s][sp]:
                w_t = (r["gyro"] * args.gyro_unit) @ R.T
                th_t, th_p = trunkimu.angle_from_rate(w_t, r["T"]), trunkimu.angle_from_rate(r["w_p"], r["T"])
                for a in names:
                    c = axis_col[a]
                    h = trunkimu.harmonic_ratio(th_t[:, c], th_p[:, c])
                    for k in ("amplitude_ratio", "phase_lag_deg", "cancelled_fraction"):
                        per[a][k].append(h[k])
                    per[a]["pelvis_amp_deg"].append(np.degrees(abs(trunkimu.first_harmonic(th_p[:, c]))))
                    per[a]["trunk_amp_deg"].append(np.degrees(abs(trunkimu.first_harmonic(th_t[:, c]))))
                    gains[a].append(np.sqrt(np.mean(w_t[:, c] ** 2) / np.mean(r["w_p"][:, c] ** 2)))
            for a in names:
                for k in per[a]:
                    summary[sp][a][k].append(float(np.median(per[a][k])))
                for k in within[sp][a]:
                    within[sp][a][k].append(float(np.subtract(*np.percentile(per[a][k], [75, 25]))))
    q = np.array(quality)
    print(f"alignment of the IMU to the pelvis frame: accelerometer correlation per pelvis axis (x fwd, y up, z right), median over {len(q)} subjects "
          f"{np.median(q[:, 0]):.2f} / {np.median(q[:, 1]):.2f} / {np.median(q[:, 2]):.2f}, worst {q[:, 0].min():.2f} / {q[:, 1].min():.2f} / {q[:, 2].min():.2f}")
    print("gyro rms over pelvis rms with the gyro read as rad/s (a unit error would show as ~57 or ~0.017): " + ", ".join(f"{a} {np.median(gains[a]):.2f}" for a in names))
    for sp in args.speeds:
        print(f"=== {sp} m/s: median [lower quartile, upper quartile] (min..max) across {len(summary[sp]['roll']['amplitude_ratio'])} subjects ===")
        for a in names:
            def f(k, nd=2):
                v = np.array(summary[sp][a][k])
                return f"{np.median(v):.{nd}f} [{np.percentile(v, 25):.{nd}f}, {np.percentile(v, 75):.{nd}f}] ({v.min():.{nd}f}..{v.max():.{nd}f})"
            print(f"  {a:5s} pelvis amplitude {f('pelvis_amp_deg', 1)} deg | trunk amplitude {f('trunk_amp_deg', 1)} deg | ratio {f('amplitude_ratio')} | "
                  f"phase lag {f('phase_lag_deg', 0)} deg | cancelled fraction {f('cancelled_fraction')}")
    return {"summary": summary, "within": within, "kept": [k[0] for k in kept], "quality": np.array([k[1] for k in kept])}


def double_report(args):
    """T3c.3: double-support feasibility. B's total CoP (fixed by the root rows) against the hull of the two contact polygons, with the
    measured total CoP (force-weighted mean of the per-plate CoPs placed on Freyja's feet) as the baseline; whether the nominal split and
    the measured share lie in the feasible set; the bound against the nominal torque against A."""
    import gaitloads
    import retarget
    dyn = gait.dynamics
    spec = gait.load_spec("walk_treadmill")
    c = gait._ctx(str(gait.simrun.MODEL_FILE))
    m = c.model
    manifest = json.loads((REPO / "data/camargo2021/manifest.json").read_text(encoding="utf-8"))
    for speed in args.speeds:
        for trunk in ("rigid", "counter_rotate"):
            rows = _rows(spec, ["B", "A_filtered"], args.cap, speed, args.workers, trunk=trunk, pitch_mean="measured")
            res = gait.build_results(rows, c, {**spec, "speeds_mps": [float(speed)]})[speed]
            fe = res["feasibility"]
            # measured baseline and measured-share test, frame by frame (the same strides, the same retargeting)
            base_out, base_n, share_in, share_n = [], 0, 0, 0
            for s, d in manifest["subjects"].items():
                z = np.load(REPO / f"data/camargo2021/processed/{s}.npz")
                ratio = retarget.leg_length_ratio(m, d["height_m"])
                for i in range(min(args.cap, d["strides"][speed])):
                    fp, fmk = z[f"{speed}_fp"][i], z[f"{speed}_foot_markers"][i]
                    cyc = retarget.Cycle(m, c.mapping, c.stand, z[f"{speed}_ik"][i], float(z[f"{speed}_duration_s"][i]), ratio,
                                         hip_in_pelvis_os=d["hip_in_pelvis_os_m"], trunk=trunk, pitch_mean="measured")
                    q, qd, qdd = cyc.grid()
                    for k in range(100):
                        if not (fp[0, k, 6] >= 0.5 and fp[1, k, 6] >= 0.5):
                            continue
                        mf, mc = gaitloads.measured_to_model_foot(fp[:, k, :], fmk[k], dyn.foot_floor_segments(m, q[k]), c.mass / d["mass_kg"])
                        w = np.array([mf["foot_right"][2], mf["foot_left"][2]])
                        p_meas = (w[0] * mc["foot_right"][:2] + w[1] * mc["foot_left"][:2]) / w.sum()
                        dd = mujoco_data(m, q[k])
                        polys = tuple(dyn.contact_polygon(dyn._foot_boxes(m, dd, mujoco_body(m, f))[0]) for f in gait.FEET)
                        out = dyn.double_support_set(polys[0], polys[1], p_meas, n_alpha=2)
                        base_n += 1
                        if not out["feasible"]:
                            base_out.append(out["outside_m"])
                        qfrc = dyn.inverse_frame(m, q[k], qd[k], qdd[k])
                        full = dyn.cop_decomposition(m, q[k], qfrc)[0]
                        share_n += 1
                        share_in += dyn.share_in_set(polys[0], polys[1], full[:2], w[0] / w.sum())
            dist = lambda v: f"median {1000 * np.median(v):.0f} mm, 95th {1000 * np.percentile(v, 95):.0f} mm" if len(v) else "none"
            od = fe.get("outside_distance_double_support_m")
            print(f"=== {speed} m/s, trunk {trunk}, {args.cap} strides per subject ===")
            print(f"B double support: {100 * fe['cop_outside_fraction_double_support']:.1f}% of frames infeasible (total CoP outside the hull), outside distance "
                  f"{('median %.0f mm, 95th %.0f mm' % (1000 * od['median'], 1000 * od['p95'])) if od else 'none'}")
            print(f"measured total CoP on Freyja's feet (baseline): {100 * len(base_out) / base_n:.1f}% of {base_n} double-support frames outside the hull, outside distance {dist(base_out)}")
            print(f"nominal proportional split lies in the feasible set (B's total CoP): {100 * fe['double_support_nominal_split_in_feasible_set_fraction']:.1f}% of frames; "
                  f"nominal rule's own CoP placement fails in {100 * fe['double_support_nominal_rule_placement_fails_fraction']:.1f}%; "
                  f"measured share lies in the feasible set: {100 * share_in / share_n:.1f}% of {share_n} frames")
            print("peak torque N m, mean / 95th over strides: joint | nominal B | bound B | A_filtered")
            for j in ("hip_fe_right", "knee_right", "ankle_pdflex_right", "hip_aa_right", "hip_fe_left", "knee_left", "ankle_pdflex_left"):
                nb, bb, aa = res["joints"][j]["B"]["peak_torque_nm"]["all"], res["bound"][j]["all"], res["joints"][j]["A_filtered"]["peak_torque_nm"]["all"]
                print(f"   {j:20s} {nb['mean']:6.1f} / {nb['p95']:6.1f} | {bb['mean']:6.1f} / {bb['p95']:6.1f} | {aa['mean']:6.1f} / {aa['p95']:6.1f}")


def mujoco_data(model, q):
    import mujoco
    d = mujoco.MjData(model)
    d.qpos[:] = q
    mujoco.mj_kinematics(model, d)
    return d


def mujoco_body(model, name):
    import mujoco
    return mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_BODY, name)


def polygon_report(args):
    """T3c.4: the polygon test for B beside the measured CoP placed on Freyja's feet, single and double support, at polygon bands of 10, 25
    and 40 mm; and B's median outside distance at the measured pitch and plus and minus 5 degrees (a diagnostic, not a design choice)."""
    spec = gait.load_spec("walk_treadmill")
    c = gait._ctx(str(gait.simrun.MODEL_FILE))
    ms = lambda v: "-" if v is None else f"{1000 * v:.0f}"
    for speed in args.speeds:
        for trunk in ("rigid", "counter_rotate"):
            print(f"=== {speed} m/s, trunk {trunk}, {args.cap} strides per subject, pitch mean measured ===")
            for off in (0.0, -5.0, 5.0):
                rows = _rows(spec, ["B"], args.cap, speed, args.workers, trunk=trunk, pitch_mean="measured", pelvis_pitch_offset_deg=off)
                res = gait.build_results(rows, c, {**spec, "speeds_mps": [float(speed)], "pelvis_pitch_offset_deg": off})[speed][trunk]["feasibility"]
                pg = res["polygon"]
                if off == 0.0:
                    print("band mm | support | B outside % | B median / p95 mm | measured outside % | measured median / p95 mm")
                    for b in pg["B"]:
                        for key in ("single", "double"):
                            x, y = pg["B"][b][key], pg["measured"][b][key]
                            r = lambda z: "-" if z["outside_fraction"] is None else f"{100 * z['outside_fraction']:.1f}"
                            print(f"  {1000 * float(b):4.0f}   {key:7s}  {r(x):>6s}   {ms(x['median_outside_m']):>4s} / {ms(x['p95_outside_m']):>4s}      {r(y):>6s}   {ms(y['median_outside_m']):>4s} / {ms(y['p95_outside_m']):>4s}")
                b25 = pg["B"]["0.025"]
                print(f"  pitch offset {off:+.0f} deg: B median outside distance at 25 mm: single {ms(b25['single']['median_outside_m'])} mm "
                      f"(outside {100 * b25['single']['outside_fraction']:.1f}%), double {ms(b25['double']['median_outside_m'])} mm (outside {100 * b25['double']['outside_fraction']:.1f}%)")


def _single_support_frames(args, trunk, model_for_loads=None):
    """Yield (subject, stride data, frame k, stance foot, cycle q/qd/qdd, ref_lab, ratio, subject info) for every single-support frame."""
    import gaitloads
    import retarget
    c = gait._ctx(str(gait.simrun.MODEL_FILE))
    manifest = json.loads((REPO / "data/camargo2021/manifest.json").read_text(encoding="utf-8"))
    for s, d in manifest["subjects"].items():
        z = np.load(REPO / f"data/camargo2021/processed/{s}.npz")
        ratio = retarget.leg_length_ratio(c.model, d["height_m"])
        for i in range(min(args.cap, d["strides"][args.speed])):
            ik, fp, fmk = z[f"{args.speed}_ik"][i], z[f"{args.speed}_fp"][i], z[f"{args.speed}_foot_markers"][i]
            cyc = retarget.Cycle(c.model, c.mapping, c.stand, ik, float(z[f"{args.speed}_duration_s"][i]), ratio,
                                 hip_in_pelvis_os=d["hip_in_pelvis_os_m"], trunk=trunk, pitch_mean="measured")
            q, qd, qdd = cyc.grid()
            ref_lab = retarget.dataset_hip_mid_lab(ik, d["hip_in_pelvis_os_m"])
            for k in range(100):
                stance = [f for j, f in enumerate(gait.FEET) if fp[j, k, 6] >= gaitloads.STANCE_FLAG]
                if len(stance) == 1:
                    yield dict(subject=s, d=d, k=k, foot=stance[0], q=q[k], qd=qd[k], qdd=qdd[k], fp=fp[:, k, :], fmk=fmk[k], ref_lab=ref_lab[k], ratio=ratio)


def swing_report(args):
    """T3c.5a: B's single-support CoP by segment group (stance leg, swing leg, pelvis and trunk): where each group's mass sits relative to
    the stance ankle and what its motion adds, with the measured CoP's offset from the ankle for reference."""
    import gaitloads
    import mujoco
    import partition
    dyn = gait.dynamics
    c = gait._ctx(str(gait.simrun.MODEL_FILE))
    m = c.model
    for trunk in ("rigid", "counter_rotate"):
        com, dyn_t, b_off, m_off, err = {}, {}, [], [], []
        for fr in _single_support_frames(args, trunk):
            d = mujoco_data(m, fr["q"])
            ankle = d.xpos[mujoco_body(m, fr["foot"])][:2].copy()
            parts = partition.cop_partition(m, fr["q"], fr["qd"], fr["qdd"], fr["foot"], ankle_xy=ankle)
            full = dyn.cop_decomposition(m, fr["q"], dyn.inverse_frame(m, fr["q"], fr["qd"], fr["qdd"]))[0][:2]
            mf, mc = gaitloads.measured_to_model_foot(fr["fp"], fr["fmk"], dyn.foot_floor_segments(m, fr["q"]), c.mass / fr["d"]["mass_kg"])
            for g, v in parts.items():
                com.setdefault(g, []).append((v["mass_fraction"], *v["com_minus_ankle_xy"]))
                dyn_t.setdefault(g, []).append(v["dynamic_xy"])
            b_off.append(full - ankle); m_off.append(mc[fr["foot"]][:2] - ankle); err.append(full - mc[fr["foot"]][:2])
        mm = lambda a, nd=0: "(" + ", ".join(f"{1000 * v:.{nd}f}" for v in a) + ")"
        print(f"=== {args.speed} m/s, trunk {trunk}, {len(b_off)} single-support frames: offsets from the stance ankle, mm (x fore-aft, y lateral) ===")
        print("group          mass %   where its mass sits: mean / rms        what its motion adds: mean / rms")
        for g in com:
            cm, dy = np.array(com[g]), np.array(dyn_t[g])
            print(f"  {g:13s} {100 * cm[:, 0].mean():5.1f}   {mm(cm[:, 1:].mean(axis=0)):>14s} / {mm(np.sqrt((cm[:, 1:] ** 2).mean(axis=0))):>14s}      {mm(dy.mean(axis=0)):>14s} / {mm(np.sqrt((dy ** 2).mean(axis=0))):>14s}")
        b_off, m_off, err = np.array(b_off), np.array(m_off), np.array(err)
        print(f"  B CoP minus ankle: mean {mm(b_off.mean(axis=0))}, rms {mm(np.sqrt((b_off ** 2).mean(axis=0)))} | measured CoP minus ankle: mean {mm(m_off.mean(axis=0))}, rms {mm(np.sqrt((m_off ** 2).mean(axis=0)))} "
              f"| B minus measured: mean {mm(err.mean(axis=0))}, rms {mm(np.sqrt((err ** 2).mean(axis=0)))}")


def masses_report(args):
    """T3c.5b: the same B CoP with the dataset model's segment masses and centres of mass in an in-memory copy of Freyja's model (never saved)."""
    import gaitloads
    import datasetmass
    import retarget
    import zipfile
    dyn = gait.dynamics
    c = gait._ctx(str(gait.simrun.MODEL_FILE))
    m = c.model
    copies = {}
    for trunk in ("rigid", "counter_rotate"):
        rows = {"freyja": [], "dataset masses": []}
        for fr in _single_support_frames(args, trunk):
            s = fr["subject"]
            if s not in copies:
                table = datasetmass.read_body_table(zipfile.ZipFile(ic_raw() / f"{s}.zip"), s)
                copies[s] = datasetmass.with_dataset_masses(m, table, fr["ratio"], fr["d"]["hip_in_pelvis_os_m"][:2])
            mf, mc = gaitloads.measured_to_model_foot(fr["fp"], fr["fmk"], dyn.foot_floor_segments(m, fr["q"]), c.mass / fr["d"]["mass_kg"])
            for label, mod in (("freyja", m), ("dataset masses", copies[s])):
                full = dyn.cop_decomposition(mod, fr["q"], dyn.inverse_frame(mod, fr["q"], fr["qd"], fr["qdd"]))[0][:2]
                rows[label].append(full - mc[fr["foot"]][:2])
        print(f"=== {args.speed} m/s, trunk {trunk}, single support ({len(rows['freyja'])} frames): B CoP minus measured CoP, rms mm (x fore-aft, y lateral) ===")
        for label, r in rows.items():
            r = np.array(r)
            print(f"  {label:15s} x {1000 * np.sqrt((r[:, 0] ** 2).mean()):5.0f}  y {1000 * np.sqrt((r[:, 1] ** 2).mean()):5.0f}   mean x {1000 * r[:, 0].mean():+5.0f}  y {1000 * r[:, 1].mean():+5.0f}")


def ic_raw():
    import ingest_camargo as ic
    return ic.raw_dir()


def placement_report(args):
    """T3c.5c: the lateral offset of each stance foot against the measured CoP's lateral position, and B's, in single support. The measured
    CoP is placed by its position relative to the hip-centre midpoint (not on the foot), so this measures where Freyja's foot is, not
    where her CoP is on it."""
    import gaitloads
    import retarget
    dyn = gait.dynamics
    c = gait._ctx(str(gait.simrun.MODEL_FILE))
    m = c.model
    for trunk in ("rigid", "counter_rotate"):
        foot_y, meas_y, b_y, foot_x, meas_x, width = [], [], [], [], [], []
        for fr in _single_support_frames(args, trunk):
            d = mujoco_data(m, fr["q"])
            seg = dyn.foot_floor_segments(m, fr["q"])[fr["foot"]]
            centre = 0.5 * (seg[0] + seg[1])
            mf, mc = gaitloads.measured_to_model(fr["fp"], fr["ref_lab"], retarget.model_hip_mid(m, fr["q"])[:2], c.mass / fr["d"]["mass_kg"], fr["ratio"])
            full = dyn.cop_decomposition(m, fr["q"], dyn.inverse_frame(m, fr["q"], fr["qd"], fr["qdd"]))[0][:2]
            foot_y.append(centre[1]); meas_y.append(mc[fr["foot"]][1]); b_y.append(full[1]); foot_x.append(centre[0]); meas_x.append(mc[fr["foot"]][0])
            width.append(d.xpos[mujoco_body(m, "foot_left")][1] - d.xpos[mujoco_body(m, "foot_right")][1])
        foot_y, meas_y, b_y, foot_x, meas_x, width = map(np.array, (foot_y, meas_y, b_y, foot_x, meas_x, width))
        mm = lambda v: f"{1000 * np.mean(v):+.0f} +/- {1000 * np.std(v):.0f}"
        print(f"=== {args.speed} m/s, trunk {trunk}, {len(foot_y)} single-support frames (mm, mean +/- sd; stance side sign folded so + is lateral) ===")
        print(f"  stance foot centre minus measured CoP: lateral {mm(foot_y - meas_y)} (signed model y), fore-aft {mm(foot_x - meas_x)}")
        print(f"  B CoP minus stance foot centre, lateral: {mm(b_y - foot_y)}; B CoP minus measured CoP, lateral: {mm(b_y - meas_y)}")
        print(f"  Freyja's ankle-to-ankle width in single support: {mm(np.abs(width))}")


def pushoff_report(args):
    """T3c.4 (toe question): can a rigid, toeless foot box represent push-off? The measured CoP, placed on Freyja's foot at the same
    normalised place, tested against that foot's contact polygon, by stance-phase decile of each foot's own stance (0 = heel strike of that
    foot, 100 = its toe-off), single support and double support separately; with the foot's pitch (heel height above the toe) beside it."""
    import gaitloads
    import retarget
    dyn = gait.dynamics
    c = gait._ctx(str(gait.simrun.MODEL_FILE))
    m = c.model
    manifest = json.loads((REPO / "data/camargo2021/manifest.json").read_text(encoding="utf-8"))
    bins = {k: [[] for _ in range(10)] for k in ("single", "double")}
    pitch = [[] for _ in range(10)]
    for s, d in manifest["subjects"].items():
        z = np.load(REPO / f"data/camargo2021/processed/{s}.npz")
        ratio = retarget.leg_length_ratio(m, d["height_m"])
        for i in range(min(args.cap, d["strides"][args.speed])):
            ik, fp, fmk = z[f"{args.speed}_ik"][i], z[f"{args.speed}_fp"][i], z[f"{args.speed}_foot_markers"][i]
            cyc = retarget.Cycle(m, c.mapping, c.stand, ik, float(z[f"{args.speed}_duration_s"][i]), ratio, hip_in_pelvis_os=d["hip_in_pelvis_os_m"],
                                 trunk=args.trunk, pitch_mean="measured")
            q, qd, qdd = cyc.grid()
            for fi, foot in enumerate(gait.FEET):
                st = np.flatnonzero(fp[fi, :100, 6] >= 0.5)
                if len(st) < 5:
                    continue
                first, last = st[0], st[-1]
                for k in st:
                    dec = min(9, int(10 * (k - first) / max(1, last - first + 1)))
                    stance = tuple(f for j, f in enumerate(gait.FEET) if fp[j, k, 6] >= 0.5)
                    mf, mc = gaitloads.measured_to_model_foot(fp[:, k, :], fmk[k], dyn.foot_floor_segments(m, q[k]), c.mass / d["mass_kg"])
                    key = "single" if len(stance) == 1 else "double"
                    dist = dyn.polygon_outside_m(m, q[k], (foot,), mc[foot][:2]) if len(stance) == 1 else dyn.polygon_outside_m(m, q[k], (foot,), mc[foot][:2])
                    bins[key][dec].append(dist)
                    dd = mujoco_data(m, q[k])
                    heel, toe = dyn.foot_floor_segments(m, q[k])[foot]
                    corners, _ = dyn._foot_boxes(m, dd, mujoco_body(m, foot))
                    pitch[dec].append(float(corners[:, 2].max() - corners[:, 2].min()))
    print(f"=== {args.speed} m/s, trunk {args.trunk}: the measured CoP on each foot's own contact polygon, by decile of that foot's stance ===")
    print("  stance %   single support: outside % (median mm)    double support: outside % (median mm)    box height span mm")
    for dec in range(10):
        row = []
        for key in ("single", "double"):
            v = np.array(bins[key][dec])
            out = v[v > 1e-9]
            row.append(f"{100 * len(out) / len(v):5.1f} ({1000 * np.median(out) if len(out) else 0:3.0f}) n={len(v)}" if len(v) else "   -")
        print(f"  {10 * dec:3d}-{10 * dec + 10:3d}    {row[0]:>28s}        {row[1]:>28s}      {1000 * np.mean(pitch[dec]):5.0f}")


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
            cyc = retarget.Cycle(m, c.mapping, c.stand, ik, T, ratio, hip_in_pelvis_os=hip, trunk=args.trunk, pitch_mean=_pitch(args.pitch_mean))
            q, qd, qdd = cyc.grid()
            ref_lab = retarget.dataset_hip_mid_lab(ik, hip)
            fmk = z[f"{args.speed}_foot_markers"][i]
            for k in range(100):
                stance = tuple(f for j, f in enumerate(gait.FEET) if fp[j, k, 6] >= gaitloads.STANCE_FLAG)
                if not stance:
                    continue
                key = "single" if len(stance) == 1 else "double"
                qfrc = dyn.inverse_frame(m, q[k], qd[k], qdd[k])
                if args.cop_mode == "foot_frame":
                    mf, mc = gaitloads.measured_to_model_foot(fp[:, k, :], fmk[k], dyn.foot_floor_segments(m, q[k]), c.mass / d["mass_kg"])
                else:
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
    print(f"=== {args.speed} m/s, {args.cap} strides per subject, trunk {args.trunk}, measured CoP mapping {args.cop_mode}, pelvis pitch mean {args.pitch_mean} ===")
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


# ------------------------------------------------------------------------------ T9.1 the human-like trunk reference point

def joint_over_pelvis(gain, lag_deg) -> float:
    """|1 - r e^(-i phi)|: how much of the pelvis's first-harmonic amplitude the lumbosacral joint must supply when the trunk's harmonic is r e^(-i phi) times the pelvis's."""
    return float(abs(1.0 - gain * np.exp(-1j * np.deg2rad(lag_deg))))


def harmonic_report(args):
    """T9.1: the lumbosacral lateral and axial rows for a human-like trunk (first_harmonic at the T3c.2 medians and at the quartile corners)
    beside rigid and counter_rotate, per speed, over every subject-stride; and how much of the quartile spread is the subjects and how much is
    the IMU estimate."""
    import retarget
    manifest = json.loads((REPO / "data/camargo2021/manifest.json").read_text(encoding="utf-8"))
    print("joint rotation needed per unit of pelvis first-harmonic amplitude, |1 - r e^(-i phi)| (the brief's arithmetic: about 1.2 to 1.4 roll, 1.0 to 1.1 yaw):")
    for sp, d in retarget.FIRST_HARMONIC_DEFAULTS.items():
        for ax in ("roll", "yaw"):
            cs = [joint_over_pelvis(*x) for x in quartile_corners(d[ax])]
            print(f"  {sp} m/s {ax}: median ({d[ax]['median'][0]}, {d[ax]['median'][1]:.0f} deg) -> {joint_over_pelvis(*d[ax]['median']):.2f}; quartile corners {min(cs):.2f} to {max(cs):.2f}")
    tasks = gait_extract.lsj_tasks(args.speeds, args.cap, manifest)
    print(f"{len(tasks)} subject-stride x variant cycles, {len({(t['subject'], t['speed'], t['index']) for t in tasks})} subject-strides")
    rows = _pool(_lsj_task, tasks, args.workers)
    table = gait_extract.lsj_table(rows, args.speeds)
    for sp in args.speeds:
        for j in LSJ:
            print(f"=== {sp} m/s, {j}: median / 95th percentile / maximum across subject-strides ===")
            print(f"{'variant':36s} {'peak angle deg':>22s} {'peak torque N m':>24s} {'peak speed rad/s':>22s} {'power+ W (p95 / max)':>22s} {'regen W (p95 / max)':>22s}")
            by = table[sp][j]
            for v in VARIANTS:
                m = by[v]
                f3 = lambda k, nd: f"{m[k]['median']:.{nd}f} / {m[k]['p95']:.{nd}f} / {m[k]['max']:.{nd}f}"
                z0 = lambda x: f"{x + 0.0:.0f}" if round(x) != 0 else "0"  # no "-0"
                print(f"{v:36s} {f3('peak_angle_deg', 1):>22s} {f3('peak_torque_nm', 1):>24s} {f3('peak_speed_rad_s', 2):>22s} "
                      + f"{z0(m['peak_power_pos_w']['p95'])} / {z0(m['peak_power_pos_w']['max'])}".rjust(22) + f" {z0(m['peak_regen_w']['p95'])} / {z0(m['peak_regen_w']['max'])}".rjust(23))
            corners = [by[v] for v in VARIANTS if v.startswith("first_harmonic q")]
            print("  spread over the four quartile corners (min to max): " + "; ".join(
                f"{k.replace('peak_', '')} p95 {min(c[k]['p95'] for c in corners):.1f} to {max(c[k]['p95'] for c in corners):.1f}" for k in ("peak_angle_deg", "peak_torque_nm", "peak_speed_rad_s", "peak_power_pos_w", "peak_regen_w")))
    # how far the quartile spread is the subjects and how far the estimate
    from scipy.stats import spearmanr
    args2 = argparse.Namespace(speeds=args.speeds, min_quality=0.0, gyro_unit=1.0)
    imu = trunk_imu_report(args2)
    q = imu["quality"]
    ok = (q >= 0.6).all(axis=1)
    iqr = lambda v: float(np.subtract(*np.percentile(v, [75, 25])))
    print(f"=== subjects against estimate ({len(q)} subjects; {int(ok.sum())} with the IMU alignment correlation at least 0.6 on every axis; lateral (z) axis: median {np.median(q[:, 2]):.2f}, worst {q[:, 2].min():.2f}) ===")
    for sp in args.speeds:
        for ax in ("roll", "yaw"):
            for k, label in (("amplitude_ratio", "ratio"), ("phase_lag_deg", "lag deg")):
                v = np.array(imu["summary"][sp][ax][k])
                w = np.array(imu["within"][sp][ax][k])
                rho_x = spearmanr(v, q[:, 0])[0]
                rho_z = spearmanr(v, q[:, 2])[0]
                print(f"  {sp} {ax:4s} {label:8s}: IQR across all subjects {iqr(v):.2f}, across the {int(ok.sum())} well-aligned {iqr(v[ok]):.2f}; "
                      f"median within-subject stride IQR {np.median(w):.2f}; Spearman with alignment (forward {rho_x:+.2f}, lateral {rho_z:+.2f})")

# ------------------------------------------------------------------------------ T9.3 pitch flags

PITCH_FLAG_DEG = gait.PITCH_FLAG_DEG  # the brief's threshold (5 degrees) on |change of the IK pitch - change of the marker pitch| from static to walking; its home is gait.py


def marker_pelvic_tilt_deg(asis_r, asis_l, psis_r, psis_l):
    """Anterior-positive sagittal tilt of the line from the PSIS midpoint to the ASIS midpoint, from marker positions (N, 3) in a lab frame
    with y up. Forward is taken from the pelvis itself (the vertical cross the left-to-right ASIS line), not from a lab axis: the static trials
    are recorded facing another way than the treadmill trials. The line points forward and down for an anteriorly tilted pelvis. Only changes
    of it are compared, so the anatomical offset between this line and the pelvic frame the IK uses does not matter."""
    ar, al, pr, pl = (np.asarray(v, float) for v in (asis_r, asis_l, psis_r, psis_l))
    lat = ar - al
    lat[:, 1] = 0.0
    lat /= np.linalg.norm(lat, axis=1, keepdims=True)
    fwd = np.cross(np.array([0.0, 1.0, 0.0]), lat)
    v = 0.5 * (ar + al) - 0.5 * (pr + pl)
    return np.degrees(np.arctan2(-v[:, 1], np.sum(v * fwd, axis=1)))


def pitch_flag(delta_ik, delta_marker, threshold=PITCH_FLAG_DEG) -> bool:
    """True when the static-to-walking change of the IK pitch and of the marker pitch differ by more than the threshold (strictly)."""
    return bool(abs(delta_ik - delta_marker) > threshold)


def _tilt_from_table(t, mask=None):
    cols = lambda name: np.stack([t[f"{name}_{c}"] for c in "xyz"], axis=1)
    tilt = marker_pelvic_tilt_deg(cols("R_ASIS"), cols("L_ASIS"), cols("R_PSIS"), cols("L_PSIS"))
    tilt = tilt if mask is None else tilt[mask]
    return float(np.nanmean(tilt)) if np.isfinite(tilt).any() else float("nan"), int(np.isfinite(tilt).sum()), int(len(tilt))


def pitch_report(args):
    """T9.3: the IK pelvis pitch against the ASIS and PSIS markers for every subject: the static-to-walking change of each, their difference, and
    the flag (a difference above PITCH_FLAG_DEG at either speed). Subjects are kept either way; the list goes in the spec (`pitch_flag_subjects`)."""
    import re
    import zipfile
    sys.path.insert(0, str(REPO / "analysis"))
    import ingest_camargo as ic
    manifest = json.loads((REPO / "data/camargo2021/manifest.json").read_text(encoding="utf-8"))
    raw = ic.raw_dir()
    pl = ic.IK_CHANNELS.index("pelvis_list")
    rows, flagged = [], []
    print(f"IK pelvis pitch (anterior positive, minus pelvis_list) and ASIS/PSIS-marker pelvic tilt, degrees; a change is walking minus static; flag when the changes differ by more than {PITCH_FLAG_DEG:g} at either speed")
    print(f"{'subject':8s} {'static IK':>9s} {'static mk':>9s} | " + " | ".join(f"{sp} m/s: walk IK, walk mk, dIK, dmk, diff" for sp in args.speeds) + " | flag")
    for s, info in manifest["subjects"].items():
        zf = zipfile.ZipFile(raw / f"{s}.zip")
        names = zf.namelist()
        static = [_tilt_from_table(ic.read_table(zf.read(n)))[0] for n in sorted(x for x in names if re.search(r"/static/markers/.*\.mat$", x))]
        st_mk = float(np.mean(static))
        st_ik = float(info["static_pelvis_pitch_deg"])
        z = np.load(REPO / "data/camargo2021/processed" / f"{s}.npz")
        cache, cells, flag = {}, [], False
        for sp in args.speeds:
            ik_w, mk_w, bad = [], [], 0
            for i in range(len(z[f"{sp}_duration_s"])):
                trial = int(z[f"{sp}_trial"][i])
                if trial not in cache:
                    n = next(x for x in names if re.search(rf"/treadmill/markers/treadmill_{trial:02d}_\d+\.mat$", x))
                    cache[trial] = ic.read_table(zf.read(n))
                t = cache[trial]
                t0, T = float(z[f"{sp}_t0"][i]), float(z[f"{sp}_duration_s"][i])
                tilt, n_ok, n_all = _tilt_from_table(t, (t["Header"] >= t0) & (t["Header"] < t0 + T))
                if np.isfinite(tilt):
                    mk_w.append(tilt)
                else:
                    bad += 1
                ik_w.append(-float(np.mean(z[f"{sp}_ik"][i][:100, pl])))
            ik_m, mk_m = float(np.mean(ik_w)), float(np.mean(mk_w))
            d_ik, d_mk = ik_m - st_ik, mk_m - st_mk
            f = pitch_flag(d_ik, d_mk)
            flag = flag or f
            cells.append(f"{ik_m:7.1f} {mk_m:7.1f} {d_ik:6.1f} {d_mk:6.1f} {d_ik - d_mk:6.1f}" + (f" ({bad} strides without markers)" if bad else ""))
            rows.append((s, sp, d_ik, d_mk))
        if flag:
            flagged.append(s)
        print(f"{s:8s} {st_ik:9.1f} {st_mk:9.1f} | " + " | ".join(cells) + f" | {'FLAG' if flag else ''}")
    diffs = np.array([r[2] - r[3] for r in rows])
    print(f"flagged ({len(flagged)} of {len(manifest['subjects'])}): {', '.join(flagged) if flagged else 'none'}; difference of changes over subject-speeds: median {np.median(diffs):+.1f}, "
          f"range {diffs.min():+.1f} to {diffs.max():+.1f}, |difference| above {PITCH_FLAG_DEG:g} in {int(np.sum(np.abs(diffs) > PITCH_FLAG_DEG))} of {len(diffs)}")


# ------------------------------------------------------------------------------ T9.2 where B's backward offset comes from

TRUNKCOM_VARIANTS = ("freyja", "freyja + dataset trunk offset", "dataset masses", "dataset masses + dataset trunk offset")


def trunkcom_report(args):
    """T9.2a: the trunk group's centre of mass relative to the hip-centre midpoint in Freyja and in the dataset's OpenSim model, and B's single-support
    CoP error against the measured CoP with the group's centre of mass moved (in-memory copies, never saved) to the dataset's torso offset, with and
    without the dataset's other segment masses."""
    import datasetmass
    import gaitloads
    import trunkcom
    import zipfile
    dyn = gait.dynamics
    c = gait._ctx(str(gait.simrun.MODEL_FILE))
    m = c.model
    manifest = json.loads((REPO / "data/camargo2021/manifest.json").read_text(encoding="utf-8"))
    raw = ic_raw()
    off0 = trunkcom.trunk_offset(m)
    ids = [trunkcom._ids(m, [n])[0] for n in datasetmass.TRUNK_GROUP]
    print(f"Freyja: the trunk group (abdomen, thorax, head and neck, both arms) is {100 * m.body_mass[ids].sum() / m.body_mass.sum():.1f}% of the body; its centre of mass minus the "
          f"hip-centre midpoint at the neutral pose: x {1000 * off0[0]:+.1f} mm (anterior), y {1000 * off0[1]:+.1f}, z {1000 * off0[2]:+.1f} mm (up)")
    ds = {}
    for s in manifest["subjects"]:
        ds[s] = trunkcom.read_torso_offset(zipfile.ZipFile(raw / f"{s}.zip"), s)
    arr = np.array([ds[s]["offset_xy"] for s in ds])
    ratios = {s: gait.retarget.leg_length_ratio(m, manifest["subjects"][s]["height_m"]) for s in ds}
    scaled = np.array([ratios[s] * ds[s]["offset_xy"] for s in ds])
    frac = np.array([ds[s]["mass_fraction"] for s in ds])
    pr = lambda a: f"median {1000 * np.median(a):+.1f}, range {1000 * a.min():+.1f} to {1000 * a.max():+.1f}"
    print(f"dataset torso (trunk, head, arms; {100 * frac.mean():.1f}% of the body): centre of mass minus the hip-centre midpoint, pelvis frame, mm over {len(ds)} subjects: "
          f"x {pr(arr[:, 0])}; up {pr(arr[:, 1])}")
    print(f"  scaled by each subject's leg-length ratio ({min(ratios.values()):.2f} to {max(ratios.values()):.2f}), as the other segments are: x {pr(scaled[:, 0])}; up {pr(scaled[:, 1])}")
    print(f"  the shift applied: x {1000 * (np.median(scaled[:, 0]) - off0[0]):+.1f} mm, up {1000 * (np.median(scaled[:, 1]) - off0[2]):+.1f} mm (median over subjects)")
    for speed in args.speeds:
        args.speed = speed
        for trunk in ("rigid", "counter_rotate"):
            models = {}
            err = {v: [] for v in TRUNKCOM_VARIANTS}
            for fr in _single_support_frames(args, trunk):
                s = fr["subject"]
                if s not in models:
                    table = datasetmass.read_body_table(zipfile.ZipFile(raw / f"{s}.zip"), s)
                    dm = datasetmass.with_dataset_masses(m, table, fr["ratio"], fr["d"]["hip_in_pelvis_os_m"][:2])
                    target = ratios[s] * ds[s]["offset_xy"]
                    models[s] = {"freyja": m, "freyja + dataset trunk offset": trunkcom.shift_to(m, target)[0], "dataset masses": dm,
                                 "dataset masses + dataset trunk offset": trunkcom.shift_to(dm, target)[0]}
                mf, mc = gaitloads.measured_to_model_foot(fr["fp"], fr["fmk"], dyn.foot_floor_segments(m, fr["q"]), c.mass / fr["d"]["mass_kg"])
                for v in TRUNKCOM_VARIANTS:
                    mod = models[s][v]
                    full = dyn.cop_decomposition(mod, fr["q"], dyn.inverse_frame(mod, fr["q"], fr["qd"], fr["qdd"]))[0][:2]
                    err[v].append(full - mc[fr["foot"]][:2])
            print(f"=== {speed} m/s, trunk {trunk}, single support ({len(err['freyja'])} frames, first {args.cap} strides per subject): B CoP minus measured CoP, mm ===")
            for v in TRUNKCOM_VARIANTS:
                r = np.array(err[v])
                print(f"  {v:40s} fore-aft mean {1000 * r[:, 0].mean():+6.1f}  rms {1000 * np.sqrt((r[:, 0] ** 2).mean()):5.1f}   lateral mean {1000 * r[:, 1].mean():+6.1f}  rms {1000 * np.sqrt((r[:, 1] ** 2).mean()):5.1f}")


def standing_data_report(args):
    """T9.2b: does any subject's static trial carry force-plate data (a quiet-standing CoP)? Lists what each subject's static folder holds."""
    import re
    import zipfile
    import ingest_camargo as ic
    manifest = json.loads((REPO / "data/camargo2021/manifest.json").read_text(encoding="utf-8"))
    raw = ic.raw_dir()
    kinds, plate = {}, 0
    for s in manifest["subjects"]:
        names = zipfile.ZipFile(raw / f"{s}.zip").namelist()
        folders = sorted({m.group(1) for n in names if (m := re.search(r"/static/([^/]+)/", n))})
        kinds[s] = folders
        plate += any(f in ("fp", "forceplate", "force") for f in folders)
    sets = {tuple(v) for v in kinds.values()}
    print(f"static trial folders per subject ({len(kinds)} subjects): " + "; ".join(f"{list(k)} in {sum(1 for v in kinds.values() if tuple(v) == k)}" for k in sorted(sets)))
    print(f"subjects whose static trial has force-plate data: {plate}")


# ------------------------------------------------------------------------------ T9.4 toe evidence

def toe_report(args):
    """T9.4: what the dataset says about the metatarsophalangeal joint. The brief expects `mtp_angle` kinematics and an inverse-dynamics moment in
    late stance; this reports the largest magnitude of each over every subject-stride and foot, which is the whole finding if the joint is locked."""
    import re
    import zipfile
    import ingest_camargo as ic
    manifest = json.loads((REPO / "data/camargo2021/manifest.json").read_text(encoding="utf-8"))
    raw = ic.raw_dir()
    rows, n_all = {}, 0
    for s in manifest["subjects"]:
        zf = zipfile.ZipFile(raw / f"{s}.zip")
        names = zf.namelist()
        z = np.load(REPO / "data/camargo2021/processed" / f"{s}.npz")
        cache = {}
        amax = mmax = 0.0
        n = 0
        for sp in args.speeds:
            for i in range(len(z[f"{sp}_duration_s"])):
                trial = int(z[f"{sp}_trial"][i])
                if trial not in cache:
                    get = lambda sensor: ic.read_table(zf.read(next(x for x in names if re.search(rf"/treadmill/{sensor}/treadmill_{trial:02d}_\d+\.mat$", x))))
                    cache[trial] = (get("ik"), get("id"))
                ik, idt = cache[trial]
                t0, T = float(z[f"{sp}_t0"][i]), float(z[f"{sp}_duration_s"][i])
                for foot in ("r", "l"):
                    a = ic.phase_normalise(ik["Header"], ik[f"mtp_angle_{foot}"], t0, t0 + T, 101)
                    mo = ic.phase_normalise(idt["Header"], idt[f"mtp_angle_{foot}_moment"], t0, t0 + T, 101)
                    amax, mmax, n = max(amax, float(np.nanmax(np.abs(a)))), max(mmax, float(np.nanmax(np.abs(mo)))), n + 1
        rows[s] = (amax, mmax, n)
        n_all += n
    print(f"dataset metatarsophalangeal (toe) joint over every subject-stride and foot at {', '.join(args.speeds)} m/s ({n_all} stride-feet, {len(rows)} subjects):")
    print(f"  largest |mtp_angle| of any subject: {max(r[0] for r in rows.values()):.6g} deg (subjects with a non-zero angle: {sum(r[0] > 0 for r in rows.values())})")
    mm = np.array([r[1] for r in rows.values()])
    print(f"  largest |mtp moment| per subject, N m: median {np.median(mm):.2f}, range {mm.min():.2f} to {mm.max():.2f} (the same channel's hip, knee and ankle moments are tens to hundreds of N m)")


# ------------------------------------------------------------------------------ Stage 2b T2 and T4: A_filtered's peak torques and gain-or-shape

def stem_fit(model, data) -> dict:
    """Model moment against the dataset's, one array per stride and limb (both per kg of their own body). The slope and intercept are the
    OLS fit of the model on the data pooled over every frame; `gain` is the least-squares gain through the origin. RMS and peak difference
    use gait.agreement's conventions (RMS as a percentage of the stride's own dataset peak-to-peak range, then averaged over strides), the
    gain-removed ones with the model divided by the gain; `corr` is the mean of the per-stride correlations (the band's statistic)."""
    xs, ys = np.concatenate(data), np.concatenate(model)
    slope, icpt = ols(xs, ys)
    gain = float((xs * ys).sum() / (xs * xs).sum())
    raw = [gait.agreement(m, d) for m, d in zip(model, data)]
    fixed = [gait.agreement(np.asarray(m) / gain, d) for m, d in zip(model, data)]
    return {"slope": slope, "intercept": icpt, "gain": gain, "corr": float(np.mean([a["corr"] for a in raw])), "corr_pooled": float(np.corrcoef(xs, ys)[0, 1]),
            "rms_pct_ptp": float(np.mean([a["rms_pct_ptp"] for a in raw])), "rms_gain_removed_pct_ptp": float(np.mean([a["rms_pct_ptp"] for a in fixed])),
            "peak_diff": float(np.mean([a["peak_diff"] for a in raw])), "peak_diff_gain_removed": float(np.mean([a["peak_diff"] for a in fixed]))}


A_SAGITTAL = gait_extract.A_STEMS
A_OFF_BAND = ("hip_aa", "hip_ier")


def a_torque_report(args):
    for speed in args.speeds:
        S, mass, spec = gait_extract.a_filtered_strides(speed, args.workers)
        off = set(spec["offset_subjects"])
        print(f"\n=== {speed} m/s: {len(S)} subject-strides, {len({s['subject'] for s in S})} subjects; Freyja mass {mass:.2f} kg ===")
        print("T2  peak |torque| per stride, statistics over subject-strides: mean / median / p95 / max.")
        print("    A: A_filtered in N m, then in N m/kg of Freyja's mass; data: the dataset's peak moment in N m/kg of the subject; ratio: A's per-kg figure over the data's;")
        print("    scaled: the data's per-kg peak x Freyja's mass x leg-length ratio, N m (force by the mass ratio, lever arms by the leg-length ratio)")
        for label, keep in (("all subjects", lambda u: True), ("without offset subjects " + "/".join(sorted(off)), lambda u: u not in off)):
            print(f"  [{label}]")
            for stem in A_SAGITTAL:
                for side in ("right", "left"):
                    j = f"{stem}_{side}"
                    sel = [s for s in S if keep(s["subject"])]
                    a = np.array([np.abs(s["tau"][j]).max() for s in sel])
                    dk = np.array([np.abs(s["data"][j]).max() for s in sel])
                    pred = dk * mass * np.array([s["leg_ratio"] for s in sel])
                    sa, sak, sd, sp_ = peak_stats(a), peak_stats(a / mass), peak_stats(dk), peak_stats(pred)
                    k4 = ("mean", "median", "p95", "max")
                    fmt = lambda st, nd: " ".join(f"{st[k]:{5 + nd}.{nd}f}" for k in k4)
                    print(f"   {j:20s} A {fmt(sa, 1)} | {fmt(sak, 3)} | data {fmt(sd, 3)} | ratio " + " ".join(f"{sak[k] / sd[k]:5.2f}" for k in k4) + f" | scaled {fmt(sp_, 1)}")
        print("T4  A_filtered against the dataset, both limbs and every subject-stride pooled (per kg of each body); slope = A on data")
        print("    stem          slope  intercept   gain    corr  corr_pooled | rms % ptp  after gain | peak diff N m/kg  after gain | per-subject slope median [min, max]")
        subs = sorted({s["subject"] for s in S})
        for stem in A_SAGITTAL + A_OFF_BAND:
            model = [np.asarray(s["tau"][f"{stem}_{side}"]) / mass for s in S for side in ("right", "left")]
            data = [s["data"][f"{stem}_{side}"] for s in S for side in ("right", "left")]
            f = stem_fit(model, data)
            per = []
            for u in subs:
                ix = [2 * k + m for k, s in enumerate(S) if s["subject"] == u for m in (0, 1)]  # one entry per (stride, limb), in the order of `model`
                per.append(ols(np.concatenate([data[k] for k in ix]), np.concatenate([model[k] for k in ix]))[0])
            print(f"    {stem:12s} {f['slope']:6.3f} {f['intercept']:9.4f} {f['gain']:7.3f} {f['corr']:7.3f} {f['corr_pooled']:7.3f}   | {f['rms_pct_ptp']:6.1f} {f['rms_gain_removed_pct_ptp']:9.1f}"
                  f"   | {f['peak_diff']:8.3f} {f['peak_diff_gain_removed']:12.3f}   | {np.median(per):.3f} [{min(per):.3f}, {max(per):.3f}]")


# ------------------------------------------------------------------------------ Stage 2b T1: hip extension, raw against retargeted

def hip_extension_report(args):
    """T1: per-stride peak hip extension (and the knee flexion, ankle plantarflexion peaks) from the processed dataset kinematics (the
    phase-normalised inverse kinematics, before any retargeting) and from the retargeted joint angles of the cycles the gait record uses."""
    import re
    import zipfile
    import retarget
    spec = gait.load_spec("walk_treadmill")
    processed = REPO / spec["dataset"]["processed"]
    manifest = json.loads((REPO / spec["dataset"]["manifest"]).read_text(encoding="utf-8"))
    c = gait._ctx(gait.simrun.MODEL_FILE)
    nm = gait.ic.IK_CHANNELS
    adr = lambda j: c.hinge[j][0]
    q4 = lambda a: f"{np.median(a):5.1f} {np.percentile(a, 95):5.1f} {np.max(a):5.1f}"
    print(f"Freyja stand_static hip_fe {np.degrees(c.stand[adr('hip_fe_right')]):.2f} deg (right), knee {np.degrees(c.stand[adr('knee_right')]):.2f}, ankle {np.degrees(c.stand[adr('ankle_pdflex_right')]):.2f}; "
          f"hip range {np.degrees(c.model.jnt_range[c.model.joint('hip_fe_right').id]).round(1).tolist()} deg")
    raw_dir = None
    try:
        raw_dir = gait.ic.raw_dir()
        raw_dir = raw_dir if raw_dir.exists() else None
    except Exception:
        pass
    static = {}
    for s in manifest["subjects"]:
        if raw_dir is None:
            break
        zf = zipfile.ZipFile(raw_dir / f"{s}.zip")
        tabs = [gait.ic.read_table(zf.read(n)) for n in sorted(x for x in zf.namelist() if re.search(r"/static/ik/.*\.mat$", x))]
        static[s] = {k: float(np.mean([np.mean(t[k]) for t in tabs])) for k in ("hip_flexion_r", "hip_flexion_l", "knee_angle_r", "ankle_angle_r", "pelvis_list")}
    for speed in args.speeds:
        rows = []
        for s, info in manifest["subjects"].items():
            z = gait._subject_arrays(processed, s)
            ik, T = z[f"{speed}_ik"], z[f"{speed}_duration_s"]
            ratio = retarget.leg_length_ratio(c.model, info["height_m"])
            for i in range(len(ik)):
                cyc = retarget.Cycle(c.model, c.mapping, c.stand, ik[i], float(T[i]), ratio, cutoff_hz=float(spec["smoothing"]["cutoff_hz"]), root_rule=spec["root_rule"],
                                     hip_in_pelvis_os=info.get("hip_in_pelvis_os_m"), root_ref=spec["root_reference"], pitch_mean=spec["pitch_mean"], trunk="rigid")
                q = cyc.grid()[0][:gait.N_FRAMES]
                ch = lambda n: ik[i][:, nm.index(n)]
                deg = lambda j: np.degrees(q[:, adr(j)])
                row = {"subject": s, "pitch": float(ch("pelvis_list").mean())}
                row["hip_raw"] = peak_extension_deg(ch("hip_flexion_r"), ch("hip_flexion_l"))
                row["hip_rt"] = peak_extension_deg(deg("hip_fe_right"), deg("hip_fe_left"))
                row["hip_flex_raw"] = float(max(ch("hip_flexion_r").max(), ch("hip_flexion_l").max()))
                row["hip_flex_rt"] = float(max(deg("hip_fe_right").max(), deg("hip_fe_left").max()))
                row["knee_raw"] = float(-min(ch("knee_angle_r").min(), ch("knee_angle_l").min()))
                row["knee_rt"] = float(max(deg("knee_right").max(), deg("knee_left").max()))
                row["ankle_raw"] = float(-min(ch("ankle_angle_r").min(), ch("ankle_angle_l").min()))
                row["ankle_rt"] = float(-min(deg("ankle_pdflex_right").min(), deg("ankle_pdflex_left").min()))
                row["thigh_world"] = peak_extension_deg(*(thigh_world_deg(ch(f"hip_flexion_{x}"), ch("pelvis_list")) for x in "rl"))
                row["hip_mean"] = float(ch("hip_flexion_r").mean())
                rows.append(row)
        print(f"\n=== {speed} m/s, {len(rows)} subject-strides (extension, flexion, plantarflexion positive; degrees; median / p95 / max; per stride the larger of the two limbs) ===")
        for key, label in (("hip", "hip extension"), ("hip_flex", "hip flexion"), ("knee", "knee flexion"), ("ankle", "ankle plantarflexion")):
            raw, rt = np.array([r[key + "_raw"] for r in rows]), np.array([r[key + "_rt"] for r in rows])
            d = rt - raw
            print(f" {label:21s} dataset IK {q4(raw)} | retargeted {q4(rt)} | retargeted - dataset: mean {d.mean():+.2f} sd {d.std():.2f} min {d.min():+.2f} max {d.max():+.2f}")
        raw = np.array([r["hip_raw"] for r in rows])
        print(f" hip extension beyond the model's {-np.degrees(c.model.jnt_range[c.model.joint('hip_fe_right').id][0]):.1f} deg stop: dataset IK {np.mean(raw > 18.1):.2f} of strides")
        subs = sorted({r["subject"] for r in rows})
        print(" per subject, hip extension: median dataset / median retargeted / mean (sd) of the stride difference; mean pelvis_list; mean hip angle; static hip / pelvis_list")
        for u in subs:
            rr = [r for r in rows if r["subject"] == u]
            a, b = np.array([r["hip_raw"] for r in rr]), np.array([r["hip_rt"] for r in rr])
            st = static.get(u)
            print(f"  {u}  {np.median(a):5.1f} {np.median(b):5.1f} {np.mean(b - a):+5.2f} ({np.std(b - a):.2f})  list {np.mean([r['pitch'] for r in rr]):5.1f}  hip {np.mean([r['hip_mean'] for r in rr]):5.1f}"
                  + (f"  static hip R {st['hip_flexion_r']:5.1f} L {st['hip_flexion_l']:5.1f} list {st['pelvis_list']:5.1f}" if st else "  static: raw dir unavailable"))
        pl = np.array([r["pitch"] for r in rows])
        b, a = np.polyfit(pl, raw, 1)
        tw = np.array([r["thigh_world"] for r in rows])
        print(f" hip extension on the stride's mean pelvis_list: slope {b:.2f} intercept {a:.1f} deg, r {np.corrcoef(pl, raw)[0, 1]:.2f}; mean pelvis_list median {np.median(pl):.1f} deg (range {pl.min():.1f} to {pl.max():.1f}); "
              f"strides with it above 5 deg: {np.mean(pl > 5):.2f}")
        print(f" thigh extension from the vertical (hip angle + pelvis_list, planar): {q4(tw)}")
        print(f" hip extension, strides with mean pelvis_list below 5 deg: {q4(raw[pl < 5])}; at or above 5 deg: {q4(raw[pl >= 5])}")


def ankle_gain_command(args):
    import ankle_gain
    ankle_gain.ankle_gain_report(args)


def foot_pitch_command(args):
    import foot_pitch
    foot_pitch.report(args)


def main(argv=None):
    ap = argparse.ArgumentParser(prog="gait_diag")
    sub = ap.add_subparsers(dest="cmd", required=True)
    a = sub.add_parser("a-agreement")
    a.add_argument("--root-reference", default="hip_midpoint", choices=["hip_midpoint", "pelvis_origin"])
    a.add_argument("--cop-mode", default="hip_reference", choices=["hip_reference", "foot_frame"])
    a.add_argument("--pitch-mean", default="measured")
    a.add_argument("--cap", type=int, default=3)
    a.add_argument("--speed", default="1.4")
    a.add_argument("--workers", type=int, default=5)
    f = sub.add_parser("force")
    f.add_argument("--cap", type=int, default=5)
    f.add_argument("--speed", default="1.4")
    f.add_argument("--trunk", default="rigid", choices=["rigid", "counter_rotate"])
    cp = sub.add_parser("cop")
    cp.add_argument("--cap", type=int, default=4)
    cp.add_argument("--pitch-mean", default="measured")
    cp.add_argument("--cop-mode", default="foot_frame", choices=["hip_reference", "foot_frame"])
    cp.add_argument("--speed", default="1.4")
    cp.add_argument("--trunk", default="rigid", choices=["rigid", "counter_rotate"])
    fo = sub.add_parser("foot")
    fo.add_argument("--cap", type=int, default=4)
    fo.add_argument("--speed", default="1.4")
    fo.add_argument("--pitch-mean", default="measured")
    fo.add_argument("--trunk", default="rigid", choices=["rigid", "counter_rotate"])
    tr = sub.add_parser("trunk")
    tr.add_argument("--cap", type=int, default=4)
    tr.add_argument("--speeds", nargs="+", default=["1.4", "1.6"])
    tr.add_argument("--workers", type=int, default=5)
    ti = sub.add_parser("trunk-imu")
    ti.add_argument("--speeds", nargs="+", default=["1.4", "1.6"])
    ti.add_argument("--min-quality", type=float, default=0.0, help="drop subjects whose accelerometer alignment correlation is below this on any axis")
    ti.add_argument("--gyro-unit", type=float, default=1.0, help="multiplier from the file's gyroscope unit to rad/s")
    tc = sub.add_parser("trunkcom")
    tc.add_argument("--cap", type=int, default=4)
    tc.add_argument("--speeds", nargs="+", default=["1.4", "1.6"])
    sub.add_parser("standing")
    te = sub.add_parser("toe")
    te.add_argument("--speeds", nargs="+", default=["1.4", "1.6"])
    pt = sub.add_parser("pitch")
    pt.add_argument("--speeds", nargs="+", default=["1.4", "1.6"])
    hr = sub.add_parser("harmonic")
    hr.add_argument("--speeds", nargs="+", default=["1.4", "1.6"])
    hr.add_argument("--cap", type=int, default=0, help="strides per subject (0 = all)")
    hr.add_argument("--workers", type=int, default=5)
    ds = sub.add_parser("double")
    ds.add_argument("--cap", type=int, default=4)
    ds.add_argument("--speeds", nargs="+", default=["1.4", "1.6"])
    ds.add_argument("--workers", type=int, default=5)
    pgn = sub.add_parser("polygon")
    pgn.add_argument("--cap", type=int, default=4)
    pgn.add_argument("--speeds", nargs="+", default=["1.4", "1.6"])
    pgn.add_argument("--workers", type=int, default=5)
    for name in ("swing", "masses", "placement"):
        sp_ = sub.add_parser(name)
        sp_.add_argument("--cap", type=int, default=4)
        sp_.add_argument("--speed", default="1.4")
    po = sub.add_parser("pushoff")
    po.add_argument("--cap", type=int, default=4)
    po.add_argument("--speed", default="1.4")
    po.add_argument("--trunk", default="counter_rotate", choices=["rigid", "counter_rotate"])
    la = sub.add_parser("lateral")
    la.add_argument("--cap", type=int, default=3)
    la.add_argument("--subjects", type=int, default=6)
    la.add_argument("--speed", default="1.4")
    la.add_argument("--trunk", default="rigid", choices=["rigid", "counter_rotate"])
    at = sub.add_parser("a-torque")
    at.add_argument("--speeds", nargs="+", default=["1.4", "1.6"])
    at.add_argument("--workers", type=int, default=5)
    he = sub.add_parser("hipext")
    he.add_argument("--speeds", nargs="+", default=["1.4", "1.6"])
    ag_ = sub.add_parser("ankle-gain")  # Stage 2b T6: report only; needs data/camargo2021/processed/ankle_lat (python sim/scripts/ankle_gain.py extract <subject>)
    ag_.add_argument("--speeds", nargs="+", default=["1.4", "1.6"])
    ag_.add_argument("--workers", type=int, default=5)
    ag_.add_argument("--subjects", nargs="+", default=None)
    ag_.add_argument("--cap", type=int, default=None)
    fpc = sub.add_parser("foot-pitch")  # Stage 2d T2: report only; reads the static trial's markers from the raw archives
    fpc.add_argument("--speeds", nargs="+", default=["1.4", "1.6"])
    fpc.add_argument("--workers", type=int, default=5)
    fpc.add_argument("--cap", type=int, default=0, help="strides per subject for the pitch table (0 = all)")
    fpc.add_argument("--polygon-cap", type=int, default=None, help="also the polygon by decile, this many strides per subject (0 = all; memo10 used 4)")
    fpc.add_argument("--trunk", default="counter_rotate", choices=["rigid", "counter_rotate"])
    fpc.add_argument("--pitch-offset-deg", type=float, default=0.0, help="the existing pelvis pitch sensitivity knob; 0 = the spec's default")
    fpc.add_argument("--ankle-offset-deg", type=float, default=0.0, help="counterfactual: add this to both ankle angles of the input (what a constant mapping offset would do)")
    args = ap.parse_args(argv)
    {"foot-pitch": foot_pitch_command, "ankle-gain": ankle_gain_command, "hipext": hip_extension_report,"a-torque": a_torque_report,"a-agreement": a_agreement, "force": force_report, "lateral": lateral, "cop": cop_steps, "foot": foot_report, "trunk": trunk_report, "trunk-imu": trunk_imu_report, "harmonic": harmonic_report, "pitch": pitch_report, "trunkcom": trunkcom_report, "standing": standing_data_report, "toe": toe_report, "double": double_report, "polygon": polygon_report, "swing": swing_report, "masses": masses_report, "placement": placement_report, "pushoff": pushoff_report}[args.cmd](args)


if __name__ == "__main__":
    main()
