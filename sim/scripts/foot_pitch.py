"""
Stage 2d T2 (report; one constant offset only under the brief's trigger): the foot's pitch in stance, the model's sole against the dataset's
heel-to-toe-tip marker line, by decile of that foot's own stance. The diagnostics behind docs/memos/memo11-stage2d-diagnosis.md.

    python sim/scripts/gait_diag.py foot-pitch [--speeds 1.4 1.6] [--workers 5] [--cap 0] [--polygon-cap 4]

Pitch is toe-up positive. The model's sole pitch is the elevation of the foot box's long axis (0 at `stand_static`, where the soles are level). The
dataset's is the elevation of the line from the heel marker to the toe-tip marker, relative to the same subject's static trial (the toe-tip marker
sits lower than the heel marker on a flat foot, so only the change from standing is a pitch). Single support only for the pitch comparison. Nothing
here changes the model, the mapping, a default or a band, and nothing is written to the repo; the static trial's markers are read from the raw
archives each run.

The decile of stance is taken over the whole stance of the foot it belongs to, counted from that foot's heel strike (circularly: the contralateral
foot's stance runs from about 50% of the stride to about 10% of the next, so frames 51 to 99 and 0 to 11 are one stance).
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import gait  # noqa: E402

REPO = gait.REPO

OFF_FLAT_DEG = 6.0  # the pitch at which the 25 mm contact-polygon band changes shape on the 206 mm foot box: asin(25/206) = 7.0 deg, the brief's 6 deg is the round number below it
TRIGGER_MEAN_DEG = 1.0  # the brief's trigger: pooled mean difference over 30 to 60% of stance exceeds this in magnitude ...
TRIGGER_SD_DEG = 2.0  # ... and the standard deviation of the subject means is below this
WINDOW = (3, 4, 5)  # deciles 30 to 60% of stance
N_DEC = 10


# ------------------------------------------------------------------------------ pure helpers

def box_pitch_deg(R) -> float:
    """Elevation of a box's long (local x) axis above the horizontal, degrees, toe-up positive. R is the geom's 3x3 world rotation (columns are the local axes)."""
    ax = np.asarray(R, float).reshape(3, 3)[:, 0]
    return float(np.degrees(np.arctan2(ax[2], np.hypot(ax[0], ax[1]))))


def marker_pitch_deg(heel, toe):
    """Elevation of the line from the heel marker to the toe marker, degrees, toe-up positive. Points in the lab frame (y up); (..., 3)."""
    d = np.asarray(toe, float) - np.asarray(heel, float)
    return np.degrees(np.arctan2(d[..., 1], np.hypot(d[..., 0], d[..., 2])))


def relative_marker_pitch_deg(pitch, static_pitch):
    """The marker pitch relative to the subject's static trial."""
    return np.asarray(pitch, float) - float(static_pitch)


def stance_deciles(stance) -> np.ndarray:
    """Decile (0 to 9) of each frame of one foot's stance, counted from its heel strike, -1 outside stance. `stance` is the boolean flag of the
    100 unique phase points of a stride (frame 100 repeats frame 0); the stance may wrap around the stride boundary."""
    s = np.asarray(stance, bool)
    n = len(s)
    out = np.full(n, -1, int)
    if not s.any():
        return out
    starts = np.flatnonzero(s & ~np.roll(s, 1))
    if len(starts) == 0:
        raise ValueError("a flag that is true throughout has no heel strike to count from")
    # the force threshold flickers at toe-off (a one or two frame blip after the stance, about a quarter of the foot-strides): the stance is the
    # longest circular run and a shorter run is not part of it
    runs = []
    for st in starts:
        length = 0
        while s[(st + length) % n]:
            length += 1
        runs.append((length, int(st)))
    length, start = max(runs)
    for j in range(length):
        k = (start + j) % n
        out[k] = min(N_DEC - 1, int(N_DEC * j / length))
    return out


def by_decile(rows, off_flat_deg=OFF_FLAT_DEG) -> dict:
    """Per decile of stance: frames, mean model pitch, mean dataset pitch, mean difference (model minus dataset) and the standard deviation across
    subjects of the subject means (every subject counts once, however many strides it has), and the fractions of frames more than `off_flat_deg`
    off flat. `rows` are dicts with subject, dec, model, data."""
    out = {}
    for dec in sorted({r["dec"] for r in rows}):
        sel = [r for r in rows if r["dec"] == dec]
        subs = sorted({r["subject"] for r in sel})
        mod = [np.mean([r["model"] for r in sel if r["subject"] == s]) for s in subs]
        dat = [np.mean([r["data"] for r in sel if r["subject"] == s]) for s in subs]
        diff = np.array(mod) - np.array(dat)
        out[dec] = {"n": len(sel), "mean_model": float(np.mean(mod)), "mean_data": float(np.mean(dat)), "mean_diff": float(diff.mean()),
                    "sd_subject_means": float(diff.std(ddof=1)) if len(diff) > 1 else float("nan"),
                    "frac_model_off_flat": float(np.mean([abs(r["model"]) > off_flat_deg for r in sel])),
                    "frac_data_off_flat": float(np.mean([abs(r["data"]) > off_flat_deg for r in sel]))}
    return out


def pool_window(rows, decs=WINDOW) -> dict:
    """The mean difference over the frames of the given deciles: each subject's frames are averaged first, then the subjects are, and the
    standard deviation is that of the subject means (ddof 1)."""
    sel = [r for r in rows if r["dec"] in decs]
    subs = sorted({r["subject"] for r in sel})
    d = np.array([np.mean([r["model"] - r["data"] for r in sel if r["subject"] == s]) for s in subs])
    mo = np.array([np.mean([r["model"] for r in sel if r["subject"] == s]) for s in subs])
    da = np.array([np.mean([r["data"] for r in sel if r["subject"] == s]) for s in subs])
    return {"n": len(sel), "n_subjects": len(subs), "mean_diff": float(d.mean()), "sd_subject_means": float(d.std(ddof=1)),
            "mean_model": float(mo.mean()), "mean_data": float(da.mean()), "min_subject": float(d.min()), "max_subject": float(d.max())}


def offset_for_trigger(mean_diff, sd_subject_means):
    """The brief's trigger: |mean| > 1.0 degree and sd < 2.0 degrees fire a constant offset equal to the negative of the mean, to 0.1 degree;
    otherwise None."""
    if abs(mean_diff) > TRIGGER_MEAN_DEG and sd_subject_means < TRIGGER_SD_DEG:
        return round(-float(mean_diff), 1)
    return None


CRITERION_DECILES = (2, 3)  # 20 to 40% of stance, counted from heel strike (Stage 2e brief, "Foot offset")
OFFSET_DEFAULT_DEG = -3.4  # memo11's recommendation, kept when the criterion lands within OFFSET_TOLERANCE_DEG of it
OFFSET_TOLERANCE_DEG = 1.0  # the brief's


def window_mean_model(rows, decs=CRITERION_DECILES) -> float:
    """Mean model sole pitch over the frames of the given deciles: each subject's frames averaged first, then the subjects (every subject counts once)."""
    sel = [r for r in rows if r["dec"] in decs]
    subs = sorted({r["subject"] for r in sel})
    return float(np.mean([np.mean([r["model"] for r in sel if r["subject"] == s]) for s in subs]))


def criterion_offset(rows, decs=CRITERION_DECILES) -> float:
    """The ankle offset (degrees) that makes the mean model sole pitch zero over the window: minus that mean (a constant ankle offset shifts the
    sole's pitch by exactly that angle, test_the_model_sole_follows_a_rotation_of_the_ankle). Unrounded."""
    return -window_mean_model(rows, decs)


def choose_offset(criterion, default=OFFSET_DEFAULT_DEG, tol=OFFSET_TOLERANCE_DEG):
    """(value, which): the default when the criterion is within `tol` of it, otherwise the criterion rounded to 0.1 degree."""
    if abs(criterion - default) <= tol + 1e-12:
        return float(default), "default"
    return round(float(criterion), 1), "criterion"


def with_ankle_offset(ik, offset_deg):
    """A copy of the dataset's IK array with `offset_deg` added to both ankle angles (dorsiflexion positive, the mapping's sign is +1). This is what a constant
    ankle offset in the mapping would do to the retargeted ankle, applied to the input instead of the mapping: a counterfactual for the report, no mapping
    or retargeting change."""
    import retarget
    names = retarget._channels()
    out = np.array(ik, float, copy=True)
    for n in ("ankle_angle_r", "ankle_angle_l"):
        out[:, names.index(n)] += float(offset_deg)
    return out


# ------------------------------------------------------------------------------ the model's sole

def sole_pitch_deg(model, q, foot, data=None) -> float:
    """Pitch of one foot's sole for the pose q (toe-up positive), from the foot body's box geom."""
    import mujoco
    d = data if data is not None else mujoco.MjData(model)
    d.qpos[:] = q
    mujoco.mj_kinematics(model, d)
    body = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_BODY, foot)
    for g in range(model.ngeom):
        if model.geom_bodyid[g] == body and model.geom_type[g] == mujoco.mjtGeom.mjGEOM_BOX:
            return box_pitch_deg(d.geom_xmat[g])
    raise ValueError(f"no box geom on {foot}")


# ------------------------------------------------------------------------------ the dataset's static trial

def static_marker_pitch_deg(subject: str) -> dict:
    """Mean heel-to-toe-tip marker pitch of each foot in the subject's static trial(s), degrees, {'R': .., 'L': ..} (raw archives, mm in the file)."""
    import re
    import zipfile
    import ingest_camargo as ic
    zf = zipfile.ZipFile(ic.raw_dir() / f"{subject}.zip")
    names = sorted(n for n in zf.namelist() if re.search(r"/static/markers/.*\.mat$", n))
    if not names:
        raise FileNotFoundError(f"{subject}: no static marker file in the archive")
    acc = {"R": [], "L": []}
    for n in names:
        t = ic.read_table(zf.read(n))
        for f in ("R", "L"):
            heel = np.stack([t[f"{f}_Heel_{c}"] for c in "xyz"], axis=1)
            toe = np.stack([t[f"{f}_Toe_Tip_{c}"] for c in "xyz"], axis=1)
            acc[f].append(marker_pitch_deg(heel, toe))
    return {f: float(np.nanmean(np.concatenate(v))) for f, v in acc.items()}


# ------------------------------------------------------------------------------ the per-subject worker

def subject_rows(task: dict) -> list:
    """Rows for every stance frame of one subject at one speed: subject, speed, foot, dec, support ('single' or 'double'), model and data pitch
    (relative to the static trial) and, when asked, the distance of the measured CoP outside that foot's 25 mm contact polygon."""
    import gaitloads
    import retarget
    dyn = gait.dynamics
    c = gait._ctx(task["model_path"])
    m = c.model
    s, sp, cap = task["subject"], task["speed"], task["cap"]
    z = np.load(Path(task["processed"]) / f"{s}.npz")
    d = task["subject_info"]
    static = static_marker_pitch_deg(s)
    ratio = retarget.leg_length_ratio(m, d["height_m"])
    mapping = retarget.mapping_without_offsets(c.mapping) if task.get("ignore_mapping_offset") else c.mapping
    import mujoco
    work = mujoco.MjData(m)
    out = []
    for i in range(d["strides"][sp] if not cap else min(cap, d["strides"][sp])):
        ik, fpl, fmk = z[f"{sp}_ik"][i], z[f"{sp}_fp"][i], z[f"{sp}_foot_markers"][i]
        if task.get("ankle_offset_deg"):
            ik = with_ankle_offset(ik, task["ankle_offset_deg"])
        cyc = retarget.Cycle(m, mapping, c.stand, ik, float(z[f"{sp}_duration_s"][i]), ratio, hip_in_pelvis_os=d["hip_in_pelvis_os_m"],
                             trunk=task["trunk"], pitch_mean="measured", pitch_offset_deg=task["pitch_offset_deg"])
        q, _, _ = cyc.grid()
        for fi, foot in enumerate(gait.FEET):
            decs = stance_deciles(fpl[fi, :100, 6] >= gaitloads.STANCE_FLAG)
            for k in np.flatnonzero(decs >= 0):
                stance = tuple(f for j, f in enumerate(gait.FEET) if fpl[j, k, 6] >= gaitloads.STANCE_FLAG)
                row = {"subject": s, "speed": sp, "foot": foot, "dec": int(decs[k]), "support": "single" if len(stance) == 1 else "double",
                       "model": sole_pitch_deg(m, q[k], foot, work),
                       "data": float(relative_marker_pitch_deg(marker_pitch_deg(fmk[k, fi, 0], fmk[k, fi, 1]), static["RL"[fi]]))}
                if task["polygon"]:
                    mf, mc = gaitloads.measured_to_model_foot(fpl[:, k, :], fmk[k], dyn.foot_floor_segments(m, q[k]), c.mass / d["mass_kg"])
                    row["outside_m"] = float(dyn.polygon_outside_m(m, q[k], (foot,), mc[foot][:2]))
                out.append(row)
    return out


def collect(speeds, workers, cap, polygon, trunk="rigid", pitch_offset_deg=0.0, ankle_offset_deg=0.0, ignore_mapping_offset=False) -> dict:
    """{speed: rows} for all 17 subjects."""
    import json
    from concurrent.futures import ProcessPoolExecutor
    spec = gait.load_spec("walk_treadmill")
    manifest = json.loads((REPO / spec["dataset"]["manifest"]).read_text(encoding="utf-8"))
    tasks = [{"subject": s, "speed": sp, "cap": cap, "polygon": polygon, "trunk": trunk, "pitch_offset_deg": pitch_offset_deg,
              "ankle_offset_deg": ankle_offset_deg, "ignore_mapping_offset": ignore_mapping_offset, "model_path": str(gait.simrun.MODEL_FILE), "processed": str(REPO / spec["dataset"]["processed"]), "subject_info": info}
             for sp in speeds for s, info in manifest["subjects"].items()]
    if workers <= 1:
        res = [subject_rows(t) for t in tasks]
    else:
        with ProcessPoolExecutor(max_workers=workers) as ex:
            res = list(ex.map(subject_rows, tasks, chunksize=1))
    out = {sp: [] for sp in speeds}
    for t, r in zip(tasks, res):
        out[t["speed"]] += r
    return out


# ------------------------------------------------------------------------------ the polygon by decile

def polygon_by_decile(rows, band_m=0.0) -> dict:
    """{(dec, support): (n, fraction outside, median outside mm, p95 outside mm)}; outside means the distance is above `band_m` (the polygon already
    carries its 25 mm vertex band, so 0 here is the memo10 rule)."""
    out = {}
    for dec in range(N_DEC):
        for sup in ("single", "double"):
            v = np.array([r["outside_m"] for r in rows if r["dec"] == dec and r["support"] == sup and "outside_m" in r])
            o = v[v > band_m + 1e-9]
            out[(dec, sup)] = (len(v), len(o) / len(v) if len(v) else float("nan"),
                               1000 * float(np.median(o)) if len(o) else 0.0, 1000 * float(np.percentile(o, 95)) if len(o) else 0.0)
    return out


# ------------------------------------------------------------------------------ the report

def criterion_report(args):
    """Stage 2e T3: the value of the ankle offset by the brief's criterion, measured with the mapping's own offsets removed (so it can be rerun after
    the value is authored): mean model sole pitch over single-support frames at 20 to 40% of stance, 1.4 m/s, pooled over the subjects."""
    rows = collect(["1.4"], args.workers, args.cap, False, ignore_mapping_offset=True)["1.4"]
    single = [r for r in rows if r["support"] == "single"]
    w = pool_window(single, CRITERION_DECILES)
    crit = criterion_offset(single)
    value, which = choose_offset(crit)
    win = [r for r in single if r["dec"] in CRITERION_DECILES]
    subs = sorted({r["subject"] for r in win})
    per = np.array([np.mean([r["model"] for r in win if r["subject"] == s]) for s in subs])
    print(f"criterion window: single support, 20 to 40% of stance, 1.4 m/s, {len(win)} frames, {len(subs)} subjects (mapping offsets removed)")
    print(f"  mean model sole pitch (toe-up positive): subjects averaged {w['mean_model']:+.3f}, frames pooled {np.mean([r['model'] for r in win]):+.3f}; "
          f"sd of the subject means {per.std(ddof=1):.2f}, range {per.min():+.2f} to {per.max():+.2f}")
    print(f"  marker cross-check (heel to toe-tip marker line minus the static trial): dataset {w['mean_data']:+.3f} in 20-40%; "
          f"model minus dataset {w['mean_diff']:+.3f} (sd of subject differences {w['sd_subject_means']:.2f})")
    w2 = pool_window(single, (3, 4, 5))
    print(f"  the same over 30 to 60%: model {w2['mean_model']:+.3f}, dataset {w2['mean_data']:+.3f}, difference {w2['mean_diff']:+.3f}")
    print(f"criterion offset {crit:+.3f} deg; default {OFFSET_DEFAULT_DEG:+.1f}, tolerance {OFFSET_TOLERANCE_DEG}; the rule gives {value:+.1f} ({which})")


def report(args):
    if getattr(args, "criterion", False):
        return criterion_report(args)
    speeds = list(args.speeds)
    nomap = getattr(args, "no_mapping_offset", False)
    rows = collect(speeds, args.workers, args.cap, False, pitch_offset_deg=args.pitch_offset_deg, ankle_offset_deg=args.ankle_offset_deg, ignore_mapping_offset=nomap)
    print(f"foot box: 206 mm long (165 mm ahead of the ankle, 41 mm behind); a 25 mm band changes shape at asin(25/206) = 7.0 deg, the brief's 6 deg is used for 'off flat'")
    allrows = []
    for sp in speeds:
        single = [r for r in rows[sp] if r["support"] == "single"]
        allrows += single
        n_sub = len({r["subject"] for r in single})
        print(f"=== {sp} m/s, single support, {len(single)} frames, {n_sub} subjects: toe-up positive, degrees ===")
        print("stance %   n     model   dataset   diff   sd(subj means)   model >6 off   data >6 off")
        for dec, v in by_decile(single).items():
            print(f"  {10 * dec:2d}-{10 * dec + 10:3d} {v['n']:6d} {v['mean_model']:7.2f} {v['mean_data']:8.2f} {v['mean_diff']:7.2f} {v['sd_subject_means']:10.2f} "
                  f"{100 * v['frac_model_off_flat']:12.1f}% {100 * v['frac_data_off_flat']:12.1f}%")
        w = pool_window(single)
        print(f"  30-60%: mean diff {w['mean_diff']:+.2f}, sd of {w['n_subjects']} subject means {w['sd_subject_means']:.2f}, model {w['mean_model']:+.2f}, "
              f"dataset {w['mean_data']:+.2f}, subjects from {w['min_subject']:+.2f} to {w['max_subject']:+.2f}")
    w = pool_window(allrows)
    off = offset_for_trigger(w["mean_diff"], w["sd_subject_means"])
    print(f"=== both speeds pooled, 30-60% of stance: mean diff {w['mean_diff']:+.3f}, sd of subject means {w['sd_subject_means']:.3f} "
          f"(n = {w['n']} frames, {w['n_subjects']} subjects) ===")
    print(f"trigger (|mean| > {TRIGGER_MEAN_DEG} and sd < {TRIGGER_SD_DEG}): " + (f"FIRES, offset {off:+.1f} deg" if off is not None else "does not fire"))
    if args.polygon_cap is not None:
        prow = collect(speeds, args.workers, args.polygon_cap, True, trunk=args.trunk, pitch_offset_deg=args.pitch_offset_deg,
                       ankle_offset_deg=args.ankle_offset_deg, ignore_mapping_offset=nomap)
        for sp in speeds:
            pg = polygon_by_decile(prow[sp])
            print(f"=== {sp} m/s, the measured CoP on each foot's own 25 mm polygon by decile of that foot's stance (heel strike to toe-off), "
                  f"{args.polygon_cap or 'all'} strides per subject ===")
            print("stance %   single support: outside % (median / p95 mm), n        double support: outside % (median / p95 mm), n")
            for dec in range(N_DEC):
                cell = lambda t: "-" if not t[0] else f"{100 * t[1]:5.1f} ({t[2]:3.0f} / {t[3]:3.0f}) n={t[0]}"
                print(f"  {10 * dec:2d}-{10 * dec + 10:3d}    {cell(pg[(dec, 'single')]):>34s}      {cell(pg[(dec, 'double')]):>34s}")
