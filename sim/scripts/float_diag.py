"""
Stage 2g follow-up (memo 26, report only): why the retargeted stance foot floats above the floor, and what it does to method A.

    python sim/scripts/float_diag.py cause        [--workers N] [--json OUT]   # T3: the root rule's lowest point, float by stance decile, counterfactual models
    python sim/scripts/float_diag.py a-sensitivity [--workers N]               # T2: method A with the measured force applied at the sole instead of the floor plane
    python sim/scripts/float_diag.py residual     [--workers N]                # T4: A's root residual in single support against B's error

1.4 m/s, rigid trunk, every subject-stride, the spec's frame offset unless a variant says otherwise. Nothing here changes the retargeting, the root rule, the sheet,
a tolerance or a tracked output; the counterfactual models are built in memory from sim/models/freyja.xml (or from the Stage 2 model in git) and written to a
temporary directory.

The root rule (retarget.Cycle, root_rule `pelvis_dataset`): the pelvis height is the dataset's hip-midpoint height scaled to the model, shifted by ONE constant per stride so
that the lowest foot-box corner of EITHER foot at ANY of the 100 phase points touches z = 0 (retarget.py, `lows.min()`). A stance foot floats whenever its own lowest
corner is above the stride's overall lowest one, and that one can belong to the swing foot.
"""
from __future__ import annotations

import argparse
import json
import subprocess
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
import old_box_diag  # noqa: E402
import retarget  # noqa: E402

REPO = gait.REPO
OLD_MODEL_COMMIT = "d9b5a48"  # the tracked model before the Stage 2g snapshot change
N_DECILES = 10
SPEED = "1.4"
CORNER_NAMES = {("foot", -1): "heel (foot box, rear)", ("foot", 1): "foot box front", ("toe", -1): "toe base", ("toe", 1): "toe tip"}


# ------------------------------------------------------------------------------ pure helpers

def stance_deciles(mask) -> np.ndarray:
    """For a cyclic boolean stance mask (one foot, N frames): the decile (0 to 9) of every stance frame within its own contiguous stance interval, -1 elsewhere. An interval
    that wraps from the last frame to the first is one interval."""
    m = np.asarray(mask, bool)
    n = len(m)
    out = np.full(n, -1, dtype=int)
    if not m.any():
        return out
    if m.all():
        return np.minimum((np.arange(n) * N_DECILES) // n, N_DECILES - 1)
    start0 = next(k for k in range(n) if m[k] and not m[k - 1])
    k, seen = start0, 0
    while seen < n:
        if m[k % n]:
            length = 0
            while m[(k + length) % n] and seen + length < n:
                length += 1
            for i in range(length):
                out[(k + i) % n] = min(i * N_DECILES // length, N_DECILES - 1)
            k += length
            seen += length
        else:
            k += 1
            seen += 1
    return out


def lowest_corner(model, data, foot=None):
    """(z, which, sx) of the lowest foot-box corner for the pose in `data` (kinematics must be current): `which` is "foot" or "toe" (the body the box belongs to), sx the
    corner's side along the box's long axis (-1 rear, +1 front). Same set of corners as retarget.Cycle._corner_z."""
    best = (np.inf, None, 0)
    for g in range(model.ngeom):
        bname = mujoco.mj_id2name(model, mujoco.mjtObj.mjOBJ_BODY, int(model.geom_bodyid[g]))
        owner = retarget.FOOT_OF.get(bname)
        if model.geom_type[g] != mujoco.mjtGeom.mjGEOM_BOX or owner not in retarget.FOOT_BODIES or (foot is not None and owner != retarget.FOOT_BODIES[foot]):
            continue
        r, c, s = data.geom_xmat[g].reshape(3, 3), data.geom_xpos[g], model.geom_size[g]
        for sx in (-1, 1):
            for sy in (-1, 1):
                for sz in (-1, 1):
                    z = (c + r @ (np.array([sx, sy, sz]) * s))[2]
                    if z < best[0]:
                        best = (float(z), "toe" if bname.startswith("toe") else "foot", sx)
    return best


def stride_floats(model, q, stance_mask) -> dict:
    """The float of one stride from its (N, nq) frames and the (2, N) stance flags: per frame and foot the lowest-corner height, the stance maximum and mean, the sum and count of
    the stance float by stance decile, and the stride's overall lowest corner (the point that sets the root height): frame, foot, which box and side, and whether that foot was in
    stance at that frame."""
    d = mujoco.MjData(model)
    mask = np.asarray(stance_mask, bool)
    n = q.shape[0]
    low = np.zeros((n, 2))
    which = [[None, None] for _ in range(n)]
    for k in range(n):
        d.qpos[:] = q[k]
        mujoco.mj_kinematics(model, d)
        for f in (0, 1):
            z, w, sx = lowest_corner(model, d, f)
            low[k, f], which[k][f] = z, (w, sx)
    k0, f0 = np.unravel_index(int(np.argmin(low)), low.shape)
    flt = np.where(mask.T, low, np.nan)  # (n, 2): the float of a stance foot at that frame
    dec_sum, dec_n = np.zeros(N_DECILES), np.zeros(N_DECILES)
    for f in (0, 1):
        dec = stance_deciles(mask[f])
        for i in range(N_DECILES):
            sel = dec == i
            dec_sum[i] += float(np.maximum(low[sel, f], 0.0).sum())
            dec_n[i] += float(sel.sum())
    stance_vals = np.maximum(flt[~np.isnan(flt)], 0.0)
    return {"float_max_m": float(stance_vals.max()), "float_mean_m": float(stance_vals.mean()), "decile_sum_m": dec_sum.tolist(), "decile_n": dec_n.tolist(),
            "min_frame": int(k0), "min_foot": int(f0), "min_box": which[k0][f0][0], "min_side": int(which[k0][f0][1]), "min_in_stance": bool(mask[f0, k0]),
            "min_z_m": float(low[k0, f0])}


def summarise_strides(rows: list) -> dict:
    fm = np.array([r["float_max_m"] for r in rows])
    dsum, dn = np.sum([r["decile_sum_m"] for r in rows], axis=0), np.sum([r["decile_n"] for r in rows], axis=0)
    kinds = {}
    for r in rows:
        key = ("stance" if r["min_in_stance"] else "swing", CORNER_NAMES[(r["min_box"], r["min_side"])])
        kinds[key] = kinds.get(key, 0) + 1
    return {"strides": len(rows), "float_max_mean_m": float(fm.mean()), "float_max_p95_m": float(np.percentile(fm, 95)), "float_max_max_m": float(fm.max()),
            "float_mean_m": float(np.mean([r["float_mean_m"] for r in rows])),
            "by_decile_mean_m": (dsum / np.maximum(dn, 1)).tolist(), "root_point": {f"{a}: {b}": c for (a, b), c in sorted(kinds.items(), key=lambda kv: -kv[1])}}


# ------------------------------------------------------------------------------ models

def old_model_xml() -> str:
    return subprocess.check_output(["git", "show", f"{OLD_MODEL_COMMIT}:sim/models/freyja.xml"], cwd=REPO).decode("utf-8").replace("\r\n", "\n")


def with_ankle_height(xml: str, ankle_m: float, toe_height_m: float) -> str:
    """The model text with the foot box and the toe hinge moved so the ankle is `ankle_m` above the sole (nothing else changes: lengths, masses, joints)."""
    import re
    out, n = re.subn(r'(<body name="foot_(?:right|left)".*?<geom type="box" pos="[^ ]+ 0 )[^"]+(" size="[^ ]+ [^ ]+ )[^"]+(")',
                     lambda m: f"{m.group(1)}{-ankle_m / 2:.12g}{m.group(2)}{ankle_m / 2:.12g}{m.group(3)}", xml, flags=re.S)
    if n != 2:
        raise ValueError(f"expected two foot boxes, found {n}")
    out, n = re.subn(r'(<body name="toe_(?:right|left)" pos="[^ ]+ 0 )[^"]+(")', lambda m: f"{m.group(1)}{-(ankle_m - toe_height_m / 2):.12g}{m.group(2)}", out)
    if n != 2:
        raise ValueError(f"expected two toe bodies, found {n}")
    return out


def without_toe_boxes(xml: str) -> str:
    import re
    out, n = re.subn(r'(<body name="toe_(?:right|left)".*?)\s*<geom type="box"[^>]*/>', r"\1", xml, flags=re.S)
    if n != 2:
        raise ValueError(f"expected two toe boxes, found {n}")
    return out


def with_rear(xml: str, heel_m: float, hinge_m: float) -> str:
    """The foot box (heel to toe hinge) with a different heel offset behind the ankle."""
    import re
    out, n = re.subn(r'(<body name="foot_(?:right|left)".*?<geom type="box" pos=")[^ ]+( 0 [^"]+" size=")[^ ]+( )',
                     lambda m: f"{m.group(1)}{(hinge_m - heel_m) / 2:.12g}{m.group(2)}{(hinge_m + heel_m) / 2:.12g}{m.group(3)}", xml, flags=re.S)
    if n != 2:
        raise ValueError(f"expected two foot boxes, found {n}")
    return out


def variants(workdir: Path) -> dict:
    """name -> (model path, pelvis_frame_offset). The new model is sim/models/freyja.xml; the others are edits of its text, or the Stage 2 model from git."""
    new_xml = (REPO / "sim" / "models" / "freyja.xml").read_text(encoding="utf-8")
    snap = {}
    import csv
    for r in csv.DictReader((REPO / "params" / "snapshot.csv").open(encoding="utf-8")):
        snap[r["placeholder"]] = float(r["value"])
    heel, hinge, toe_h = snap["foot_heel_behind_ankle"], snap["toe_hinge_ahead_ankle"], snap["toe_height"]
    texts = {
        "stage2 model, offset none": (old_model_xml(), "none"),
        "stage2 model, offset measured": (old_model_xml(), "measured"),
        "new model, offset none": (new_xml, "none"),
        "new model": (new_xml, "measured"),
        "new, ankle height 62.7 mm": (with_ankle_height(new_xml, 0.0627, toe_h), "measured"),
        "new, toe box removed": (without_toe_boxes(new_xml), "measured"),
        "new, heel 41.25 mm (box and toe as new)": (with_rear(new_xml, 0.04125, hinge), "measured"),
        "new, Stage 2 box (41.25 to 165 mm, no toe box)": (old_box_diag.old_box_xml(new_xml), "measured"),
    }
    out = {}
    for i, (name, (text, mode)) in enumerate(texts.items()):
        if name == "new model":
            out[name] = (str(REPO / "sim" / "models" / "freyja.xml"), mode)
            continue
        p = workdir / f"variant{i}.xml"
        p.write_text(text, encoding="utf-8", newline="\n")
        out[name] = (str(p), mode)
    return out


# ------------------------------------------------------------------------------ one stride

def float_task(task: dict) -> dict:
    c = gait._ctx(task["model_path"])
    z = gait._subject_arrays(task["processed"], task["subject"])
    sp, i = task["speed"], task["index"]
    ik, fp = z[f"{sp}_ik"][i], z[f"{sp}_fp"][i]
    T, sub = float(z[f"{sp}_duration_s"][i]), task["subject_info"]
    hip = sub.get("hip_in_pelvis_os_m")
    ref = task["root_reference"] if hip is not None else "pelvis_origin"
    stance = (fp[:, :, 6] >= gaitloads.STANCE_FLAG)[:, :gait.N_FRAMES]
    cyc = retarget.Cycle(c.model, c.mapping, c.stand, ik, T, retarget.leg_length_ratio(c.model, sub["height_m"]), cutoff_hz=task["cutoff_hz"],
                         pitch_offset_deg=task["pitch_offset_deg"], root_rule=task["root_rule"], hip_in_pelvis_os=hip, root_ref=ref, pitch_mean=task["pitch_mean"],
                         trunk=task["trunk"], pelvis_frame_offset_deg=gait.frame_offset_deg(task["pelvis_frame_offset"], sub), toe="welded", stance=fp[:, :, 6] >= gaitloads.STANCE_FLAG)
    q = cyc.grid()[0][:gait.N_FRAMES]
    return stride_floats(c.model, q, stance)


def tasks_for(model_path: str, mode: str, speed: str = SPEED) -> list:
    spec = dict(gait.load_spec("walk_treadmill"), pelvis_frame_offset=mode, speeds_mps=[float(speed)])
    manifest = json.loads((REPO / spec["dataset"]["manifest"]).read_text(encoding="utf-8"))
    processed = REPO / spec["dataset"]["processed"]
    return gait._tasks(spec, manifest, model_path, processed, ["A_filtered"], float(spec["smoothing"]["cutoff_hz"]), float(spec["pelvis_pitch_offset_deg"]), None, False, False, False, trunk="rigid")


def cause(args):
    with tempfile.TemporaryDirectory() as tmp, ProcessPoolExecutor(max_workers=args.workers) as ex:
        results = {}
        for name, (path, mode) in variants(Path(tmp)).items():
            rows = list(ex.map(float_task, tasks_for(path, mode), chunksize=4))
            results[name] = summarise_strides(rows)
            s = results[name]
            print(f"== {name}: {s['strides']} strides; stance float (per-stride maximum) mean / p95 / max {1000 * s['float_max_mean_m']:.1f} / {1000 * s['float_max_p95_m']:.1f} / "
                  f"{1000 * s['float_max_max_m']:.1f} mm; mean over all stance frames {1000 * s['float_mean_m']:.1f} mm")
            print("   by stance decile, mean float mm: " + " ".join(f"{1000 * x:5.1f}" for x in s["by_decile_mean_m"]))
            print("   lowest point of the stride (sets the root height): " + "; ".join(f"{k} {v}" for k, v in s["root_point"].items()))
    if args.json:
        Path(args.json).write_text(json.dumps(results, indent=1, sort_keys=True), encoding="utf-8", newline="\n")


# ------------------------------------------------------------------------------ T2 and T4: method A

def a_sensitivity(args):
    spec = dict(gait.load_spec("walk_treadmill"), speeds_mps=[float(SPEED)])
    manifest = json.loads((REPO / spec["dataset"]["manifest"]).read_text(encoding="utf-8"))
    processed = REPO / spec["dataset"]["processed"]
    c = gait._ctx(str(gait.simrun.MODEL_FILE))
    out = {}
    for lift in ("floor", "sole"):
        tasks = [dict(t, cop_lift=lift) for t in gait._tasks(spec, manifest, gait.simrun.MODEL_FILE, processed, ["A_filtered"], float(spec["smoothing"]["cutoff_hz"]),
                                                            float(spec["pelvis_pitch_offset_deg"]), None, False, True, False, trunk="rigid")]
        rows = gait._run_tasks(tasks, args.workers)
        out[lift] = gait.build_results(rows, c, spec)[SPEED]["rigid"]
    print("A_filtered, 1.4 m/s, rigid trunk: measured force applied at the floor plane (record) and at the sole of the stance foot")
    print("joint                 p95 floor -> sole        max floor -> sole")
    for j in c.joints:
        if j.startswith(("hip_fe", "knee", "ankle_pdflex")):
            a = out["floor"]["joints"][j]["A_filtered"]["peak_torque_nm"]["all"]
            b = out["sole"]["joints"][j]["A_filtered"]["peak_torque_nm"]["all"]
            print(f"  {j:19s} {a['p95']:7.1f} -> {b['p95']:7.1f} ({100 * (b['p95'] / a['p95'] - 1):+5.1f}%)   {a['max']:7.1f} -> {b['max']:7.1f} ({100 * (b['max'] / a['max'] - 1):+5.1f}%)")
    for lift in ("floor", "sole"):
        for stem in ("hip_fe", "knee", "ankle_pdflex"):
            x = out[lift]["band"]["A_filtered"]["all"]["joints"][stem]
            print(f"  band {lift:5s} {stem:13s} corr {x['corr']:.3f}  rms {x['rms_pct_ptp']:.2f}% of ptp  meets {x['meets']}")
        print(f"  band {lift:5s} all meets {out[lift]['band']['A_filtered']['all']['meets']}")


def residual(args):
    spec = dict(gait.load_spec("walk_treadmill"), speeds_mps=[float(SPEED)])
    manifest = json.loads((REPO / spec["dataset"]["manifest"]).read_text(encoding="utf-8"))
    processed = REPO / spec["dataset"]["processed"]
    tasks = gait._tasks(spec, manifest, gait.simrun.MODEL_FILE, processed, ["A_filtered", "B"], float(spec["smoothing"]["cutoff_hz"]), float(spec["pelvis_pitch_offset_deg"]), None,
                        False, False, False, trunk="rigid")
    with ProcessPoolExecutor(max_workers=args.workers) as ex:
        rows = list(ex.map(residual_stride, tasks, chunksize=4))
    print(summarise_residual(rows))


def residual_stride(task: dict) -> dict:
    """Single-support frames of one stride: the measured (filtered) force of the stance foot, method A's root residual (force, and moment about the root origin, world frame), method
    B's total ground force and B's CoP minus the measured CoP (the unfiltered measured CoP, as gait.run_stride's `single_support_cop_error` takes it)."""
    c = gait._ctx(task["model_path"])
    model = c.model
    z = gait._subject_arrays(task["processed"], task["subject"])
    sp, i = task["speed"], task["index"]
    ik, fp = z[f"{sp}_ik"][i], z[f"{sp}_fp"][i]
    T, sub = float(z[f"{sp}_duration_s"][i]), task["subject_info"]
    hip = sub.get("hip_in_pelvis_os_m")
    ref = task["root_reference"] if hip is not None else "pelvis_origin"
    ratio, mass_ratio = retarget.leg_length_ratio(model, sub["height_m"]), c.mass / sub["mass_kg"]

    def cycle(toe):
        return retarget.Cycle(model, c.mapping, c.stand, ik, T, ratio, cutoff_hz=task["cutoff_hz"], pitch_offset_deg=task["pitch_offset_deg"], root_rule=task["root_rule"],
                              hip_in_pelvis_os=hip, root_ref=ref, pitch_mean=task["pitch_mean"], trunk=task["trunk"],
                              pelvis_frame_offset_deg=gait.frame_offset_deg(task["pelvis_frame_offset"], sub), toe=toe, stance=fp[:, :, 6] >= gaitloads.STANCE_FLAG)
    qw, qdw, qddw = cycle("welded").grid()
    q, qd, qdd = cycle("rolling").grid()
    fpf = gaitloads.filter_measured(fp, T, task["cutoff_hz"])
    ref_lab = retarget.dataset_hip_mid_lab(ik, hip) if ref == "hip_midpoint" else ik[:, 3:6]
    out = {k: [] for k in ("f_meas", "res_force", "res_moment", "b_force", "b_cop_err")}
    for k in range(gait.N_FRAMES):
        stance = tuple(f for j, f in enumerate(gait.FEET) if fp[j, k, 6] >= gaitloads.STANCE_FLAG)
        if len(stance) != 1:
            continue
        ref_xy = retarget.model_hip_mid(model, q[k])[:2] if ref == "hip_midpoint" else q[k, :2]
        qfrc_a = dynamics.inverse_frame(model, qw[k], qdw[k], qddw[k])
        forces, cops = gaitloads.measured_to_model(fpf[:, k, :], ref_lab[k], ref_xy, mass_ratio, ratio, task["cop_scale"])
        _, res, _ = dynamics.solve_given(model, qw[k], qfrc_a, forces, cops)
        qfrc_b = dynamics.inverse_frame(model, q[k], qd[k], qdd[k])
        rb = dynamics.solve_frame(model, q[k], qd[k], qdd[k], stance=stance, sweep=False, qfrc=qfrc_b)
        _, mcops = gaitloads.measured_to_model(fp[:, k, :], ref_lab[k], ref_xy, mass_ratio, ratio, task["cop_scale"])
        out["f_meas"].append(np.asarray(forces[stance[0]], float))
        out["res_force"].append(res[:3])
        out["res_moment"].append(res[3:])
        out["b_force"].append(np.asarray(qfrc_b[:3], float))
        out["b_cop_err"].append((np.asarray(rb.cop[stance[0]], float) - mcops[stance[0]])[:2])
    out["weight_n"] = c.weight
    return out


def summarise_residual(rows: list) -> str:
    cols = {k: np.vstack([np.reshape(r[k], (-1, np.shape(r[k])[-1])) for r in rows if len(r[k])]) for k in ("f_meas", "res_force", "res_moment", "b_force", "b_cop_err")}
    bw = float(rows[0]["weight_n"])
    fz = cols["f_meas"][:, 2]
    res_f, res_m = cols["res_force"], cols["res_moment"]
    nf, mh = np.linalg.norm(res_f, axis=1), np.linalg.norm(res_m[:, :2], axis=1)
    implied = np.column_stack([-res_m[:, 1] / fz, res_m[:, 0] / fz])
    err = cols["b_cop_err"]
    lines = [f"single-support frames: {len(fz)}; body weight {bw:.1f} N",
             f"A_filtered root residual force: |F| mean {nf.mean():.1f} N ({100 * nf.mean() / bw:.1f}% BW), p95 {np.percentile(nf, 95):.1f} N ({100 * np.percentile(nf, 95) / bw:.1f}% BW); "
             f"components mean (x, y, z) {res_f.mean(axis=0).round(1).tolist()} N",
             f"A_filtered root residual horizontal moment about the root origin: |M| mean {mh.mean():.1f} N m, p95 {np.percentile(mh, 95):.1f} N m",
             f"CoP offset it implies (the shift of the measured force's point that closes the moment): x mean {1000 * implied[:, 0].mean():.1f} mm, median {1000 * np.median(implied[:, 0]):.1f}, "
             f"p95 of |x| {1000 * np.percentile(np.abs(implied[:, 0]), 95):.1f} mm; y mean {1000 * implied[:, 1].mean():.1f} mm",
             f"B's CoP minus the measured one, same frames: x mean {1000 * err[:, 0].mean():.1f} mm, median {1000 * np.median(err[:, 0]):.1f} mm; y mean {1000 * err[:, 1].mean():.1f} mm",
             f"identity check, B's total ground force minus (measured force + A's residual force): max |difference| {np.abs(cols['b_force'] - (cols['f_meas'] + res_f)).max():.3g} N"]
    return "\n".join(lines)


def main(argv=None):
    ap = argparse.ArgumentParser(prog="float_diag")
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name in ("cause", "a-sensitivity", "residual"):
        p = sub.add_parser(name)
        p.add_argument("--workers", type=int, default=6)
        if name == "cause":
            p.add_argument("--json")
    args = ap.parse_args(argv)
    {"cause": cause, "a-sensitivity": a_sensitivity, "residual": residual}[args.cmd](args)


if __name__ == "__main__":
    main()
