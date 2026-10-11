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
    for s in manifest["subjects"]:
        allrows = [r for sp in args.speeds for r in prep[s][sp]]
        R, q = trunkimu.align_sensor_to_pelvis(np.concatenate([r["acc"] for r in allrows]), np.concatenate([r["f_p"] for r in allrows]))
        quality.append(q)
        if q.min() < args.min_quality:
            continue  # the IMU could not be aligned to the pelvis frame well enough for this subject
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
                res = gait.build_results(rows, c, {**spec, "speeds_mps": [float(speed)], "pelvis_pitch_offset_deg": off})[speed]["feasibility"]
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
    la = sub.add_parser("lateral")
    la.add_argument("--cap", type=int, default=3)
    la.add_argument("--subjects", type=int, default=6)
    la.add_argument("--speed", default="1.4")
    la.add_argument("--trunk", default="rigid", choices=["rigid", "counter_rotate"])
    args = ap.parse_args(argv)
    {"a-agreement": a_agreement, "force": force_report, "lateral": lateral, "cop": cop_steps, "foot": foot_report, "trunk": trunk_report, "trunk-imu": trunk_imu_report, "double": double_report, "polygon": polygon_report, "swing": swing_report, "masses": masses_report, "placement": placement_report}[args.cmd](args)


if __name__ == "__main__":
    main()
