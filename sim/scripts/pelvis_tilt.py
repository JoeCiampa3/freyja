"""
Stage 2d T6 (report only): the pelvic tilt from the ASIS and PSIS markers, static and walking, against the IK pelvis pitch, and the hip extension relative
to the marker-defined pelvis. The diagnostics behind docs/memos/memo11-stage2d-diagnosis.md.

    python sim/scripts/gait_diag.py marker-hip [--speeds 1.4 1.6] [--workers 5]

Markers: R_ASIS, L_ASIS, R_PSIS, L_PSIS (the treadmill trials' marker files and the static trial's, in the raw archives; nothing is cached in the repo).
The tilt is `gait_diag.marker_pelvic_tilt_deg` (anterior positive; forward is taken from the pelvis itself). The hip angle relative to the marker pelvis is
the thigh's flexion from the vertical (hip flexion plus `pelvis_list`, the T1 rule) plus the marker pelvis's anterior tilt, which is the ISB convention
(the pelvis's anterior axis lies in the ASIS-PSIS plane, so a pelvis tilted forward by t flexes the hip by t when the thigh is vertical). Nothing here changes
the model, the sheet, the mapping, a default or the band.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import gait  # noqa: E402

REPO = gait.REPO
MIN_VALID = 0.9  # a stride's marker window needs this fraction of finite tilt samples; fewer and the stride is skipped, not filled


def tilt_series(table: dict, t0: float, T: float, n: int = 100, min_valid: float = MIN_VALID):
    """The marker pelvic tilt (degrees, anterior positive) at the n phase points of the stride [t0, t0 + T) (the ingest's own grid), gaps interpolated;
    None when fewer than `min_valid` of the samples in the stride's window are finite."""
    import gait_diag
    cols = lambda name: np.stack([table[f"{name}_{c}"] for c in "xyz"], axis=1)
    tilt = gait_diag.marker_pelvic_tilt_deg(cols("R_ASIS"), cols("L_ASIS"), cols("R_PSIS"), cols("L_PSIS"))
    t = np.asarray(table["Header"], float)
    ok = np.isfinite(tilt)
    window = (t >= t0) & (t <= t0 + T)
    if not window.any() or ok[window].mean() < min_valid:
        return None
    return np.interp(t0 + T * np.arange(n) / n, t[ok], tilt[ok])


def hip_relative_to_marker_pelvis(hip_deg, pelvis_list_deg, tilt_deg):
    """Hip flexion relative to the marker-defined pelvis: the thigh's flexion from the vertical (hip + list) plus the marker pelvis's anterior tilt."""
    return np.asarray(hip_deg, float) + np.asarray(pelvis_list_deg, float) + np.asarray(tilt_deg, float)


def peak_extension(right, left) -> float:
    """Minus the smallest hip angle of either limb (extension positive; negative when the hip never extends)."""
    return float(-min(np.min(right), np.min(left)))


def static_tilt_deg(zf, ic) -> float:
    """Mean marker pelvic tilt over the subject's static trial(s)."""
    import gait_diag
    names = sorted(n for n in zf.namelist() if re.search(r"/static/markers/.*\.mat$", n))
    vals = [gait_diag._tilt_from_table(ic.read_table(zf.read(n)))[0] for n in names]
    return float(np.mean(vals))


def subject_task(task: dict) -> dict:
    import zipfile
    sys.path.insert(0, str(REPO / "analysis"))
    import ingest_camargo as ic
    s = task["subject"]
    zf = zipfile.ZipFile(ic.raw_dir() / f"{s}.zip")
    names = zf.namelist()
    z = np.load(Path(task["processed"]) / f"{s}.npz")
    ch = ic.IK_CHANNELS
    out = {"subject": s, "static_marker_tilt": static_tilt_deg(zf, ic), "static_ik_pitch": float(task["subject_info"]["static_pelvis_pitch_deg"]), "rows": [], "skipped": {}}
    cache = {}
    for sp in task["speeds"]:
        skipped = 0
        for i in range(len(z[f"{sp}_duration_s"])):
            trial = int(z[f"{sp}_trial"][i])
            if trial not in cache:
                n = next(x for x in names if re.search(rf"/treadmill/markers/treadmill_{trial:02d}_\d+\.mat$", x))
                cache[trial] = ic.read_table(zf.read(n))
            tilt = tilt_series(cache[trial], float(z[f"{sp}_t0"][i]), float(z[f"{sp}_duration_s"][i]))
            if tilt is None:
                skipped += 1
                continue
            ik = z[f"{sp}_ik"][i][:gait.N_FRAMES]
            col = lambda n: ik[:, ch.index(n)]
            lst = col("pelvis_list")
            hip_r, hip_l = col("hip_flexion_r"), col("hip_flexion_l")
            rel = lambda hip, tl: hip_relative_to_marker_pelvis(hip, lst, tl)
            out["rows"].append({"speed": sp, "walk_marker_tilt": float(tilt.mean()), "walk_ik_pitch": float(-lst.mean()),
                                "hip_ik": peak_extension(hip_r, hip_l),
                                "thigh_vertical": peak_extension(hip_r + lst, hip_l + lst),
                                "hip_marker": peak_extension(rel(hip_r, tilt), rel(hip_l, tilt)),
                                "hip_marker_const": peak_extension(rel(hip_r, tilt.mean()), rel(hip_l, tilt.mean())),
                                "hip_flexion_max_marker": float(max(rel(hip_r, tilt).max(), rel(hip_l, tilt).max()))})
        out["skipped"][sp] = skipped
    return out


def report(args):
    import json
    from concurrent.futures import ProcessPoolExecutor
    spec = gait.load_spec("walk_treadmill")
    manifest = json.loads((REPO / spec["dataset"]["manifest"]).read_text(encoding="utf-8"))
    tasks = [{"subject": s, "subject_info": info, "processed": str(REPO / spec["dataset"]["processed"]), "speeds": list(args.speeds)} for s, info in manifest["subjects"].items()]
    if args.workers <= 1:
        res = [subject_task(t) for t in tasks]
    else:
        with ProcessPoolExecutor(max_workers=args.workers) as ex:
            res = list(ex.map(subject_task, tasks, chunksize=1))
    print("markers used: R_ASIS, L_ASIS, R_PSIS, L_PSIS (treadmill and static trials); tilt anterior positive, degrees")
    print(f"{'subject':8s} {'static IK':>9s} {'static mk':>9s} {'mk - IK':>8s} | " + " | ".join(f"{sp} m/s: walk IK, walk mk, mk - IK, walk - static (IK, mk)" for sp in args.speeds))
    for r in res:
        cells = []
        for sp in args.speeds:
            rows = [x for x in r["rows"] if x["speed"] == sp]
            if not rows:
                cells.append("no strides")
                continue
            ik, mk = np.mean([x["walk_ik_pitch"] for x in rows]), np.mean([x["walk_marker_tilt"] for x in rows])
            cells.append(f"{ik:6.1f} {mk:6.1f} {mk - ik:6.1f} {ik - r['static_ik_pitch']:+6.1f} {mk - r['static_marker_tilt']:+6.1f}" + (f" ({r['skipped'][sp]} skipped)" if r["skipped"][sp] else ""))
        print(f"{r['subject']:8s} {r['static_ik_pitch']:9.1f} {r['static_marker_tilt']:9.1f} {r['static_marker_tilt'] - r['static_ik_pitch']:8.1f} | " + " | ".join(cells))
    st_mk = np.array([r["static_marker_tilt"] for r in res])
    st_ik = np.array([r["static_ik_pitch"] for r in res])
    print(f"static, 17 subjects: marker tilt mean {st_mk.mean():.1f} (sd {st_mk.std(ddof=1):.1f}, range {st_mk.min():.1f} to {st_mk.max():.1f}); IK pitch mean {st_ik.mean():.1f} (sd {st_ik.std(ddof=1):.1f}); marker minus IK {np.mean(st_mk - st_ik):+.1f} (sd {np.std(st_mk - st_ik, ddof=1):.1f})")
    for sp in args.speeds:
        rows = [x for r in res for x in r["rows"] if x["speed"] == sp]
        sub_mk = np.array([np.mean([x["walk_marker_tilt"] for x in r["rows"] if x["speed"] == sp]) for r in res])
        sub_ik = np.array([np.mean([x["walk_ik_pitch"] for x in r["rows"] if x["speed"] == sp]) for r in res])
        print(f"=== {sp} m/s, {len(rows)} strides ({sum(r['skipped'][sp] for r in res)} skipped for missing markers) ===")
        print(f"  walking pelvic tilt per subject: marker mean {sub_mk.mean():.1f} (sd {sub_mk.std(ddof=1):.1f}, range {sub_mk.min():.1f} to {sub_mk.max():.1f}); IK pitch mean {sub_ik.mean():.1f} (sd {sub_ik.std(ddof=1):.1f}, range {sub_ik.min():.1f} to {sub_ik.max():.1f})")
        print("  peak hip extension, degrees, median / 95th percentile / maximum over strides:")
        for key, label in (("hip_ik", "relative to the IK pelvis (the model's joint as retargeted)"), ("thigh_vertical", "from the vertical (thigh angle, no pelvis)"),
                           ("hip_marker", "relative to the marker pelvis, its tilt through the stride"), ("hip_marker_const", "relative to the marker pelvis, its stride-mean tilt")):
            v = np.array([x[key] for x in rows])
            print(f"    {label:62s} {np.median(v):6.1f} / {np.percentile(v, 95):6.1f} / {v.max():6.1f}")
        d = np.array([x["hip_marker"] - x["thigh_vertical"] for x in rows])
        print(f"  marker-pelvis extension minus the extension from the vertical, per stride: mean {d.mean():+.1f} (sd {d.std():.1f}); strides whose marker pelvis tilts more than 5 degrees anterior on average: {100 * np.mean([x['walk_marker_tilt'] > 5 for x in rows]):.0f}%")
        sub = [(r["subject"], np.median([x["hip_marker"] for x in r["rows"] if x["speed"] == sp])) for r in res]
        print("  per subject, median extension relative to the marker pelvis: " + ", ".join(f"{a} {b:.1f}" for a, b in sub))
