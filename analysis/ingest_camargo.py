"""
Stage 2 T1: ingest the Camargo et al. 2021 treadmill walking trials (the speeds in the spec: 1.4 and 1.6 m/s, and 0.5 m/s since Stage 2f) into per-stride, phase-normalised
arrays. Reads trials on demand from the per-subject zip archives (random access), never the whole dataset, and never writes
into the raw folder. Processed arrays go to data/camargo2021/processed/ (gitignored); the manifest is tracked.

    python analysis/ingest_camargo.py            # all subjects in data/camargo2021/ingest_spec.yaml

Stride: right heel strike to the next right heel strike, events from the vertical force of the instrumented treadmill's
right and left plates. Arrays are 101 phase points (0 and 100% are consecutive heel strikes), linear interpolation from the
dataset's 200 Hz IK/ID and 1 kHz force plates. Nothing is filtered here and nothing is clipped; strides that fail an
acceptance test are counted by reason in the manifest.

The files are MATLAB v5 MCOS tables, which scipy does not decode; `read_table` parses the table object's subsystem with
scipy's own stream reader, so no new dependency (h5py is not needed: the files are not v7.3).
"""
from __future__ import annotations

import hashlib
import io
import json
import os
import re
import sys
import zipfile
from pathlib import Path

import numpy as np
import scipy.io as sio
import yaml
from scipy.io.matlab._mio5 import MatFile5Reader

REPO = Path(__file__).resolve().parents[1]
SCRIPT_PATH = "analysis/ingest_camargo.py"
VERSION = "1"
G = 9.81  # m/s2, only to express force in body weights in checks

IK_CHANNELS = ["pelvis_tilt", "pelvis_list", "pelvis_rotation", "pelvis_tx", "pelvis_ty", "pelvis_tz",
               "hip_flexion_r", "hip_flexion_l", "hip_adduction_r", "hip_adduction_l", "hip_rotation_r", "hip_rotation_l",
               "knee_angle_r", "knee_angle_l", "ankle_angle_r", "ankle_angle_l", "subtalar_angle_r", "subtalar_angle_l"]
ID_CHANNELS = ([f"{j}_{s}_moment" for j in ("hip_flexion", "hip_adduction", "hip_rotation", "knee_angle", "ankle_angle", "subtalar_angle")
                for s in ("r", "l")]
               + ["pelvis_tilt_moment", "pelvis_list_moment", "pelvis_rotation_moment",
                  "pelvis_tx_force", "pelvis_ty_force", "pelvis_tz_force"])
FOOT_MARKERS = ("R_Heel", "R_Toe_Tip", "L_Heel", "L_Toe_Tip")  # mm in the file; stored per stride as (foot R/L, heel/toe, xyz) metres
FP_CHANNELS = ["Fx", "Fy", "Fz", "CoPx", "CoPy", "CoPz", "stance"]
FEET = ("R", "L")
SENSORS = ("conditions", "ik", "id", "fp", "markers", "imu")


# ------------------------------------------------------------------ locations and tables

def raw_dir(config_path: Path | None = None) -> Path:
    """The raw folder: $CAMARGO_RAW_DIR, else the `camargo_raw_dir` key of sim/local_config.json (read, never written),
    else data/camargo2021/raw (gitignored)."""
    env = os.environ.get("CAMARGO_RAW_DIR")
    if env:
        return Path(env)
    cfg = Path(config_path) if config_path else REPO / "sim" / "local_config.json"
    if cfg.exists():
        try:
            key = json.loads(cfg.read_text()).get("camargo_raw_dir")
        except (OSError, ValueError):
            key = None
        if key:
            return Path(key)
    return REPO / "data" / "camargo2021" / "raw"


def read_table(blob: bytes) -> dict:
    """Columns of the single MATLAB `table` stored in a Camargo .mat file, as {name: 1-D float array}."""
    m = sio.loadmat(io.BytesIO(blob))
    fw = bytes(m["__function_workspace__"][0])
    # The subsystem is a bare stream of data elements; give it a v5 header so the reader accepts it.
    stream = b"MATLAB 5.0 MAT-file".ljust(116, b" ") + b"\0" * 8 + b"\x00\x01IM" + fw[8:]
    rd = MatFile5Reader(io.BytesIO(stream), struct_as_record=False, squeeze_me=False)
    rd.mat_stream.seek(128)
    rd.initialize_read()
    header, _ = rd.read_var_header()
    obj = rd.read_var_array(header)
    cells = obj[0, 0].MCOS[0]["arr"]
    columns, names = cells[2, 0].ravel(), cells[7, 0].ravel()
    out = {}
    for name, col in zip(names, columns):
        out[str(np.asarray(name).ravel()[0])] = np.asarray(col).ravel()
    return out


def hip_centre_in_pelvis(zf, subject: str) -> list:
    """Hip joint centre in the subject's OpenSim pelvis frame (x forward, y up, z right), metres: [x, y, half the hip separation].
    From the right and left hip joints' pelvis offset frames in osimxml/<subject>.osim; the left must mirror the right."""
    import xml.etree.ElementTree as ET
    name = next(n for n in zf.namelist() if n.lower() == f"osimxml/{subject.lower()}.osim")  # AB07's file is ab07.osim
    root = ET.fromstring(zf.read(name))
    found = {}
    for joint in root.iter("CustomJoint"):
        if joint.get("name") in ("hip_r", "hip_l"):
            for frame in joint.iter("PhysicalOffsetFrame"):
                if frame.findtext("socket_parent") == "/bodyset/pelvis":
                    found[joint.get("name")] = [float(v) for v in frame.findtext("translation").split()]
    r, l = found["hip_r"], found["hip_l"]
    if abs(r[0] - l[0]) > 1e-9 or abs(r[1] - l[1]) > 1e-9 or abs(r[2] + l[2]) > 1e-9:
        raise ValueError(f"{subject}: the left hip centre does not mirror the right")
    return [r[0], r[1], abs(r[2])]


def subject_info(path: Path) -> dict:
    t = read_table(path.read_bytes())
    first = lambda v: str(np.asarray(v).ravel()[0])
    return {first(s): {"age": float(a), "sex": first(g), "height_m": float(h), "mass_kg": float(w)}
            for s, a, g, h, w in zip(t["Subject"], t["Age"], t["Gender"], t["Height"], t["Weight"])}


# ------------------------------------------------------------------ signal helpers (pure)

def contacts(t, f, threshold_n: float, min_duration_s: float):
    """[(on, off)] sample indices of the stance phases in force trace f: on is the first sample above the threshold, off the
    first sample at or below it afterwards. Runs shorter than min_duration_s (cross-over steps) and runs cut by the ends of
    the trace are dropped."""
    above = np.asarray(f) > threshold_n
    d = np.diff(above.astype(np.int8))
    ons, offs = np.where(d == 1)[0] + 1, np.where(d == -1)[0] + 1
    out = []
    for a in ons:
        b = offs[offs > a]
        if b.size and t[b[0]] - t[a] >= min_duration_s:
            out.append((int(a), int(b[0])))
    return out


def phase_normalise(t, x, t0: float, t1: float, n: int = 101):
    """x(t) at n equally spaced times from t0 to t1 inclusive, linear interpolation."""
    return np.interp(np.linspace(t0, t1, n), t, x)


def wrap_gap(x):
    """|x(end) - x(start)| along axis 0 (the phase axis): how far a stride is from closing on itself."""
    x = np.asarray(x)
    return np.abs(x[-1] - x[0])


def relative_half_width(lo: float, hi: float) -> float:
    """(hi - lo) / (hi + lo): the half-width of [lo, hi] as a fraction of its midpoint."""
    return (hi - lo) / (hi + lo)


def range_around(median: float, lo: float, hi: float) -> tuple:
    """[lo, hi] moved to be centred on `median` with the same relative half-width."""
    w = relative_half_width(lo, hi)
    return median * (1 - w), median * (1 + w)


def stride_range(spec: dict, speed) -> tuple:
    """The plausible heel-strike-to-heel-strike duration (lo, hi) in seconds at a target speed: `stride_s` is keyed by speed."""
    lo, hi = spec["stride_s"][speed]
    return float(lo), float(hi)


def steady_segments(t, speed, target: float, tol: float, ptp: float, min_s: float = 1.0):
    """[(t_start, t_end)] plateaus of the belt speed: maximal runs whose speed varies by at most `ptp`, with mean within
    `tol` of `target`, lasting at least min_s."""
    t, speed = np.asarray(t), np.asarray(speed)
    cand = np.abs(speed - target) < tol
    out = []
    idx = np.flatnonzero(cand)
    if idx.size == 0:
        return out
    chunks = np.split(idx, np.where(np.diff(idx) > 1)[0] + 1)
    for chunk in chunks:
        i, end = chunk[0], chunk[-1] + 1
        while i < end:
            seg = speed[i:end]
            lo, hi = np.minimum.accumulate(seg), np.maximum.accumulate(seg)
            bad = np.flatnonzero(hi - lo > ptp)
            j = i + (bad[0] if bad.size else end - i)
            if t[j - 1] - t[i] >= min_s and abs(speed[i:j].mean() - target) < tol:
                out.append((float(t[i]), float(t[j - 1])))
            i = j
    return out


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


# ------------------------------------------------------------------ one subject

def _find(names, subject_zip_names, sensor, trial):
    pat = re.compile(rf"(^|/)treadmill/{sensor}/{trial}\.mat$")
    hits = [n for n in subject_zip_names if pat.search(n)]
    if len(hits) != 1:
        raise FileNotFoundError(f"{sensor}/{trial}: {len(hits)} matches")
    return hits[0]


def _spec_hash(spec: dict) -> str:
    return hashlib.sha256(json.dumps(spec, sort_keys=True, default=str).encode()).hexdigest()


def ingest_subject(raw: Path, subject: str, spec: dict) -> dict:
    """Strides of one subject at each target speed: {'strides': {speed: {...arrays...}}, 'rejects': {...}, 'files': {...}}."""
    info = subject_info(REPO / "data" / "camargo2021" / "SubjectInfo.mat")[subject]
    zf = zipfile.ZipFile(raw / f"{subject}.zip")
    names = zf.namelist()
    trials = sorted({Path(n).stem for n in names if re.search(r"/treadmill/conditions/.*\.mat$", n)})
    thr, min_c = spec["contact_force_n"], spec["min_contact_s"]
    n_ph = spec["n_phase"]
    acc = {s: {k: [] for k in ("ik", "id", "fp", "foot_markers", "trunk_imu", "t0", "duration_s", "toe_off_phase", "contra_hs_phase", "contra_to_phase", "trial")}
           for s in spec["speeds_mps"]}
    rejects = {s: {} for s in spec["speeds_mps"]}
    files = {}
    # The subject's standing pelvis roll and sagittal pitch from the static trial(s). In this lab the dataset's `pelvis_tilt` is the
    # ROLL (a rotation about the walking axis) and `pelvis_list` the sagittal PITCH; pitch is reported anterior positive, which is
    # minus pelvis_list (see sim/scenarios/gait/camargo_mapping.yaml).
    static_roll, static_pitch = [], []
    for n in sorted(x for x in names if re.search(r"/static/ik/.*\.mat$", x)):
        blob = zf.read(n)
        files[f"{subject}/{Path(n).stem}/ik"] = hashlib.sha256(blob).hexdigest()
        tbl = read_table(blob)
        static_roll.append(float(np.mean(tbl["pelvis_tilt"])))
        static_pitch.append(-float(np.mean(tbl["pelvis_list"])))
    static_roll = float(np.mean(static_roll)) if static_roll else None
    static_pitch = float(np.mean(static_pitch)) if static_pitch else None
    # The same standing pelvis in the Dumas (ISB) frame, from the ASIS and PSIS markers of the static trial(s): the model's pelvis frame
    # (decisions/0004-hip-stop-pelvis-pose.md). Its difference from the IK pitch above is the frame offset the retargeting can apply.
    static_dumas = []
    for n in sorted(x for x in names if re.search(r"/static/markers/.*\.mat$", x)):
        blob = zf.read(n)
        files[f"{subject}/{Path(n).stem}/markers"] = hashlib.sha256(blob).hexdigest()
        tbl = read_table(blob)
        static_dumas.append(dumas_pelvic_tilt_deg(*(np.stack([tbl[f"{m}_{c}"] for c in "xyz"], axis=1) / 1000.0
                                                    for m in ("R_ASIS", "L_ASIS", "R_PSIS", "L_PSIS"))))
    static_dumas_tilt = float(np.nanmean(np.concatenate(static_dumas))) if static_dumas else None
    hip_in_pelvis = hip_centre_in_pelvis(zf, subject)

    def reject(s, why):
        rejects[s][why] = rejects[s].get(why, 0) + 1

    for trial in trials:
        cond_name = _find(names, names, "conditions", trial)
        cblob = zf.read(cond_name)
        cond = read_table(cblob)
        plateaus = {s: steady_segments(cond["Header"], cond["Speed"], s, spec["speed_tol_mps"], spec["speed_ptp_mps"], min_s=10.0)
                    for s in spec["speeds_mps"]}
        if not any(plateaus.values()):
            continue
        blobs = {"conditions": cblob}
        tables = {"conditions": cond}
        for sensor in ("ik", "id", "fp", "markers", "imu"):
            blobs[sensor] = zf.read(_find(names, names, sensor, trial))
            tables[sensor] = read_table(blobs[sensor])
        for sensor, b in blobs.items():
            files[f"{subject}/{trial}/{sensor}"] = hashlib.sha256(b).hexdigest()
        fp, ik, idt, mk, imu = tables["fp"], tables["ik"], tables["id"], tables["markers"], tables["imu"]
        tf = fp["Header"]
        con = {"R": contacts(tf, fp["Treadmill_R_vy"], thr, min_c), "L": contacts(tf, fp["Treadmill_L_vy"], thr, min_c)}
        speed_at = np.interp(tf, cond["Header"], cond["Speed"])
        for s, plats in plateaus.items():
            for p0, p1 in plats:
                for (a, off), (b, _) in zip(con["R"][:-1], con["R"][1:]):
                    t0, t1, to = tf[a], tf[b], tf[off]
                    if not (p0 + spec["settle_s"] <= t0 and t1 <= p1):
                        continue  # outside this plateau (counted once per plateau where it applies, so only in-range strides get reasons)
                    T = t1 - t0
                    if not stride_range(spec, s)[0] <= T <= stride_range(spec, s)[1]:
                        reject(s, "duration"); continue
                    if np.ptp(speed_at[a:b + 1]) > spec["speed_ptp_mps"]:
                        reject(s, "speed_not_steady"); continue
                    to_ph = (to - t0) / T
                    if not spec["toe_off_phase"][0] <= to_ph <= spec["toe_off_phase"][1]:
                        reject(s, "toe_off_phase"); continue
                    lon = [(i, o) for i, (x, o) in enumerate(con["L"]) if t0 < tf[x] < t1]
                    if len(lon) != 1:
                        reject(s, "contra_heel_strike_count"); continue
                    li = lon[0][0]
                    hs_ph = (tf[con["L"][li][0]] - t0) / T
                    if not spec["contra_heel_strike_phase"][0] <= hs_ph <= spec["contra_heel_strike_phase"][1]:
                        reject(s, "contra_heel_strike_phase"); continue
                    if li == 0:
                        reject(s, "contra_toe_off_missing"); continue
                    lto_ph = (tf[con["L"][li - 1][1]] - t0) / T
                    if not spec["contra_toe_off_phase"][0] <= lto_ph <= spec["contra_toe_off_phase"][1]:
                        reject(s, "contra_toe_off_phase"); continue
                    ikv = np.stack([phase_normalise(ik["Header"], ik[c], t0, t1, n_ph) for c in IK_CHANNELS], axis=1)
                    idv = np.stack([phase_normalise(idt["Header"], idt[c], t0, t1, n_ph) for c in ID_CHANNELS], axis=1)
                    if np.isnan(ikv).any() or np.isnan(idv).any():
                        reject(s, "nan"); continue
                    fpv = np.empty((2, n_ph, len(FP_CHANNELS)))
                    for k, foot in enumerate(FEET):
                        cols = [phase_normalise(tf, fp[f"Treadmill_{foot}_{c}"], t0, t1, n_ph)
                                for c in ("vx", "vy", "vz", "px", "py", "pz")]
                        fpv[k, :, :6] = np.stack(cols, axis=1)
                        stance = fpv[k, :, 1] > thr
                        fpv[k, :, 6] = stance
                        fpv[k, ~stance, 3:6] = np.nan  # the CoP of an unloaded plate is not defined
                    fmv = np.empty((n_ph, 2, 2, 3))
                    for fi, foot in enumerate(("R", "L")):
                        for mi, mname in enumerate(("Heel", "Toe_Tip")):
                            for ci, comp in enumerate("xyz"):
                                fmv[:, fi, mi, ci] = phase_normalise(mk["Header"], mk[f"{foot}_{mname}_{comp}"], t0, t1, n_ph) / 1000.0
                    if np.isnan(fmv).any():
                        reject(s, "nan_markers"); continue
                    imv = np.stack([phase_normalise(imu["Header"], imu[f"trunk_{k}_{c}"], t0, t1, n_ph) for k in ("Accel", "Gyro") for c in "XYZ"], axis=1)
                    if np.isnan(imv).any():
                        reject(s, "nan_imu"); continue
                    acc[s]["ik"].append(ikv); acc[s]["id"].append(idv); acc[s]["fp"].append(fpv); acc[s]["foot_markers"].append(fmv); acc[s]["trunk_imu"].append(imv)
                    acc[s]["t0"].append(t0); acc[s]["duration_s"].append(T); acc[s]["toe_off_phase"].append(to_ph)
                    acc[s]["contra_hs_phase"].append(hs_ph); acc[s]["contra_to_phase"].append(lto_ph)
                    acc[s]["trial"].append(int(re.search(r"treadmill_(\d+)_", trial).group(1)))
    strides = {}
    for s, d in acc.items():
        n = len(d["t0"])
        strides[s] = {"n": n,
                      "ik": np.array(d["ik"]).reshape(n, n_ph, len(IK_CHANNELS)),
                      "id": np.array(d["id"]).reshape(n, n_ph, len(ID_CHANNELS)),
                      "fp": np.array(d["fp"]).reshape(n, 2, n_ph, len(FP_CHANNELS)),
                      "foot_markers": np.array(d["foot_markers"]).reshape(n, n_ph, 2, 2, 3),
                      "trunk_imu": np.array(d["trunk_imu"]).reshape(n, n_ph, 6),
                      **{k: np.array(d[k]) for k in ("t0", "duration_s", "toe_off_phase", "contra_hs_phase", "contra_to_phase", "trial")}}
    return {"subject": subject, "mass_kg": info["mass_kg"], "height_m": info["height_m"], "sex": info["sex"], "age": info["age"],
            "strides": strides, "rejects": rejects, "files": files,
            "static_pelvis_roll_deg": static_roll, "static_pelvis_pitch_deg": static_pitch, "static_dumas_tilt_deg": static_dumas_tilt,
            "hip_in_pelvis_os_m": hip_in_pelvis}


def model_angles(strides: dict, mapping: dict) -> dict:
    """Right-limb angles in the model convention (see gaitfeatures) for the strides of one subject and speed."""
    pick = lambda joint: mapping["joints"][joint]["sign"] * strides["ik"][:, :, IK_CHANNELS.index(mapping["joints"][joint]["dataset"])]
    return {"hip_fe": pick("hip_fe_right"), "knee": pick("knee_right"), "ankle": pick("ankle_pdflex_right"),
            "hip_aa": pick("hip_aa_right"), "toe_off_phase": strides["toe_off_phase"]}


# ------------------------------------------------------------------ driver

def main(argv=None) -> int:
    spec_path = REPO / "data" / "camargo2021" / "ingest_spec.yaml"
    spec = yaml.safe_load(spec_path.read_text())
    raw = raw_dir()
    out_dir = REPO / "data" / "camargo2021" / "processed"
    out_dir.mkdir(parents=True, exist_ok=True)
    manifest = {"schema": "camargo-manifest/1", "generated_by": SCRIPT_PATH,
                "inputs": ["data/camargo2021/ingest_spec.yaml", "data/camargo2021/SubjectInfo.mat", "raw/<subject>.zip trials listed in files_sha256"],
                "script": SCRIPT_PATH, "script_version": VERSION,
                "dataset": spec["dataset"], "spec_sha256": _spec_hash(spec), "subjects": {}, "files_sha256": {}}
    manifest["dataset"]["retrieved"] = str(spec["dataset"]["retrieved"])
    for subject in spec["subjects"]:
        res = ingest_subject(raw, subject, spec)
        arrays = {}
        for s, d in res["strides"].items():
            for k, v in d.items():
                if k != "n":
                    arrays[f"{s}_{k}"] = v
        arrays["hip_in_pelvis_os_m"] = np.array(res["hip_in_pelvis_os_m"])
        for key in ("static_pelvis_roll_deg", "static_pelvis_pitch_deg", "static_dumas_tilt_deg"):
            arrays[key] = np.array(np.nan if res[key] is None else res[key])
        np.savez(out_dir / f"{subject}.npz", **arrays)
        manifest["subjects"][subject] = {
            "mass_kg": res["mass_kg"], "height_m": res["height_m"], "sex": res["sex"], "age": res["age"],
            "static_pelvis_roll_deg": res["static_pelvis_roll_deg"], "static_pelvis_pitch_deg": res["static_pelvis_pitch_deg"],
            "static_dumas_tilt_deg": res["static_dumas_tilt_deg"],
            "walking_pelvis_roll_deg": {str(s): float(d["ik"][:, :, IK_CHANNELS.index("pelvis_tilt")].mean()) for s, d in res["strides"].items()},
            "walking_pelvis_pitch_deg": {str(s): -float(d["ik"][:, :, IK_CHANNELS.index("pelvis_list")].mean()) for s, d in res["strides"].items()},
            "hip_in_pelvis_os_m": res["hip_in_pelvis_os_m"],
            "strides": {str(s): d["n"] for s, d in res["strides"].items()},
            "rejected": {str(s): res["rejects"][s] for s in res["rejects"]}}
        manifest["files_sha256"].update(res["files"])
        print(subject, {s: d["n"] for s, d in res["strides"].items()}, file=sys.stderr)
    with open(REPO / "data" / "camargo2021" / "manifest.json", "w", encoding="utf-8", newline="\n") as f:  # LF on every platform: the bytes are hashed into gait records
        f.write(json.dumps(manifest, indent=1, sort_keys=True) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
