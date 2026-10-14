"""
Stage 2e T6 (report only): where the thigh to shank split of the dataset's subjects comes from, from the dataset's own files.

    python sim/scripts/gait_diag.py split-audit

Per subject: the OpenSim model's thigh (hip joint centre to knee centre at zero flexion, knee_gain.thigh_length_m) and shank (knee centre to ankle
centre, the tibia-frame location of the ankle joint), and, from the static trial's markers, a regression hip centre (Harrington et al. 2007, J Biomech
40:595-602, from the pelvis width and depth) and the lateral knee and ankle markers. The dataset has no medial epicondyle or malleolus markers, so a joint
centre cannot be taken as the midpoint of a pair; the lengths below are taken in the sagittal plane (the mediolateral component removed), which leaves
the marker-to-joint-centre offsets in the other two directions as the uncertainty.

Nothing here changes the model, the sheet, the mapping or any default, and nothing is written to the repo.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import gait  # noqa: E402

REPO = gait.REPO

# Harrington et al. 2007 regression of the hip joint centre in the pelvis frame (origin at the midpoint of the ASIS, x anterior, y up, z toward the
# side), mm, from the pelvic width PW (ASIS to ASIS) and depth PD (ASIS midpoint to PSIS midpoint): x = -0.24 PD - 9.9, y = -0.30 PW - 10.9, z = 0.33 PW + 7.3.
# Transcribed from a secondary source (the Visual3D wiki), not from the paper; the published prediction error is a maximum of 31 mm in adults (the paper's
# RMS is about 1.5 cm). The coefficients are recorded here because they are the regression the audit uses.
HARRINGTON_X = (-0.24, -9.9)
HARRINGTON_Y = (-0.30, -10.9)
HARRINGTON_Z = (0.33, 7.3)


# ------------------------------------------------------------------------------ pure helpers

def pelvis_frame(asis_r, asis_l, psis_r, psis_l) -> dict:
    """The pelvis frame of Bell and Harrington from the four markers (lab coordinates, mm): origin at the ASIS midpoint, `right` from the left ASIS to the
    right one, `anterior` from the PSIS midpoint to the ASIS midpoint made perpendicular to it, `up` their cross product (right-handed: right x anterior is
    not used; up = anterior x right... chosen so that up points toward the head for a subject whose right is +x and who faces -z)."""
    asis_r, asis_l, psis_r, psis_l = (np.asarray(v, float) for v in (asis_r, asis_l, psis_r, psis_l))
    mid_a, mid_p = 0.5 * (asis_r + asis_l), 0.5 * (psis_r + psis_l)
    right = (asis_r - asis_l) / np.linalg.norm(asis_r - asis_l)
    a = mid_a - mid_p
    anterior = a - (a @ right) * right
    anterior /= np.linalg.norm(anterior)
    up = np.cross(right, anterior)
    up /= np.linalg.norm(up)
    return {"origin": mid_a, "right": right, "anterior": anterior, "up": up, "width": float(np.linalg.norm(asis_r - asis_l)), "depth": float(np.linalg.norm(mid_a - mid_p))}


def harrington_hjc(frame) -> tuple:
    """(right, left) regression hip joint centres in lab coordinates, mm."""
    pw, pd = frame["width"], frame["depth"]
    x = HARRINGTON_X[0] * pd + HARRINGTON_X[1]
    y = HARRINGTON_Y[0] * pw + HARRINGTON_Y[1]
    z = HARRINGTON_Z[0] * pw + HARRINGTON_Z[1]
    base = frame["origin"] + x * frame["anterior"] + y * frame["up"]
    return base + z * frame["right"], base - z * frame["right"]


def length_without_lateral(a, b, frame) -> float:
    """Distance between two points with the component along the pelvis's lateral axis removed (a length in the sagittal plane)."""
    v = np.asarray(b, float) - np.asarray(a, float)
    v = v - (v @ frame["right"]) * frame["right"]
    return float(np.linalg.norm(v))


def spread(values) -> dict:
    v = np.asarray(values, float)
    return {"min": float(v.min()), "median": float(np.median(v)), "max": float(v.max()), "sd": float(v.std(ddof=1)) if len(v) > 1 else float("nan"), "n": int(len(v))}


def ratio(thigh, shank) -> float:
    return float(thigh / shank)


# ------------------------------------------------------------------------------ the dataset side

def _static_markers(zf):
    """Mean over the static trial(s) of each marker (lab, mm): {name: (3,)}."""
    import re
    import ingest_camargo as ic
    names = sorted(n for n in zf.namelist() if re.search(r"/static/markers/.*\.mat$", n))
    acc = {}
    for n in names:
        t = ic.read_table(zf.read(n))
        for key in t:
            if key.endswith("_x") and key[:-2] + "_y" in t:
                m = key[:-2]
                acc.setdefault(m, []).append(np.stack([t[m + "_x"], t[m + "_y"], t[m + "_z"]], axis=1))
    return {m: np.nanmean(np.concatenate(v), axis=0) for m, v in acc.items()}


def subject_row(subject: str) -> dict:
    import zipfile
    import ingest_camargo as ic
    import knee_gain
    zf = zipfile.ZipFile(ic.raw_dir() / f"{subject}.zip")
    blob = zf.read(next(n for n in zf.namelist() if n.lower() == f"osimxml/{subject.lower()}.osim"))
    row = {"subject": subject, "osim_thigh": 1000 * knee_gain.thigh_length_m(blob, "r"), "osim_shank": 1000 * float(np.linalg.norm(knee_gain._ankle_translation(blob)))}
    mk = _static_markers(zf)
    f = pelvis_frame(mk["R_ASIS"], mk["L_ASIS"], mk["R_PSIS"], mk["L_PSIS"])
    hr, hl = harrington_hjc(f)
    row["pelvic_width"], row["pelvic_depth"] = f["width"], f["depth"]
    row["mk_thigh"] = 0.5 * (length_without_lateral(hr, mk["R_Knee_Lat"], f) + length_without_lateral(hl, mk["L_Knee_Lat"], f))
    row["mk_shank"] = 0.5 * (length_without_lateral(mk["R_Knee_Lat"], mk["R_Ankle_Lat"], f) + length_without_lateral(mk["L_Knee_Lat"], mk["L_Ankle_Lat"], f))
    return row


def report(args):
    import json
    c = gait._ctx(gait.simrun.MODEL_FILE)
    manifest = json.loads((REPO / "data" / "camargo2021" / "manifest.json").read_text(encoding="utf-8"))
    import mujoco
    m = c.model
    d = mujoco.MjData(m)
    d.qpos[:] = c.stand
    mujoco.mj_kinematics(m, d)
    jid = lambda n: mujoco.mj_name2id(m, mujoco.mjtObj.mjOBJ_JOINT, n)
    hip, knee, ankle = (d.xanchor[jid(n)] for n in ("hip_fe_right", "knee_right", "ankle_pdflex_right"))
    fthigh, fshank = 1000 * float(np.linalg.norm(knee - hip)), 1000 * float(np.linalg.norm(ankle - knee))
    rows = [subject_row(s) for s in manifest["subjects"]]
    for r in rows:
        r["height_m"] = manifest["subjects"][r["subject"]]["height_m"]
        r["osim_ratio"], r["mk_ratio"] = ratio(r["osim_thigh"], r["osim_shank"]), ratio(r["mk_thigh"], r["mk_shank"])
        r["osim_sum"], r["mk_sum"] = r["osim_thigh"] + r["osim_shank"], r["mk_thigh"] + r["mk_shank"]
    print(f"Freyja at stand_static: thigh {fthigh:.1f} mm, shank {fshank:.1f} mm, ratio {fthigh / fshank:.3f}, sum {fthigh + fshank:.1f} mm")
    print("subject  height m | OpenSim thigh  shank  ratio  sum | markers (regression hip, lateral knee and ankle, sagittal plane) thigh  shank  ratio  sum | pelvic width, depth")
    for r in rows:
        print(f"  {r['subject']}   {r['height_m']:.3f} | {r['osim_thigh']:7.1f} {r['osim_shank']:7.1f} {r['osim_ratio']:6.3f} {r['osim_sum']:7.1f} | "
              f"{r['mk_thigh']:7.1f} {r['mk_shank']:7.1f} {r['mk_ratio']:6.3f} {r['mk_sum']:7.1f} | {r['pelvic_width']:5.0f} {r['pelvic_depth']:5.0f}")
    print("across the 17 subjects: min / median / max / sd (n)")
    for key, lab in (("osim_thigh", "OpenSim thigh mm"), ("osim_shank", "OpenSim shank mm"), ("osim_ratio", "OpenSim thigh/shank"), ("osim_sum", "OpenSim thigh+shank mm"),
                     ("mk_thigh", "marker thigh mm"), ("mk_shank", "marker shank mm"), ("mk_ratio", "marker thigh/shank"), ("mk_sum", "marker thigh+shank mm")):
        s = spread([r[key] for r in rows])
        print(f"  {lab:24s} {s['min']:8.3f} / {s['median']:8.3f} / {s['max']:8.3f} / {s['sd']:7.3f} ({s['n']})")
    dthigh = np.array([r["mk_thigh"] - r["osim_thigh"] for r in rows])
    dshank = np.array([r["mk_shank"] - r["osim_shank"] for r in rows])
    print(f"marker minus OpenSim: thigh mean {dthigh.mean():+.1f} mm (sd {dthigh.std(ddof=1):.1f}), shank mean {dshank.mean():+.1f} mm (sd {dshank.std(ddof=1):.1f}); "
          f"correlation of the two per-subject ratios {np.corrcoef([r['osim_ratio'] for r in rows], [r['mk_ratio'] for r in rows])[0, 1]:+.2f}")
