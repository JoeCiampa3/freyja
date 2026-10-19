"""
Stage 2 diagnostics ahead of the snapshot change (report only; memo23). Nothing here changes the model, the template, the sheet, the preprocessor, the
spec or a tracked output.

    python sim/scripts/snapshot_diag.py foot       # D1 foot geometry from the static trials, and D7 (trunk and head chords, if the markers exist)
    python sim/scripts/snapshot_diag.py tilt       # D2 static pelvic tilt in the Dumas frame, against the IK pelvis and the model
    python sim/scripts/snapshot_diag.py hipstop    # D3 hip extension demand against the model's stop
    python sim/scripts/snapshot_diag.py lateral    # D5 the strides behind the lumbosacral rigid-mode lateral torque maxima
    python sim/scripts/snapshot_diag.py stamp      # D6 git_dirty and diff_sha256 of the tracked extract and of the newest gait record
    python sim/scripts/snapshot_diag.py ansur      # D8 ANSUR II female statistics (data/ansur2/raw, gitignored)

The raw folder is resolved through ingest_camargo.raw_dir(); the config file is never printed. D4 (the polygon by decile) is
`gait_diag.py foot-pitch --polygon-cap 0`, unchanged.

Frames. Static trials are lab-frame marker tables (mm, y up); the facing differs between trials, so every angle and length here is taken from the
markers themselves (forward is the horizontal heel-to-toe-tip direction of a foot, the anterior axis of the pelvis for the pelvis), never from a lab axis.
"""
from __future__ import annotations

import csv
import json
import re
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "analysis"))

UP = np.array([0.0, 1.0, 0.0])  # the lab's vertical in the marker tables
FOOT_FIT_MARKERS = ("Heel", "Toe_Lat", "Toe_Med", "Toe_Tip")  # the markers on the calcaneus body in the OpenSim model, fitted rigidly to the static trial
NON_TRUNK_PREFIXES = ("ASIS", "PSIS", "Heel", "Toe", "Ankle", "Knee", "Thigh", "Shank")  # the lower-limb and pelvis marker names of the Camargo set


# ------------------------------------------------------------------------------ rigid fit and the foot

def kabsch(P, Q):
    """(R, t, rms): the proper rotation and translation that best map the points P (n, 3) onto Q (n, 3) in the least-squares sense (Q ~ P @ R.T + t),
    and the RMS residual in the units of the points. Never a reflection."""
    P, Q = np.asarray(P, float), np.asarray(Q, float)
    pc, qc = P.mean(axis=0), Q.mean(axis=0)
    U, _, Vt = np.linalg.svd((P - pc).T @ (Q - qc))
    d = np.sign(np.linalg.det(Vt.T @ U.T))
    R = Vt.T @ np.diag([1.0, 1.0, d]) @ U.T
    t = qc - R @ pc
    res = Q - (P @ R.T + t)
    return R, t, float(np.sqrt(np.mean(np.sum(res ** 2, axis=1))))


def _by_suffix(markers: dict, suffix: str):
    for k, v in markers.items():
        if k.endswith(suffix):
            return np.asarray(v, float)
    raise KeyError(suffix)


def foot_geometry(markers_lab: dict, calcn_markers: dict, ajc, mtp) -> dict:
    """Foot-frame distances of one foot from one static pose. `markers_lab` are the static trial's mean marker positions (m, lab, y up); `calcn_markers`
    the same markers in the model's calcaneus frame, `ajc` and `mtp` the model's ankle and metatarsophalangeal centres in that frame. The calcaneus frame is
    fitted to the four foot markers (`kabsch`), which carries both centres into the lab. Forward is the horizontal heel-to-toe-tip direction, up the lab's
    vertical. Foot length is the heel-to-toe-tip distance along forward; fractions use the forward components (all lengths in metres)."""
    names = [n for n in calcn_markers if any(n.endswith(s) for s in FOOT_FIT_MARKERS) and n in markers_lab]
    R, t, rms = kabsch([calcn_markers[n] for n in names], [markers_lab[n] for n in names])
    ajc_lab, mtp_lab = R @ np.asarray(ajc, float) + t, R @ np.asarray(mtp, float) + t
    own = {n: markers_lab[n] for n in calcn_markers if n in markers_lab}  # this foot's markers only: the static trial carries both feet's
    heel, tip = _by_suffix(own, "Heel"), _by_suffix(own, "Toe_Tip")
    h = tip - heel
    h = h - (h @ UP) * UP
    fwd = h / np.linalg.norm(h)
    comp = lambda a, b: float((b - a) @ fwd)
    length = comp(heel, tip)
    out = {"fit_rms_m": rms, "n_fit_markers": len(names), "ajc_lab": ajc_lab, "mtp_lab": mtp_lab, "fwd": fwd, "heel_lab": heel, "foot_length_m": length,
           "ajc_to_heel_fwd_m": comp(heel, ajc_lab), "ajc_to_toe_tip_fwd_m": comp(ajc_lab, tip), "ajc_to_mtp_fwd_m": comp(ajc_lab, mtp_lab),
           "ajc_to_heel_m": float(np.linalg.norm(heel - ajc_lab)), "ajc_to_toe_tip_m": float(np.linalg.norm(tip - ajc_lab)),
           "ajc_to_mtp_m": float(np.linalg.norm(mtp_lab - ajc_lab)),
           "ajc_to_heel_up_m": float((ajc_lab - heel) @ UP), "ajc_height_above_toe_tip_m": float((ajc_lab - tip) @ UP),
           "ajc_height_above_mtp_m": float((ajc_lab - mtp_lab) @ UP)}
    out["toe_tip_fraction"] = out["ajc_to_toe_tip_fwd_m"] / length
    out["mtp_fraction"] = out["ajc_to_mtp_fwd_m"] / length
    return out


# ------------------------------------------------------------------------------ the OpenSim model of a subject

def _xyz(text: str) -> np.ndarray:
    return np.array([float(v) for v in text.split()])


def osim_foot_points(osim_xml: bytes, side: str) -> dict:
    """{ajc, mtp, markers} in the calcaneus frame (metres, x forward, y up, z right) from a subject's OpenSim model, with the side's subtalar angle at zero.
    The ankle centre is the talus origin's offset: the subtalar joint places the talus point P on the calcaneus point Q, so the talus point A that the ankle
    puts on the tibia lies at Q - P + A in the calcaneus frame. The offset frames of the three joints must carry no rotation. `markers` are the markers
    fixed to the calcaneus body."""
    import xml.etree.ElementTree as ET
    root = ET.fromstring(osim_xml)
    frames = {}
    for joint in root.iter("CustomJoint"):
        if joint.get("name") in (f"ankle_{side}", f"subtalar_{side}", f"mtp_{side}"):
            for fr in joint.iter("PhysicalOffsetFrame"):
                if np.abs(_xyz(fr.findtext("orientation"))).max() > 1e-9:
                    raise ValueError(f"{joint.get('name')}/{fr.get('name')}: a rotated offset frame (orientation) is not handled")
                frames[(joint.get("name"), fr.findtext("socket_parent").split("/")[-1])] = _xyz(fr.findtext("translation"))
    A = frames[(f"ankle_{side}", f"talus_{side}")]
    P, Q = frames[(f"subtalar_{side}", f"talus_{side}")], frames[(f"subtalar_{side}", f"calcn_{side}")]
    mtp = frames[(f"mtp_{side}", f"calcn_{side}")]
    markers = {m.get("name"): _xyz(m.findtext("location")) for m in root.iter("Marker") if m.findtext("socket_parent_frame").endswith(f"/calcn_{side}")}
    return {"ajc": Q - P + A, "mtp": mtp, "markers": markers}


# ------------------------------------------------------------------------------ the pelvis

def dumas_pelvic_tilt_deg(asis_r, asis_l, psis_r, psis_l):
    """Pelvic tilt per frame in the Dumas (ISB) pelvic frame, degrees, anterior positive: from marker positions (N, 3) in a lab frame with y up. The frame's
    mediolateral axis Z runs from the left to the right ASIS; its anterior axis X lies in the plane through the ASIS and the midpoint of the PSIS,
    perpendicular to Z, pointing forward. The tilt is the dip of X below the horizontal, so it is positive when the ASIS are below the PSIS
    plane's horizontal and independent of the direction the subject faces. (A full Cardan sequence differs by the small coupling with the lateral tilt;
    for a few degrees of obliquity that is under 0.1 degree.) NaN markers give NaN frames."""
    ar, al, pr, pl = (np.asarray(v, float) for v in (asis_r, asis_l, psis_r, psis_l))
    Z = ar - al
    Z = Z / np.linalg.norm(Z, axis=1, keepdims=True)
    v = 0.5 * (ar + al) - 0.5 * (pr + pl)
    X = v - np.sum(v * Z, axis=1, keepdims=True) * Z
    X = X / np.linalg.norm(X, axis=1, keepdims=True)
    return np.degrees(np.arcsin(np.clip(-X[:, 1], -1.0, 1.0)))


def trunk_marker_names(names) -> list:
    """The marker names that are neither pelvis nor lower-limb markers (trunk, head, arm), sorted. The table's `Header` column is not a marker."""
    out = []
    for n in names:
        base = re.sub(r"^[RL]_", "", n)
        if n != "Header" and not base.startswith(NON_TRUNK_PREFIXES):
            out.append(n)
    return sorted(out)


def chord_inclination_deg(p0, p1, fwd):
    """Angle in degrees of the chord from p0 to p1 (N, 3) from the upward vertical, in the plane of the vertical and `fwd`; positive when the chord leans forward."""
    v = np.asarray(p1, float) - np.asarray(p0, float)
    f = np.asarray(fwd, float)
    f = f - (f @ UP) * UP
    f = f / np.linalg.norm(f)
    return np.degrees(np.arctan2(v @ f, v @ UP))


# ------------------------------------------------------------------------------ hip extension against the stop

def extension_demand(values, stop_deg: float) -> dict:
    """Per-stride peak extensions (degrees): count and fraction strictly beyond the stop, median, 95th percentile, maximum."""
    v = np.asarray(values, float)
    beyond = int(np.sum(v > stop_deg))
    return {"n": int(len(v)), "beyond": beyond, "fraction_beyond": beyond / len(v), "median": float(np.median(v)), "p95": float(np.percentile(v, 95)), "max": float(v.max())}


def hip_stop_demand(strides, stop_deg: float) -> dict:
    """strides: [{hip_r, hip_l, list}] in degrees (the dataset's inverse kinematics). Peak extension relative to the pelvis and from the vertical, against the stop."""
    import gait_extract
    r = [gait_extract.stride_hip_extension(s["hip_r"], s["hip_l"], s["list"]) for s in strides]
    return {"stop_deg": float(stop_deg), "pelvis_relative": extension_demand([x["hip_raw"] for x in r], stop_deg),
            "vertical": extension_demand([x["thigh_world"] for x in r], stop_deg)}


def model_hip_stop_deg(model) -> float:
    """The extension stop of the loaded model's hip_fe, degrees: its single home is gait_diag.hip_extension_stop_deg."""
    import gait_diag
    return gait_diag.hip_extension_stop_deg(model)


# ------------------------------------------------------------------------------ the strides behind a maximum

def top_strides(rows, k: int) -> list:
    """The k rows with the largest `peak`, largest first, each with the 95th percentile of all rows and its own ratio to it."""
    p95 = float(np.percentile([r["peak"] for r in rows], 95))
    return [dict(r, p95=p95, ratio_to_p95=r["peak"] / p95) for r in sorted(rows, key=lambda r: -r["peak"])[:k]]


def peak_context(tau, stance: dict) -> dict:
    """Where the largest |tau| of a stride falls: the frame (the 100 unique phase points, so also the percent of the stride), how many feet are in stance there
    and, for each, the percent of its own stance (counted from its heel strike over the longest run of the flag)."""
    import foot_pitch
    tau = np.asarray(tau, float)
    k = int(np.argmax(np.abs(tau)))
    n = len(tau)
    by_foot = {}
    for foot, flag in stance.items():
        run = foot_pitch.stance_run(np.asarray(flag, bool))
        if run is None:
            continue
        start, length = run
        j = (k - start) % n
        if j < length:
            by_foot[foot] = 100.0 * j / length
    out = {"frame": k, "stride_phase_pct": 100.0 * k / n, "support": {0: "none", 1: "single", 2: "double"}[len(by_foot)], "stance_pct_by_foot": by_foot}
    if len(by_foot) == 1:
        (out["stance_foot"], out["stance_pct"]), = by_foot.items()
    return out


# ------------------------------------------------------------------------------ small readers

def stamp_fields(path):
    """{git_dirty, diff_sha256} of a stamped record, or None when the file does not exist."""
    p = Path(path)
    if not p.exists():
        return None
    d = json.loads(p.read_text(encoding="utf-8"))
    return {"git_dirty": d.get("git_dirty"), "diff_sha256": d.get("diff_sha256")}


def ansur_stats(path, columns) -> dict:
    """{column: {n, mean, sd} or None when the column is absent}: the sample standard deviation (n - 1) of the numeric entries, in the file's units."""
    with open(path, newline="", encoding="latin-1") as f:
        rd = csv.DictReader(f)
        rows = list(rd)
        have = set(rd.fieldnames or [])
    out = {}
    for c in columns:
        if c not in have:
            out[c] = None
            continue
        v = []
        for r in rows:
            try:
                v.append(float(r[c]))
            except (TypeError, ValueError):
                pass
        out[c] = {"n": len(v), "mean": float(np.mean(v)), "sd": float(np.std(v, ddof=1))}
    return out


# ------------------------------------------------------------------------------ the static trials of a subject

def _static_names(zf, kind: str) -> list:
    return sorted(n for n in zf.namelist() if re.search(rf"/static/{kind}/.*\.mat$", n))


def subject_static(subject: str, raw: Path) -> dict:
    """The subject's static trial(s) from the raw archive: per foot the geometry (`foot_geometry`), the mid-malleoli check where both malleolus markers exist,
    the pelvic tilt in the Dumas frame (mean and standard deviation over the frames), the older line-based marker tilt, the IK pelvis_list and subtalar
    angles, and the marker names. Static trials are averaged marker by marker (nan-aware) before the foot is fitted."""
    import zipfile
    import gait_diag
    import ingest_camargo as ic
    zf = zipfile.ZipFile(raw / f"{subject}.zip")
    tabs = [ic.read_table(zf.read(n)) for n in _static_names(zf, "markers")]
    names = sorted({k.rsplit("_", 1)[0] for t in tabs for k in t if k != "Header"})
    cat = lambda name: np.concatenate([np.stack([t[f"{name}_{c}"] for c in "xyz"], axis=1) for t in tabs]) / 1000.0
    mean = {n: np.nanmean(cat(n), axis=0) for n in names}
    osim = next(n for n in zf.namelist() if n.lower() == f"osimxml/{subject.lower()}.osim")
    blob = zf.read(osim)
    foot = {}
    for side in ("R", "L"):
        pts = osim_foot_points(blob, side.lower())
        g = foot_geometry(mean, pts["markers"], pts["ajc"], pts["mtp"])
        g["ankle_lat_to_ajc_m"] = float(np.linalg.norm(mean[f"{side}_Ankle_Lat"] - g["ajc_lab"]))
        # the per-subject measured fore-aft positions, behind or ahead of the heel marker along the foot's forward direction (not the model's scaled landmarks)
        ahead_of_heel = lambda p: float((p - g["heel_lab"]) @ g["fwd"])
        g["ankle_lat_ahead_of_heel_m"] = ahead_of_heel(mean[f"{side}_Ankle_Lat"])
        g["toe_markers_mid_ahead_of_heel_m"] = ahead_of_heel(0.5 * (mean[f"{side}_Toe_Lat"] + mean[f"{side}_Toe_Med"]))
        g["model_ajc_ahead_of_heel_m"] = g["ajc_to_heel_fwd_m"]
        g["model_ajc_height_lab_m"], g["ankle_lat_height_lab_m"], g["heel_height_lab_m"] = float(g["ajc_lab"][1]), float(mean[f"{side}_Ankle_Lat"][1]), float(g["heel_lab"][1])
        g["model_mtp_ahead_of_heel_m"] = ahead_of_heel(g["mtp_lab"])
        if f"{side}_Ankle_Med" in mean:
            mid = 0.5 * (mean[f"{side}_Ankle_Lat"] + mean[f"{side}_Ankle_Med"])
            g["mid_malleoli_to_model_ajc_m"] = float(np.linalg.norm(mid - g["ajc_lab"]))
            g["malleolar_breadth_m"] = float(np.linalg.norm(mean[f"{side}_Ankle_Lat"] - mean[f"{side}_Ankle_Med"]))
            g["mid_malleoli_ahead_of_heel_m"] = ahead_of_heel(mid)
            g["mid_malleoli_height_above_model_ajc_m"] = float((mid - g["ajc_lab"]) @ UP)
        foot[side] = g
    pelvis = [cat(n) for n in ("R_ASIS", "L_ASIS", "R_PSIS", "L_PSIS")]
    tilt = dumas_pelvic_tilt_deg(*pelvis)
    line = gait_diag.marker_pelvic_tilt_deg(*pelvis)
    iks = [ic.read_table(zf.read(n)) for n in _static_names(zf, "ik")]
    ik = lambda ch: float(np.mean(np.concatenate([t[ch] for t in iks])))
    return {"subject": subject, "markers": names, "foot": foot, "dumas_tilt_mean_deg": float(np.nanmean(tilt)), "dumas_tilt_sd_deg": float(np.nanstd(tilt, ddof=1)),
            "line_tilt_mean_deg": float(np.nanmean(line)), "ik_pelvis_list_deg": ik("pelvis_list"), "ik_subtalar_deg": [ik("subtalar_angle_r"), ik("subtalar_angle_l")],
            "n_static_trials": len(tabs), "n_frames": int(len(tilt))}


# ------------------------------------------------------------------------------ the commands

def _manifest():
    return json.loads((REPO / "data/camargo2021/manifest.json").read_text(encoding="utf-8"))


def _all_subjects():
    import ingest_camargo as ic
    raw = ic.raw_dir()
    return {s: subject_static(s, raw) for s in _manifest()["subjects"]}


def _stat(v):
    v = np.asarray(v, float)
    return f"{v.mean():8.4f} {v.std(ddof=1):7.4f} {v.min():8.4f} {v.max():8.4f}"


def foot_command(args):
    man = _manifest()["subjects"]
    stature = float(next(r.split(",")[1] for r in (REPO / "params/snapshot.csv").read_text().splitlines() if r.startswith("target_stature,")))
    sub = _all_subjects()
    names = sorted({n for s in sub.values() for n in s["markers"]})
    print(f"markers in the static trials (union over {len(sub)} subjects): {', '.join(names)}")
    for n in names:
        c = sum(n in s["markers"] for s in sub.values())
        if c != len(sub):
            print(f"  {n}: {c} of {len(sub)} subjects ({', '.join(s for s, v in sub.items() if n in v['markers'])})")
    print("foot-frame geometry: the model's ankle centre (OpenSim talocrural, subtalar angle 0) and MTP joint carried into the static pose by a rigid fit of the four foot markers;")
    print("distances in mm per subject (right and left feet averaged), forward = horizontal heel-to-toe-tip direction")
    cols = ["foot_length_m", "ajc_to_heel_fwd_m", "ajc_to_toe_tip_fwd_m", "ajc_to_mtp_fwd_m", "ajc_to_heel_m", "ajc_to_toe_tip_m", "ajc_to_mtp_m",
            "ajc_to_heel_up_m", "ajc_height_above_toe_tip_m", "ajc_height_above_mtp_m", "toe_tip_fraction", "mtp_fraction", "fit_rms_m", "ankle_lat_to_ajc_m"]
    per = {c: [] for c in cols}
    print(f"{'subject':8s} {'height':>6s} {'footL':>6s} {'A>heel':>6s} {'A>MTP':>6s} {'A>tip':>6s} {'tip/L':>6s} {'MTP/L':>6s} {'fit':>5s} {'R-L footL':>9s}")
    for s, v in sub.items():
        avg = lambda c: 0.5 * (v["foot"]["R"][c] + v["foot"]["L"][c])
        for c in cols:
            per[c].append(avg(c))
        print(f"{s:8s} {man[s]['height_m']:6.2f} {1000 * avg('foot_length_m'):6.0f} {1000 * avg('ajc_to_heel_fwd_m'):6.0f} {1000 * avg('ajc_to_mtp_fwd_m'):6.0f} "
              f"{1000 * avg('ajc_to_toe_tip_fwd_m'):6.0f} {avg('toe_tip_fraction'):6.3f} {avg('mtp_fraction'):6.3f} {1000 * avg('fit_rms_m'):5.1f} "
              f"{1000 * (v['foot']['R']['foot_length_m'] - v['foot']['L']['foot_length_m']):9.1f}")
    print(f"statistics over {len(sub)} subjects (mm, or a fraction): mean, SD, min, max")
    for c in cols:
        f = 1.0 if c.endswith("fraction") else 1000.0
        a = np.asarray(per[c], float) * f
        print(f"  {c:28s} {a.mean():8.3f} {a.std(ddof=1):7.3f} {a.min():8.3f} {a.max():8.3f}")
    print("measured per subject, ahead of the heel marker along the foot (mm; mean, SD, min, max over subjects, feet averaged):")
    for c, label in (("ankle_lat_ahead_of_heel_m", "lateral malleolus marker"), ("model_ajc_ahead_of_heel_m", "model ankle centre (scaled generic)"),
                     ("toe_markers_mid_ahead_of_heel_m", "midpoint of Toe_Lat and Toe_Med markers"), ("model_mtp_ahead_of_heel_m", "model MTP joint (scaled generic)"),
                     ("model_ajc_height_lab_m", "model ankle centre, height above lab y = 0"), ("ankle_lat_height_lab_m", "lateral malleolus marker, height above y = 0"),
                     ("heel_height_lab_m", "heel marker, height above y = 0")):
        a = np.array([0.5 * (v["foot"]["R"][c] + v["foot"]["L"][c]) for v in sub.values()]) * 1000
        print(f"  {label:42s} {a.mean():7.1f} {a.std(ddof=1):6.1f} {a.min():7.1f} {a.max():7.1f}")
    fl = np.array([per["foot_length_m"][i] for i in range(len(sub))])
    for c, label in (("ankle_lat_ahead_of_heel_m", "lateral malleolus marker"), ("toe_markers_mid_ahead_of_heel_m", "Toe_Lat/Toe_Med midpoint")):
        fr = np.array([0.5 * (v["foot"]["R"][c] + v["foot"]["L"][c]) for v in sub.values()]) / fl
        print(f"  {label} as a fraction of foot length from the heel: {fr.mean():.3f} (SD {fr.std(ddof=1):.3f}, {fr.min():.3f} to {fr.max():.3f}); model ankle centre {np.mean(np.array(per['ajc_to_heel_fwd_m']) / fl):.3f}")
    mm = [(s, v) for s, v in sub.items() if "mid_malleoli_to_model_ajc_m" in v["foot"]["R"]]
    for s, v in mm:
        print(f"mid-malleoli check ({s}, the only subject with both malleolus markers): malleolar breadth R {1000 * v['foot']['R']['malleolar_breadth_m']:.0f} mm, "
              f"L {1000 * v['foot']['L']['malleolar_breadth_m']:.0f} mm; mid-malleoli to the model's ankle centre R {1000 * v['foot']['R']['mid_malleoli_to_model_ajc_m']:.1f} mm, "
              f"L {1000 * v['foot']['L']['mid_malleoli_to_model_ajc_m']:.1f} mm; mid-malleoli ahead of the heel R {1000 * v['foot']['R']['mid_malleoli_ahead_of_heel_m']:.0f}, "
              f"L {1000 * v['foot']['L']['mid_malleoli_ahead_of_heel_m']:.0f} mm against the model's {1000 * v['foot']['R']['model_ajc_ahead_of_heel_m']:.0f}, {1000 * v['foot']['L']['model_ajc_ahead_of_heel_m']:.0f}; "
              f"height of mid-malleoli above the model centre R {1000 * v['foot']['R']['mid_malleoli_height_above_model_ajc_m']:+.0f}, L {1000 * v['foot']['L']['mid_malleoli_height_above_model_ajc_m']:+.0f} mm")
    print(f"IK subtalar angle in the static trial (deg, right, left): range {min(min(s['ik_subtalar_deg']) for s in sub.values()):.1f} to {max(max(s['ik_subtalar_deg']) for s in sub.values()):.1f}"
          " (the ankle centre assumes 0; 0.07 m x angle bounds the error)")
    print(f"scaling to Freyja: each subject's lengths x (Freyja stature {stature:.2f} m / the subject's stature), then the mean and SD over subjects")
    for c in ("ajc_to_heel_fwd_m", "ajc_to_mtp_fwd_m", "ajc_to_toe_tip_fwd_m", "foot_length_m"):
        sc = np.array([x * stature / man[s]["height_m"] for x, s in zip(per[c], sub)]) * 1000
        print(f"  {c:24s} at Freyja's scale: {sc.mean():6.1f} mm (SD {sc.std(ddof=1):4.1f}, range {sc.min():.1f} to {sc.max():.1f}); unscaled mean {1000 * np.mean(per[c]):.1f}")
    sc = np.array([x * stature / man[s]["height_m"] for x, s in zip(per["foot_length_m"], sub)])
    print(f"  (the dataset's mean stature is {np.mean([man[s]['height_m'] for s in sub]):.3f} m; the sheet's foot_length is 165 mm and the foot box reaches 165 mm ahead of the ankle)")
    tr = [n for n in names if n in trunk_marker_names(names)]
    print("D7 trunk and head markers: " + (", ".join(tr) if tr else "none in the static trials (pelvis and lower limb only), so no chord inclination can be computed"))


def tilt_command(args):
    import leanpose
    import gait
    sub = _all_subjects()
    man = _manifest()["subjects"]
    c = gait._ctx(str(gait.simrun.MODEL_FILE))
    stand = leanpose.solve_lean(c.model, 0.0, gait.STANDING_FEET)
    print("static pelvic tilt, degrees, anterior positive: Dumas frame (ASIS plane, anterior axis through the PSIS midpoint); mean and SD over the static trial's frames")
    print(f"{'subject':8s} {'frames':>6s} {'Dumas':>7s} {'SD':>5s} {'line':>6s} {'-list':>6s} {'Dumas+list':>10s} {'manifest pitch':>14s}")
    d, ln, lst = [], [], []
    for s, v in sub.items():
        d.append(v["dumas_tilt_mean_deg"])
        ln.append(v["line_tilt_mean_deg"])
        lst.append(v["ik_pelvis_list_deg"])
        print(f"{s:8s} {v['n_frames']:6d} {v['dumas_tilt_mean_deg']:7.2f} {v['dumas_tilt_sd_deg']:5.2f} {v['line_tilt_mean_deg']:6.2f} {-v['ik_pelvis_list_deg']:6.2f} "
              f"{v['dumas_tilt_mean_deg'] + v['ik_pelvis_list_deg']:10.2f} {man[s]['static_pelvis_pitch_deg']:14.2f}")
    d, ln, lst = np.array(d), np.array(ln), np.array(lst)
    print(f"Dumas tilt over subjects: mean {d.mean():.2f}, SD {d.std(ddof=1):.2f}, range {d.min():.2f} to {d.max():.2f}; mean within-trial SD {np.mean([v['dumas_tilt_sd_deg'] for v in sub.values()]):.2f}")
    print(f"line tilt (gait_diag.marker_pelvic_tilt_deg): mean {ln.mean():.2f}, SD {ln.std(ddof=1):.2f}; Dumas minus line mean {np.mean(d - ln):+.2f} (SD {np.std(d - ln, ddof=1):.2f})")
    print(f"IK pelvis_list, static: mean {lst.mean():.2f}, SD {lst.std(ddof=1):.2f} (anterior pitch = minus pelvis_list); Dumas minus (-pelvis_list): mean {np.mean(d + lst):+.2f}, SD {np.std(d + lst, ddof=1):.2f}, "
          f"correlation {np.corrcoef(d, -lst)[0, 1]:+.2f}")
    print(f"model: stand_static root pitch {np.degrees(stand.root_pitch_rad):+.3f} deg (forward lean positive), ankle {np.degrees(stand.lean_rad):+.3f} deg")


def hipstop_command(args):
    import mujoco
    import gait
    spec = gait.load_spec("walk_treadmill")
    processed = REPO / spec["dataset"]["processed"]
    nm = gait.ic.IK_CHANNELS
    model = mujoco.MjModel.from_xml_path(str(gait.simrun.MODEL_FILE))
    stop = model_hip_stop_deg(model)
    print(f"hip_fe_right extension stop read from {gait.simrun.MODEL_FILE.name}: {stop:.2f} deg (the dataset's inverse kinematics, no retargeting; peak per stride over both limbs)")
    for sp in args.speeds:
        strides = []
        for s in _manifest()["subjects"]:
            ik = gait._subject_arrays(processed, s)[f"{sp}_ik"]
            for i in range(len(ik)):
                ch = lambda n: ik[i][:, nm.index(n)]
                strides.append({"hip_r": ch("hip_flexion_r"), "hip_l": ch("hip_flexion_l"), "list": ch("pelvis_list")})
        r = hip_stop_demand(strides, stop)
        print(f"=== {sp} m/s, {len(strides)} subject-strides ===")
        for key, label in (("pelvis_relative", "relative to the pelvis"), ("vertical", "relative to the vertical")):
            x = r[key]
            print(f"  {label:25s} beyond {x['beyond']:4d} of {x['n']} = {100 * x['fraction_beyond']:5.1f}%   median {x['median']:5.1f}  p95 {x['p95']:5.1f}  max {x['max']:5.1f} deg")


def _lat_task(task: dict) -> dict:
    """One subject-stride in the rigid trunk mode: the lumbosacral lateral joint's torque row of qfrc_inverse, as `gait_extract._lsj_task` computes it, with its peak and where it falls."""
    import dynamics
    import gait
    import gait_extract
    import gaitloads
    import retarget
    c = gait._ctx(task["model_path"])
    z = gait._subject_arrays(task["processed"], task["subject"])
    sp, i = task["speed"], task["index"]
    sub = task["subject_info"]
    hip = sub.get("hip_in_pelvis_os_m")
    cyc = retarget.Cycle(c.model, c.mapping, c.stand, z[f"{sp}_ik"][i], float(z[f"{sp}_duration_s"][i]), retarget.leg_length_ratio(c.model, sub["height_m"]),
                         cutoff_hz=retarget.CUTOFF_HZ, root_rule="pelvis_dataset", hip_in_pelvis_os=hip, root_ref="hip_midpoint" if hip is not None else "pelvis_origin",
                         pitch_mean="measured", **gait_extract._variant_kwargs("rigid", sp))
    q, qd, qdd = cyc.grid()
    nf = gait.N_FRAMES
    dof = c.hinge["lsj_lat"][1]
    tau = np.array([dynamics.inverse_frame(c.model, q[k], qd[k], qdd[k])[dof] for k in range(nf)])
    fp = z[f"{sp}_fp"][i]
    stance = {f: fp[j, :nf, 6] >= gaitloads.STANCE_FLAG for j, f in enumerate(gait.FEET)}
    ctx = peak_context(tau, stance)
    return {"subject": task["subject"], "speed": sp, "index": i, "peak": float(np.abs(tau).max()), "tau_at_peak": float(tau[ctx["frame"]]), **ctx}


def lateral_command(args):
    import gait
    import gait_extract
    from concurrent.futures import ProcessPoolExecutor
    man = _manifest()
    ext = json.loads((REPO / "sim/benchmarks/gait_extract.json").read_text(encoding="utf-8"))["lumbosacral"]
    tasks = []
    for sp in args.speeds:
        for s, info in man["subjects"].items():
            for i in range(info["strides"][sp]):
                tasks.append({"model_path": str(gait.simrun.MODEL_FILE), "processed": str(REPO / "data/camargo2021/processed"), "subject": s, "speed": sp, "index": i, "subject_info": info})
    with ProcessPoolExecutor(max_workers=args.workers) as ex:
        rows = list(ex.map(_lat_task, tasks, chunksize=8))
    for sp in args.speeds:
        R = [r for r in rows if r["speed"] == sp]
        top = top_strides(R, args.top)
        e = ext[sp]["lsj_lat"]["rigid"]["peak_torque_nm"]
        print(f"=== {sp} m/s, lumbosacral lateral joint, rigid trunk, {len(R)} subject-strides: peak |torque| p95 {top[0]['p95']:.2f}, max {max(r['peak'] for r in R):.2f} N m "
              f"(tracked extract: p95 {e['p95']:.2f}, max {e['max']:.2f}) ===")
        print("subject  stride  peak N m  ratio to p95  stride phase %  support   stance foot: % of its stance")
        for t in top:
            where = ", ".join(f"{f} {p:5.1f}%" for f, p in t["stance_pct_by_foot"].items()) or "no foot in stance"
            print(f"  {t['subject']:6s} {t['index']:5d} {t['peak']:9.2f} {t['ratio_to_p95']:11.2f} {t['stride_phase_pct']:14.0f}  {t['support']:7s}  {where}")
        n_above = sum(r["peak"] > top[0]["p95"] for r in R)
        by_sub = {}
        for r in R:
            if r["peak"] > top[0]["p95"]:
                by_sub[r["subject"]] = by_sub.get(r["subject"], 0) + 1
        print(f"  strides above the p95: {n_above}, by subject: {dict(sorted(by_sub.items()))}")
        ph = np.array([r["stride_phase_pct"] for r in R])
        print(f"  all strides, phase of the peak: median {np.median(ph):.0f}%, 5th to 95th percentile {np.percentile(ph, 5):.0f}% to {np.percentile(ph, 95):.0f}%; single support at the peak {100 * np.mean([r['support'] == 'single' for r in R]):.0f}%")


def stamp_command(args):
    import subprocess
    head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=REPO, capture_output=True, text=True).stdout.strip()
    for label, rel in (("tracked extract", "sim/benchmarks/gait_extract.json"), ("gait record 1424", "sim/gait/20261019-1424-walk_treadmill/gait.json")):
        p = REPO / rel
        s = stamp_fields(p)
        d = json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}
        print(f"{label:17s} {rel}: " + ("absent" if s is None else f"git_dirty {s['git_dirty']}, diff_sha256 {s['diff_sha256']}, git_commit {d.get('git_commit')}"))
    print(f"current HEAD {head}")


def ansur_command(args):
    path = REPO / "data/ansur2/raw/ANSUR_II_FEMALE_Public.csv"
    if not path.exists():
        print(f"{path.relative_to(REPO)} is absent")
        return
    cols = ["stature", "footlength", "balloffootlength", "lateralmalleolusheight"]
    st = ansur_stats(path, cols)
    print(f"{path.relative_to(REPO)}: values in the file's units (mm)")
    for c in cols:
        x = st[c]
        print(f"  {c:24s} " + ("column absent" if x is None else f"n {x['n']}, mean {x['mean']:.1f}, SD {x['sd']:.1f}"))
    hb = REPO / "data/ansur2/raw/measurers-handbook.pdf"
    print(f"measurer's handbook: {'present at ' + str(hb.relative_to(REPO)) if hb.exists() else 'absent'}")


def main(argv=None):
    import argparse
    ap = argparse.ArgumentParser(prog="snapshot_diag")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("foot")
    sub.add_parser("tilt")
    h = sub.add_parser("hipstop")
    h.add_argument("--speeds", nargs="+", default=["0.5", "1.4", "1.6"])
    la = sub.add_parser("lateral")
    la.add_argument("--speeds", nargs="+", default=["0.5", "1.4", "1.6"])
    la.add_argument("--top", type=int, default=8)
    la.add_argument("--workers", type=int, default=4)
    sub.add_parser("stamp")
    sub.add_parser("ansur")
    args = ap.parse_args(argv)
    {"foot": foot_command, "tilt": tilt_command, "hipstop": hipstop_command, "lateral": lateral_command, "stamp": stamp_command, "ansur": ansur_command}[args.cmd](args)


if __name__ == "__main__":
    main()
