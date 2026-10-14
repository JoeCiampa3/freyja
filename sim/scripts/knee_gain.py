"""
Stage 2d T4 and T5 (report only): where does A_filtered's knee excess come from, and what is the knee's moment, angle and speed envelope? The
diagnostics behind docs/memos/memo11-stage2d-diagnosis.md.

    python sim/scripts/gait_diag.py knee-gain [--part t4 t5] [--speeds 1.4 1.6] [--workers 5]

Nothing here changes the model, the sheet, the mapping, the retargeting, a default or the band, and nothing is written to the repo. The per-stride
physics is `ankle_gain.stride_terms` (A_filtered exactly as `gait.run_stride` does it, each joint's torque split into its terms); the dataset's side is
`ankle_gain._dataset_side`, whose anchor for the knee is the knee joint centre built here from the dataset's own kinematics: the hip joint centre of
that function plus the subject's OpenSim knee translation (a spline of the knee angle in the femur frame, with its multiplier) swung by the thigh's
flexion from the vertical (hip flexion plus pelvis_list, the T1 rule). It is planar: hip adduction and the pelvis's roll and yaw are not applied, which
moves the sagittal position by a few millimetres; the dataset's own closure (its plate force through that geometry against its inverse-dynamics knee
moment) is the check printed beside every result.

Signs: the knee torque is about the model's hinge, positive in the direction of increasing flexion (the actuator or muscle torque, as the dataset's
inverse-dynamics moment with its knee sign flipped), so loading response is a negative (extension) moment and the late-stance and swing moments are
positive (flexion). The dataset-direct row is the dataset's own moment per kg of the subject times Freyja's mass times the stride's leg-length ratio
(force by the mass ratio, lever by the leg ratio); angles and speeds are the retargeted ones, which are the dataset's own at the stride's own duration,
so the two rows share them.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import gait  # noqa: E402

REPO = gait.REPO

BIN_DEG = 5.0  # the brief's width of a knee-flexion bin
P95_LO, P95_HI = 92.5, 97.5  # "the 95th-percentile strides": the stride-limbs whose peak lies between these percentiles of the peaks (a 5% band around the 95th)


# ------------------------------------------------------------------------------ pure helpers

def _spline(xs, ys):
    from scipy.interpolate import CubicSpline
    xs, ys = np.asarray(xs, float), np.asarray(ys, float)
    cs = CubicSpline(xs, ys, bc_type="natural")
    lo, hi = float(xs.min()), float(xs.max())
    return lambda q: float(cs(min(max(float(q), lo), hi)))  # outside its range the end value is held, not extrapolated


def knee_translation_fn(osim_xml: bytes, side: str):
    """q (knee angle, rad, OpenSim sign: negative flexion) -> (tx, ty) of the knee joint centre in the femur frame (x anterior, y up), metres, from the
    subject's OpenSim model: the SimmSpline of `translation1` and `translation2` of `knee_<side>` times its MultiplierFunction scale."""
    import xml.etree.ElementTree as ET
    root = ET.fromstring(osim_xml)
    joint = next(j for j in root.iter("CustomJoint") if j.get("name") == f"knee_{side}")
    fns = {}
    for tr in joint.find("SpatialTransform"):
        if tr.get("name") in ("translation1", "translation2"):
            sp = next(tr.iter("SimmSpline"))
            xs, ys = (np.array([float(v) for v in sp.findtext(k).split()]) for k in ("x", "y"))
            scale = tr.findtext(".//scale")
            fns[tr.get("name")] = (_spline(xs, ys), float(scale) if scale is not None else 1.0)
    (f1, s1), (f2, s2) = fns["translation1"], fns["translation2"]
    return lambda q: (s1 * f1(q), s2 * f2(q))


def thigh_length_m(osim_xml: bytes, side: str) -> float:
    """Hip joint centre to knee joint centre at zero flexion in the subject's OpenSim model (the femur frame's origin is the hip joint centre)."""
    return float(np.hypot(*knee_translation_fn(osim_xml, side)(0.0)))


def planar_knee_offset(thigh_flexion_deg, t) -> tuple:
    """(forward, up) of the knee joint centre from the hip joint centre when the thigh is flexed by thigh_flexion_deg from the vertical (forward positive)
    and the knee sits at t = (tx, ty) in the femur frame: the rotation of t about the lateral axis."""
    p = np.radians(thigh_flexion_deg)
    tx, ty = t
    return float(tx * np.cos(p) - ty * np.sin(p)), float(tx * np.sin(p) + ty * np.cos(p))


def log_shares(factors: dict, excess: float) -> dict:
    """Split `excess` (N m) over the factors whose product is the ratio, in proportion to each factor's logarithm (so the shares add up to the excess)."""
    total = float(np.sum([np.log(v) for v in factors.values()]))
    if abs(total) < 1e-12:
        return {k: 0.0 for k in factors}
    return {k: float(excess * np.log(v) / total) for k, v in factors.items()}


def force_lever_split(force_a, force_d, lever_a, lever_d, sign) -> tuple:
    """sign x (force_a lever_a - force_d lever_d) as (force part, lever part): the force part is the force difference at the dataset's lever, the lever
    part the lever difference at A's force. They add up to the whole difference exactly, and whatever the frame, so it can be averaged over any set of frames."""
    fa, fd, la, ld = (np.asarray(v, float) for v in (force_a, force_d, lever_a, lever_d))
    return sign * (fa - fd) * ld, sign * fa * (la - ld)


def term_sign(term, force, lever) -> float:
    """+1 or -1: the sign with which a torque term follows force x lever (the term is sign x force x lever, up to the planar approximation)."""
    return 1.0 if float(np.sum(np.asarray(term, float) * np.asarray(force, float) * np.asarray(lever, float))) >= 0 else -1.0


def direction_peaks(tau) -> tuple:
    """(largest flexion moment, largest extension moment) of one stride as magnitudes; flexion is positive."""
    tau = np.asarray(tau, float)
    return float(max(0.0, tau.max())), float(max(0.0, -tau.min()))


def p95_band(peaks) -> np.ndarray:
    """Boolean mask of the stride-limbs whose peak lies between the 92.5th and 97.5th percentile of the peaks."""
    p = np.asarray(peaks, float)
    return (p >= np.percentile(p, P95_LO)) & (p <= np.percentile(p, P95_HI))


def power_peaks(tau, speed) -> tuple:
    """(largest, smallest) of moment times angular speed over the frames: peak positive and peak negative (regenerative) power."""
    p = np.asarray(tau, float) * np.asarray(speed, float)
    return float(p.max()), float(p.min())


def _direction_stats(tau, speed, sign):
    sel = sign * tau > 0
    if not sel.any():
        return {"n": 0, "median": None, "p95": None, "max": None, "speed_at_p95": None}
    mag = sign * tau[sel]
    p95 = float(np.percentile(mag, 95))
    top = mag >= p95 - 1e-12
    return {"n": int(sel.sum()), "median": float(np.median(mag)), "p95": p95, "max": float(mag.max()), "speed_at_p95": float(np.median(speed[sel][top]))}


def angle_bins(angle_deg, tau, speed, width_deg=BIN_DEG) -> list:
    """Per bin of knee flexion angle (width_deg wide, lower edge `lo`): the frames, and for the flexion and the extension moment separately the frames,
    the median, 95th percentile and maximum of the moment magnitude and the median angular speed (signed, rad/s) of the frames at or above that 95th
    percentile; and the largest absolute speed of the bin."""
    angle, tau, speed = (np.asarray(v, float) for v in (angle_deg, tau, speed))
    lo = np.floor(angle / width_deg) * width_deg
    out = []
    for edge in sorted(set(lo.tolist())):
        m = lo == edge
        out.append({"lo": float(edge), "hi": float(edge + width_deg), "n": int(m.sum()), "flexion": _direction_stats(tau[m], speed[m], 1),
                    "extension": _direction_stats(tau[m], speed[m], -1), "max_abs_speed": float(np.abs(speed[m]).max())})
    return out


# ------------------------------------------------------------------------------ the dataset's knee joint centre

_OSIM = {}


def _osim_fn(subject: str, side: str):
    if (subject, side) not in _OSIM:
        import zipfile
        sys.path.insert(0, str(REPO / "analysis"))
        import ingest_camargo as ic
        zf = zipfile.ZipFile(ic.raw_dir() / f"{subject}.zip")
        blob = zf.read(next(n for n in zf.namelist() if n.lower() == f"osimxml/{subject.lower()}.osim"))
        _OSIM[(subject, side)] = knee_translation_fn(blob, side[0])
    return _OSIM[(subject, side)]


def dataset_hip_jc(ik, hip_in_pelvis, side: str) -> np.ndarray:
    """(n, 3) the dataset model's hip joint centre of one side in the model frame (x anterior, y left, z up): the pelvis position plus the pelvis rotation
    (OpenSim body-fixed order, with its roll, pitch and yaw) applied to the hip centre in the pelvis frame ([x forward, y up, +/- half separation]).
    The midpoint of the two sides is `retarget.dataset_hip_mid_lab`, which the CoP is referenced to; the yaw swings the lateral offset into the fore-aft direction."""
    import gaitloads
    import retarget
    names = retarget._channels()
    col = lambda n: ik[:, names.index(n)]
    h = np.array([hip_in_pelvis[0], hip_in_pelvis[1], hip_in_pelvis[2] if side == "right" else -hip_in_pelvis[2]])
    out = np.zeros((ik.shape[0], 3))
    for k in range(ik.shape[0]):
        a = np.deg2rad([col("pelvis_tilt")[k], col("pelvis_list")[k], col("pelvis_rotation")[k]])
        E, _, _ = retarget.euler_zxy(a, np.zeros(3), np.zeros(3))
        out[k] = np.array([col("pelvis_tx")[k], col("pelvis_ty")[k], col("pelvis_tz")[k]]) + E @ h
    return out @ gaitloads.LAB_TO_MODEL.T


def dataset_knee_jc(subject: str, side: str, ik, hip_jc, mapping) -> np.ndarray:
    """(100, 3) the dataset's knee joint centre in the model frame (x anterior, y left, z up): the hip joint centre plus the subject's OpenSim knee
    translation swung by the thigh's flexion from the vertical. `ik` is the stride's inverse kinematics (100 frames, the dataset's channels), `hip_jc`
    the hip joint centre of ankle_gain._dataset_side."""
    ch = gait.ic.IK_CHANNELS
    hip = mapping["joints"][f"hip_fe_{side}"]
    knee = mapping["joints"][f"knee_{side}"]
    phi = hip["sign"] * ik[:, ch.index(hip["dataset"])] + ik[:, ch.index("pelvis_list")]  # thigh flexion from the vertical, degrees
    q_knee = np.radians(ik[:, ch.index(knee["dataset"])])  # the dataset's own sign: negative flexion, which is OpenSim's
    f = _osim_fn(subject, side)
    off = np.array([planar_knee_offset(p, f(q)) for p, q in zip(phi, q_knee)])
    jc = np.array(hip_jc, float, copy=True)
    jc[:, 0] += off[:, 0]
    jc[:, 2] += off[:, 1]
    return jc


# ------------------------------------------------------------------------------ one stride, with the knee's angle and speed

def knee_stride(task: dict) -> dict:
    """ankle_gain.stride_terms plus, for both knees, the retargeted angle (degrees, flexion positive) and speed (rad/s) at the 100 frames."""
    import ankle_gain
    import retarget
    S = ankle_gain.stride_terms(task)
    c = gait._ctx(task["model_path"])
    z = gait._subject_arrays(task["processed"], task["subject"])
    sp, i = task["speed"], task["index"]
    sub = task["subject_info"]
    hip = sub.get("hip_in_pelvis_os_m")
    ref = task["root_reference"] if hip is not None else "pelvis_origin"
    cyc = retarget.Cycle(c.model, c.mapping, c.stand, z[f"{sp}_ik"][i], float(z[f"{sp}_duration_s"][i]), S["leg_ratio"], cutoff_hz=task["cutoff_hz"],
                         pitch_offset_deg=task["pitch_offset_deg"], root_rule=task["root_rule"], hip_in_pelvis_os=hip, root_ref=ref,
                         pitch_mean=task["pitch_mean"], trunk=task["trunk"])
    q, qd, _ = cyc.grid()
    S["knee_angle_deg"], S["knee_speed_rad_s"] = {}, {}
    for side in ("right", "left"):
        adr, dof = c.hinge[f"knee_{side}"]
        S["knee_angle_deg"][side], S["knee_speed_rad_s"][side] = np.degrees(q[:gait.N_FRAMES, adr]), qd[:gait.N_FRAMES, dof]
    return S


def run_knee(speed, workers, cop_scale=None, subjects=None, cap=None, native_force=False):
    """`knee_stride` for every subject-stride at one speed (the spec's smoothing, rigid trunk); `cop_scale` replaces the spec's existing knob."""
    import json
    from concurrent.futures import ProcessPoolExecutor
    spec = gait.load_spec("walk_treadmill")
    if cop_scale is not None:
        spec["cop_scale"] = float(cop_scale)
    if subjects:
        spec["subjects"] = list(subjects)
    manifest = json.loads((REPO / spec["dataset"]["manifest"]).read_text(encoding="utf-8"))
    tasks = gait._tasks(spec, manifest, gait.simrun.MODEL_FILE, REPO / spec["dataset"]["processed"], ["A_filtered"], float(spec["smoothing"]["cutoff_hz"]),
                        float(spec["pelvis_pitch_offset_deg"]), cap, False, False, False, trunk="rigid")
    tasks = [dict(t, native_force=True) if native_force else t for t in tasks if t["speed"] == speed]
    if workers <= 1 or len(tasks) < 8:
        return [knee_stride(t) for t in tasks]
    with ProcessPoolExecutor(max_workers=workers) as ex:
        return list(ex.map(knee_stride, tasks, chunksize=4))


def limb_series(S: dict, side: str, c, manifest) -> dict:
    """One stride-limb's knee torque over the 100 frames, A's and the dataset's (scaled to Freyja: per kg of the subject times Freyja's mass times the
    leg ratio), each split into the vertical-force term, the horizontal-force term and the rest (A: the distal weight and inertia; the dataset: its
    inverse-dynamics moment minus its plate-and-marker ground terms), the angle and speed, and the stance deciles."""
    import ankle_gain
    import foot_pitch
    D = ankle_gain._dataset_side(S, side, "knee", c, manifest)
    j = f"knee_{side}"
    mF, mS, ratio = c.mass, D["mass_kg"], S["leg_ratio"]
    k = mF * ratio / mS
    axis, anchor, cop, F = S["axis"][j], D["anchor"], D["cop"], D["force"]
    Fv, Fh = np.zeros_like(F), np.array(F, copy=True)
    Fv[:, 2], Fh[:, 2] = F[:, 2], 0.0
    g = lambda force: -np.einsum("ij,ij->i", axis, np.cross(cop - anchor, force))
    gvD, ghD = g(Fv) * k, g(Fh) * k
    tauD = D["tau"] * k
    try:
        dec = foot_pitch.stance_deciles(D["stance"])
    except ValueError:
        dec = np.full(len(D["stance"]), -1)
    foot = f"foot_{side}"
    fA, copA, kA, hA = S["force"][foot], S["cop"][foot], S["anchor"][j], S["anchor"][f"hip_fe_{side}"]
    fD, kD, hD = F * (mF / mS), anchor, D["hip_jc"]
    return {"side": side, "subject": S["subject"], "index": S["index"], "tauA": S["tau"][j], "gvA": -S["g_vert"][j], "ghA": -S["g_horiz"][j], "inA": S["inertial"][j],
            "tauD": tauD, "gvD": gvD, "ghD": ghD, "inD": tauD - gvD - ghD, "dec": dec, "angle": S["knee_angle_deg"][side], "speed": S["knee_speed_rad_s"][side],
            "stance_a": S["force"][foot][:, 2] > 0, "stance_d": D["stance"], "ratio": ratio,
            # the planar picture of the two force terms: vertical force x (CoP minus knee, forward) and horizontal force x (knee height), D scaled to Freyja
            "FzA": fA[:, 2], "FzD": fD[:, 2], "FxA": fA[:, 0], "FxD": fD[:, 0],
            "dxA": copA[:, 0] - kA[:, 0], "dxD": ratio * (cop[:, 0] - kD[:, 0]), "hA": kA[:, 2], "hD": ratio * kD[:, 2],
            "kneeA": kA, "hipA": hA, "kneeD": kD, "hipD": hD}


# ------------------------------------------------------------------------------ the report

def _g(v):
    return float(np.exp(np.mean(np.log(np.asarray(v, float)))))


def _factors(recs):
    ok = [r for r in recs if r["factors"]]
    return {k: _g([r["factors"][k] for r in ok]) for k in ok[0]["factors"]}, len(ok)


def _p95_peaks(series, key):
    return float(np.percentile([np.abs(s[key]).max() for s in series], 95))


def report(args):
    import json
    import ankle_gain
    import foot_pitch
    c = gait._ctx(gait.simrun.MODEL_FILE)
    manifest = json.loads((REPO / "data" / "camargo2021" / "manifest.json").read_text(encoding="utf-8"))
    parts = set(args.part)
    cache = {}
    for speed in args.speeds:
        S_list = run_knee(speed, args.workers)
        cache[speed] = S_list
        series = [limb_series(S, side, c, manifest) for S in S_list for side in ("right", "left")]
        recs = [ankle_gain.limb_record(S, side, "knee", c, manifest) for S in S_list for side in ("right", "left")]
        print(f"\n=== {speed} m/s: {len(S_list)} subject-strides, {len(series)} stride-limbs, Freyja {c.mass:.2f} kg ===")
        if "t4" in parts:
            t4(speed, S_list, series, recs, c, manifest)
        if "t5" in parts:
            t5(speed, series)
    if "cf" in parts:
        t4_counterfactuals(args, c, manifest, cache)
    if "t4" in parts:
        g = geometry(c, manifest)
        f_, s_ = g["freyja"], g["subjects"]
        print(f"\n=== GEOMETRY, mm: Freyja at stand_static | the 17 subjects as measured | times their leg ratio (mean {s_['ratio']:.4f}) ===")
        for lab, k in (("thigh length (hip to knee centre)", "thigh"), ("shank length (knee to ankle centre)", "shank"), ("ankle height", "ankle_height"),
                       ("knee height (upright, ankle height + shank)", "knee_height_upright"), ("hip half separation", "hip_half_separation")):
            kk = k if k != "knee_height_upright" else "knee_height"
            print(f"  {lab:46s} {1000 * f_[kk if kk in f_ else k]:7.1f} | {1000 * s_[k]:7.1f} | {1000 * s_[k + '_scaled']:7.1f}   (Freyja over scaled {f_[kk if kk in f_ else k] / s_[k + '_scaled']:.3f})")


def t4(speed, S_list, series, recs, c, manifest):
    import ankle_gain
    nl = len(series)
    sides = [s["side"] for s in series]
    peakA = np.array([np.abs(s["tauA"]).max() for s in series])
    peakD = np.array([np.abs(s["tauD"]).max() for s in series])
    print(f"(a) PEAKS per stride-limb, N m (A against the dataset scaled): 95th percentile / maximum")
    for lab, m in (("both", np.ones(nl, bool)), ("right", np.array([x == "right" for x in sides])), ("left", np.array([x == "left" for x in sides]))):
        print(f"    {lab:5s} A {np.percentile(peakA[m], 95):6.1f} / {peakA[m].max():6.1f}   dataset {np.percentile(peakD[m], 95):6.1f} / {peakD[m].max():6.1f}   "
              f"excess at the 95th {np.percentile(peakA[m], 95) - np.percentile(peakD[m], 95):+6.1f} N m, peak ratio of means {peakA[m].mean() / peakD[m].mean():.3f}")
    fl = np.array([direction_peaks(s["tauA"])[0] for s in series]), np.array([direction_peaks(s["tauA"])[1] for s in series])
    dl = np.array([direction_peaks(s["tauD"])[0] for s in series]), np.array([direction_peaks(s["tauD"])[1] for s in series])
    print("    by direction (largest moment per stride-limb, 95th percentile / max; flexion positive): "
          f"A flexion {np.percentile(fl[0], 95):.1f} / {fl[0].max():.1f}, A extension {np.percentile(fl[1], 95):.1f} / {fl[1].max():.1f}; "
          f"dataset flexion {np.percentile(dl[0], 95):.1f} / {dl[0].max():.1f}, dataset extension {np.percentile(dl[1], 95):.1f} / {dl[1].max():.1f}")
    dirA = np.array([1 if np.abs(s["tauA"]).argmax() == s["tauA"].argmax() and s["tauA"].max() >= -s["tauA"].min() else -1 for s in series])
    print(f"    A's stride peak is a flexion moment in {100 * np.mean(dirA > 0):.1f}% of stride-limbs, an extension moment in {100 * np.mean(dirA < 0):.1f}%")
    kp = np.array([r["kp"] for r in recs])
    dec_at = np.array([s["dec"][r["kp"]] for s, r in zip(series, recs)])
    inst = np.mean([s["stance_a"][r["kp"]] for s, r in zip(series, recs)])
    print(f"(b) THE PEAK FRAME (A's largest |knee torque| in that limb's stance; in stance at all: {100 * inst:.1f}% of stride-limbs): decile of the dataset's stance of that frame "
          + " ".join(f"{d}:{100 * np.mean(dec_at == d):.0f}%" for d in range(10) if np.mean(dec_at == d) > 0) + f"; unclassified {100 * np.mean(dec_at < 0):.0f}%")
    peak = np.array([r["tA"] for r in recs]) * c.mass  # N m at the peak frame
    band = p95_band(peak)
    f_all, n_all = _factors(recs)
    f_band, n_band = _factors([r for r, b in zip(recs, band) if b])
    prod = lambda f: float(np.prod(list(f.values())))
    print(f"    factors at that frame, geometric mean ({n_all} stride-limbs with every term nonzero): " + ", ".join(f"{k} {v:.3f}" for k, v in f_all.items()) + f"; product {prod(f_all):.3f}; "
          f"observed A/dataset at the frame {_g([r['tA'] / r['tD'] for r in recs]):.3f}; stride-peak ratio {_g([r['tau_peak_ratio'] for r in recs]):.3f}")
    print(f"    factors in the 95th-percentile band of A's peak-frame torque (92.5th to 97.5th, {n_band} stride-limbs, {np.percentile(peak, 92.5):.0f} to {np.percentile(peak, 97.5):.0f} N m): "
          + ", ".join(f"{k} {v:.3f}" for k, v in f_band.items()) + f"; product {prod(f_band):.3f}; observed {_g([r['tA'] / r['tD'] for r, b in zip(recs, band) if b]):.3f}")
    for side in ("right", "left"):
        f_s, n_s = _factors([r for r in recs if r["side"] == side])
        print(f"    {side:5s} limb: " + ", ".join(f"{k} {v:.3f}" for k, v in f_s.items()) + f"; product {prod(f_s):.3f}")
    clos = np.array([r["factors"]["data_closure"] for r in recs if r["factors"]])
    print(f"    the dataset's closure (its plate force through the knee centre built here, over its own inverse-dynamics knee moment): geometric mean {_g(clos):.3f}, median {np.median(clos):.3f}, "
          f"5th to 95th percentile {np.percentile(clos, 5):.3f} to {np.percentile(clos, 95):.3f}")
    # the lever at the peak frame, mm
    mm = lambda key: 1000 * np.array([r[key] for r in recs])
    kr_a = np.array([r["ank_rel_A"] for r in recs])  # ankle relative to the hip midpoint (forward, up)
    dxA, dxD = np.array([r["dxA"] for r in recs]), np.array([r["dxD"] * r["ratio"] for r in recs])
    hA, hD = np.array([r["hA"] for r in recs]), np.array([r["hD"] * r["ratio"] for r in recs])
    print(f"(c) THE LEVER at the peak frame, mm (mean [5th, 95th percentile over stride-limbs]): CoP ahead of the knee, A {1000 * dxA.mean():.1f}, dataset x leg ratio {1000 * dxD.mean():.1f}, "
          f"difference {1000 * (dxA - dxD).mean():+.1f} [{1000 * np.percentile(dxA - dxD, 5):+.0f}, {1000 * np.percentile(dxA - dxD, 95):+.0f}]; knee height above the floor, A {1000 * hA.mean():.1f}, "
          f"dataset x ratio {1000 * hD.mean():.1f}, difference {1000 * (hA - hD).mean():+.1f}")
    fz = np.array([r["fzA"] for r in recs]) * c.mass
    fx = np.array([r["fxA"] for r in recs]) * c.mass
    print(f"    force at that frame (A): vertical {fz.mean():.0f} N, fore-aft {fx.mean():.0f} N; the rule 'each 10 mm of horizontal offset is {fz.mean() / 100:.1f} N m' follows; "
          f"vertical-force term A {np.mean([r['vert_A'] for r in recs]) * c.mass:.1f} N m, horizontal-force term {np.mean([r['horiz_A'] for r in recs]) * c.mass:.1f}, distal weight and inertia {np.mean([r['inert_A'] for r in recs]) * c.mass:+.2f}; "
          f"torque at the frame, A {np.mean([r['tA'] for r in recs]) * c.mass:.1f} N m")
    # the knee's forward position split into thigh length and thigh angle, A against the scaled subject
    rows = []
    for S, side in [(S, sd) for S in S_list for sd in ("right", "left")]:
        D = ankle_gain._dataset_side(S, side, "knee", c, manifest)
        j = f"knee_{side}"
        kpi = int(np.argmax(np.where(S["force"][f"foot_{side}"][:, 2] > 0, np.abs(S["tau"][j]), -1.0)))
        hA_, kA_ = S["anchor"][f"hip_fe_{side}"][kpi], S["anchor"][j][kpi]
        hD_, kD_ = D["hip_jc"][kpi], D["anchor"][kpi]
        r = S["leg_ratio"]
        LA, LD = np.hypot(kA_[0] - hA_[0], kA_[2] - hA_[2]), r * np.hypot(kD_[0] - hD_[0], kD_[2] - hD_[2])
        pA, pD = np.arctan2(kA_[0] - hA_[0], hA_[2] - kA_[2]), np.arctan2(kD_[0] - hD_[0], hD_[2] - kD_[2])
        xA, xD = LA * np.sin(pA), LD * np.sin(pD)
        rows.append((LA, LD, np.degrees(pA), np.degrees(pD), xA - xD, (LA - LD) * np.sin(pD), LA * (np.sin(pA) - np.sin(pD)), LA / LD))
    R = np.array(rows)
    print(f"    the knee's forward position from its own hip (thigh length x sin of its flexion), A minus the scaled subject: {1000 * R[:, 4].mean():+.1f} mm; "
          f"from the thigh length (A {1000 * R[:, 0].mean():.1f} mm against {1000 * R[:, 1].mean():.1f}, ratio {R[:, 7].mean():.3f}): {1000 * R[:, 5].mean():+.1f} mm; from the thigh angle "
          f"(A {R[:, 2].mean():.1f} deg against {R[:, 3].mean():.1f}, {np.mean(R[:, 2] - R[:, 3]):+.2f}): {1000 * R[:, 6].mean():+.1f} mm")
    la = ankle_gain.leg_angle_offsets(S_list, c, manifest)
    print("    leg orientation, A minus the dataset (forward-positive angle from the vertical, degrees; mean, sd over every frame): " + "; ".join(f"{s} {m:+.2f} ({sd:.2f})" for s, (m, sd, by) in la.items()))
    reachA, reachD, ratio = (np.array([r[k] for r in recs]) for k in ("reach_A", "reach_D", "ratio"))
    print(f"    realised reach (largest hip-midpoint to ankle distance in the sagittal plane), A over the dataset's: {np.mean(reachA / reachD):.4f} against the leg ratio {ratio.mean():.4f}, "
          f"so A over (ratio x dataset) {np.mean(reachA / (reachD * ratio)):.4f}")
    # by decile of stance
    print("(d) BY DECILE OF STANCE (the dataset's stance flag, counted from heel strike): N m, mean over stride-limbs, signed, flexion positive; vertical-force term / horizontal-force term / total")
    print("    decile     A vert    D vert |  A horiz   D horiz |  A rest    D rest |  A total   D total | p95 of the largest flexion moment in the decile: A / D, extension: A / D | frames")
    exc = {}
    for d in range(10):
        sel = [(s, s["dec"] == d) for s in series if (s["dec"] == d).any()]
        if not sel:
            continue
        m = lambda key: np.mean([s[key][mk].mean() for s, mk in sel])
        peaks = {key: np.array([direction_peaks(s[key][mk]) for s, mk in sel]) for key in ("tauA", "tauD")}
        pf = lambda key, col: float(np.percentile(peaks[key][:, col], 95))
        exc[d] = (pf("tauA", 0) - pf("tauD", 0), pf("tauA", 1) - pf("tauD", 1))
        print(f"    {10 * d:2d}-{10 * d + 10:3d}% {m('gvA'):9.1f} {m('gvD'):9.1f} | {m('ghA'):8.1f} {m('ghD'):9.1f} | {m('inA'):7.1f} {m('inD'):9.1f} | {m('tauA'):8.1f} {m('tauD'):9.1f} | "
              f"{pf('tauA', 0):6.1f} / {pf('tauD', 0):6.1f}  {pf('tauA', 1):6.1f} / {pf('tauD', 1):6.1f} | {sum(int(mk.sum()) for _, mk in sel)}")
    dmax = max(exc, key=lambda d: max(exc[d]))
    dirmax = "flexion" if exc[dmax][0] >= exc[dmax][1] else "extension"
    print(f"    the largest 95th-percentile excess of a decile: decile {10 * dmax}-{10 * dmax + 10}%, {dirmax}, {max(exc[dmax]):+.1f} N m; by decile (flexion, extension): "
          + "; ".join(f"{10 * d}%: {e[0]:+.0f}, {e[1]:+.0f}" for d, e in exc.items()))
    # where A's stride peak is, by decile, and the share of the stride-peak excess that sits in the loading response
    peak_dec = np.array([s["dec"][int(np.abs(s["tauA"]).argmax())] for s in series])
    peak_dec_d = np.array([s["dec"][int(np.abs(s["tauD"]).argmax())] for s in series])
    print("    decile of the stride peak (A / dataset, % of stride-limbs): " + " ".join(f"{d}: {100 * np.mean(peak_dec == d):.0f}/{100 * np.mean(peak_dec_d == d):.0f}" for d in range(10) if np.mean(peak_dec == d) + np.mean(peak_dec_d == d) > 0)
          + f"; not in stance {100 * np.mean(peak_dec < 0):.0f}/{100 * np.mean(peak_dec_d < 0):.0f}")
    print("(d2) SELECTION-FREE ACCOUNTING by decile of stance (A minus the dataset scaled, mean over the frames of the decile, N m unless stated; D's force is per kg of the subject times Freyja's mass, its lever times the leg ratio):")
    accounting(series)
    lr = lambda a, lo, hi: float(np.mean([np.abs(s[a][(s['dec'] >= lo) & (s['dec'] < hi)]).max() if ((s['dec'] >= lo) & (s['dec'] < hi)).any() else 0 for s in series]))
    print(f"    mean stride-limb peak in the loading response (deciles 1 and 2, 10 to 30%), A {lr('tauA', 1, 3):.1f}, dataset {lr('tauD', 1, 3):.1f}; in the rest of stance (30 to 100%), A {lr('tauA', 3, 10):.1f}, dataset {lr('tauD', 3, 10):.1f}")


def accounting(series):
    """Selection-free accounting of A minus the dataset (scaled), frame by frame, by decile of stance (and the loading response, deciles 1 and 2 together):
    the difference of each force term split into the part from the force and the part from the lever (`force_lever_split`), the rest, the total, and in
    millimetres the lever differences, the knee's forward position split into thigh length and thigh angle, and the CoP's position from the hip. Every
    number is a mean over the frames of the decile, signed as the torque (flexion positive), N m; nothing is chosen from A's own peak."""
    allf = lambda key: np.concatenate([s[key][s["stance_a"]] for s in series])
    sv = term_sign(allf("gvA"), allf("FzA"), allf("dxA"))
    sh = term_sign(allf("ghA"), allf("FxA"), allf("hA"))
    print(f"    signs: vertical-force term = {sv:+.0f} x Fz x (CoP minus knee, forward); horizontal-force term = {sh:+.0f} x Fx x (knee height)")
    print("    decile frames |  dFz N  dFx N | d(lever) mm  d(height) mm | vertical term: force, lever, other | horizontal term: force, lever, other | distal weight and inertia | A - D total || "
          "knee forward from own hip: thigh length, thigh angle mm | CoP from hip mm")
    out = {}
    for label, decs in [(f"{10 * d:2d}-{10 * d + 10:3d}%", (d,)) for d in range(10)] + [("10-30%", (1, 2)), ("30-100%", tuple(range(3, 10)))]:
        cols = {k: [] for k in ("dFz", "dFx", "ddx", "dh", "Vf", "Vl", "Vo", "Hf", "Hl", "Ho", "rest", "tot", "len", "ang", "cop")}
        for s in series:
            m = np.isin(s["dec"], decs)
            if not m.any():
                continue
            vf, vl = force_lever_split(s["FzA"][m], s["FzD"][m], s["dxA"][m], s["dxD"][m], sv)
            hf, hl = force_lever_split(s["FxA"][m], s["FxD"][m], s["hA"][m], s["hD"][m], sh)
            dV, dH = (s["gvA"] - s["gvD"])[m], (s["ghA"] - s["ghD"])[m]
            LA = np.hypot(*(s["kneeA"] - s["hipA"])[m][:, [0, 2]].T)
            LD = s["ratio"] * np.hypot(*(s["kneeD"] - s["hipD"])[m][:, [0, 2]].T)
            pA = np.arctan2(*(s["kneeA"] - s["hipA"])[m][:, [0, 2]].T * np.array([[1], [-1]]))
            pD = np.arctan2(*(s["kneeD"] - s["hipD"])[m][:, [0, 2]].T * np.array([[1], [-1]]))
            copA_rel = (s["dxA"] + s["kneeA"][:, 0] - s["hipA"][:, 0])[m]  # CoP minus hip, forward: dx = cop - knee, so cop - hip = dx + (knee - hip)
            copD_rel = (s["dxD"] + s["ratio"] * (s["kneeD"][:, 0] - s["hipD"][:, 0]))[m]
            for key, v in (("dFz", s["FzA"][m] - s["FzD"][m]), ("dFx", s["FxA"][m] - s["FxD"][m]), ("ddx", s["dxA"][m] - s["dxD"][m]), ("dh", s["hA"][m] - s["hD"][m]),
                           ("Vf", vf), ("Vl", vl), ("Vo", dV - vf - vl), ("Hf", hf), ("Hl", hl), ("Ho", dH - hf - hl),
                           ("rest", (s["inA"] - s["inD"])[m]), ("tot", (s["tauA"] - s["tauD"])[m]),
                           ("len", (LA - LD) * np.sin(pD)), ("ang", LA * (np.sin(pA) - np.sin(pD))), ("cop", copA_rel - copD_rel)):
                cols[key].append(v)
        if not cols["tot"]:
            continue
        mean = {k: float(np.mean(np.concatenate(v))) for k, v in cols.items()}
        n = int(sum(len(v) for v in cols["tot"]))
        out[label] = mean
        print(f"    {label:7s} {n:6d} | {mean['dFz']:+6.1f} {mean['dFx']:+6.1f} | {1000 * mean['ddx']:+9.1f} {1000 * mean['dh']:+11.1f} | {mean['Vf']:+8.1f} {mean['Vl']:+7.1f} {mean['Vo']:+7.1f} | "
              f"{mean['Hf']:+8.1f} {mean['Hl']:+7.1f} {mean['Ho']:+7.1f} | {mean['rest']:+8.1f} | {mean['tot']:+8.1f} || {1000 * mean['len']:+8.1f} {1000 * mean['ang']:+8.1f} | {1000 * mean['cop']:+6.1f}")
    return out


def t4_counterfactuals(args, c, manifest, cache):
    """The two counterfactuals with existing knobs: the realised reach as the CoP scale (`cop_scale`), and A_native against A_filtered."""
    import gait_extract
    import ankle_gain
    print("\n=== COUNTERFACTUALS (existing knobs only; the spec is untouched) ===")
    scales = []
    for speed, S_list in cache.items():
        recs = [ankle_gain.limb_record(S, side, "knee", c, manifest) for S in S_list for side in ("right", "left")]
        scales.append(np.mean([r["reach_A"] / (r["reach_D"] * r["ratio"]) for r in recs]))
    scale = float(np.mean(scales))
    print(f"realised reach over (leg ratio x the dataset's): {', '.join(f'{x:.4f}' for x in scales)} for {', '.join(cache)}; cop_scale used: {scale:.3f} (their mean)")
    rows = {}
    for label, cs in (("A_filtered, cop_scale 1.0 (the spec)", None), (f"A_filtered, cop_scale {scale:.3f}", scale)):
        for speed in args.speeds:
            rows[(label, speed)] = _knee_fit(speed, args.workers, cs, "A_filtered", c, manifest)
    for speed in args.speeds:
        rows[("A_native, cop_scale 1.0", speed)] = _knee_fit(speed, args.workers, None, "A_native", c, manifest)
    print("knee, per kg of each body, both limbs and every stride pooled: OLS slope of A on the dataset; 95th percentile of the peak torque, N m, A / dataset scaled, right and left; excess")
    for (label, speed), v in rows.items():
        print(f"  {speed} m/s  {label:38s} slope {v['slope']:.3f}  p95 right {v['p95_a']['right']:.1f} / {v['p95_d']['right']:.1f} ({v['p95_a']['right'] - v['p95_d']['right']:+.1f}), "
              f"left {v['p95_a']['left']:.1f} / {v['p95_d']['left']:.1f} ({v['p95_a']['left'] - v['p95_d']['left']:+.1f})")


def _knee_fit(speed, workers, cop_scale, method, c, manifest):
    import json
    import retarget
    import gait_extract
    spec = gait.load_spec("walk_treadmill")
    if cop_scale is not None:
        spec["cop_scale"] = float(cop_scale)
    processed = REPO / spec["dataset"]["processed"]
    tasks = gait._tasks(spec, manifest, gait.simrun.MODEL_FILE, processed, [method], float(spec["smoothing"]["cutoff_hz"]), float(spec["pelvis_pitch_offset_deg"]), None,
                        False, False, False, trunk="rigid")
    tasks = [dict(t, keep_torque=True) for t in tasks if t["speed"] == speed]
    rows = gait._run_tasks(tasks, workers)
    xs, ys, pa, pd = [], [], {"right": [], "left": []}, {"right": [], "left": []}
    for r in rows:
        info = manifest["subjects"][r["subject"]]
        idm = gait._subject_arrays(processed, r["subject"])[f"{speed}_id"][r["index"]]
        ratio = retarget.leg_length_ratio(c.model, info["height_m"])
        for side in ("right", "left"):
            j = f"knee_{side}"
            spec_j = c.mapping["joints"][j]
            data = spec_j["sign"] * idm[:gait.N_FRAMES, gait.ic.ID_CHANNELS.index(spec_j["dataset"] + "_moment")] / info["mass_kg"]
            tau = np.asarray(r["torque"][method][j], float)
            xs.append(data)
            ys.append(tau / c.mass)
            pa[side].append(np.abs(tau).max())
            pd[side].append(np.abs(data).max() * c.mass * ratio)
    slope = gait_extract.ols(np.concatenate(xs), np.concatenate(ys))[0]
    return {"slope": slope, "p95_a": {k: float(np.percentile(v, 95)) for k, v in pa.items()}, "p95_d": {k: float(np.percentile(v, 95)) for k, v in pd.items()}}


def t5(speed, series):
    """The knee envelope for actuator sizing: A_filtered and the dataset-direct row."""
    for label, key in (("A_filtered", "tauA"), ("dataset-direct (scaled)", "tauD")):
        tau = np.concatenate([s[key] for s in series])
        ang = np.concatenate([s["angle"] for s in series])
        spd = np.concatenate([s["speed"] for s in series])
        per = [(direction_peaks(s[key]), power_peaks(s[key], s["speed"]), float(np.abs(s["speed"]).max()), float(s["angle"].max()), float(s["angle"].min())) for s in series]
        flex = np.array([p[0][0] for p in per])
        ext = np.array([p[0][1] for p in per])
        pw = np.array([p[1] for p in per])
        print(f"--- {label}, {speed} m/s, {len(series)} stride-limbs ({len(tau)} frames); knee torque N m positive = flexion (increasing knee angle); angle degrees flexion positive; speed rad/s ---")
        print(f"(T5) peak moment, per stride-limb peaks, 95th percentile / maximum: flexion {np.percentile(flex, 95):.1f} / {flex.max():.1f}; extension {np.percentile(ext, 95):.1f} / {ext.max():.1f}; "
              f"absolute extremes over every frame: flexion {tau.max():.1f}, extension {-tau.min():.1f}")
        sp_ = np.array([p[2] for p in per])
        print(f"     peak angular speed: 95th percentile {np.percentile(sp_, 95):.2f} / maximum {sp_.max():.2f} rad/s ({np.degrees(sp_.max()):.0f} deg/s); extension direction (negative) {spd.min():.2f}, flexion direction {spd.max():.2f}")
        print(f"     peak positive power {pw[:, 0].max():.0f} W (95th percentile of the stride peaks {np.percentile(pw[:, 0], 95):.0f}), peak negative power {pw[:, 1].min():.0f} W (5th percentile {np.percentile(pw[:, 1], 5):.0f})")
        amax = np.array([p[3] for p in per])
        print(f"     knee angle range used: largest flexion 95th percentile {np.percentile(amax, 95):.1f} / maximum {amax.max():.1f} deg; smallest angle (extension) 5th percentile {np.percentile([p[4] for p in per], 5):.1f} / minimum {min(p[4] for p in per):.1f} deg")
        loc = {"flexion": [], "extension": []}
        for s in series:
            t = s[key]
            if t.max() > 0:
                loc["flexion"].append(s["angle"][int(t.argmax())])
            if t.min() < 0:
                loc["extension"].append(s["angle"][int(t.argmin())])
        print("     knee angle at each stride-limb's peak moment (5th / 50th / 95th percentile, degrees): "
              + "; ".join(f"{k} {np.percentile(v, 5):.1f} / {np.percentile(v, 50):.1f} / {np.percentile(v, 95):.1f} (n {len(v)})" for k, v in loc.items()))
        print("     per 5-degree bin of knee flexion: frames | flexion moment: frames, median, p95, max, speed at p95 | extension moment: frames, median, p95, max, speed at p95 | max |speed|")
        f = lambda v, nd=1: "-" if v is None else f"{v:.{nd}f}"
        for b in angle_bins(ang, tau, spd):
            fl, ex = b["flexion"], b["extension"]
            print(f"     {b['lo']:5.0f}-{b['hi']:3.0f} {b['n']:7d} | {fl['n']:6d} {f(fl['median']):>6s} {f(fl['p95']):>6s} {f(fl['max']):>6s} {f(fl['speed_at_p95'], 2):>6s} | "
                  f"{ex['n']:6d} {f(ex['median']):>6s} {f(ex['p95']):>6s} {f(ex['max']):>6s} {f(ex['speed_at_p95'], 2):>6s} | {b['max_abs_speed']:.2f}")


def geometry(c, manifest):
    """Freyja at stand_static against the 17 subjects as measured and times their leg ratio: thigh length, shank length, knee height, ankle height, hip half separation."""
    import mujoco
    import retarget
    import zipfile
    sys.path.insert(0, str(REPO / "analysis"))
    import ingest_camargo as ic
    import ankle_gain
    m = c.model
    d = mujoco.MjData(m)
    d.qpos[:] = c.stand
    mujoco.mj_kinematics(m, d)
    jid = lambda n: mujoco.mj_name2id(m, mujoco.mjtObj.mjOBJ_JOINT, n)
    hip, knee, ankle = (d.xanchor[jid(n)] for n in ("hip_fe_right", "knee_right", "ankle_pdflex_right"))
    out = {"freyja": {"thigh": float(np.linalg.norm(knee - hip)), "shank": float(np.linalg.norm(ankle - knee)), "knee_height": float(knee[2]), "ankle_height": float(ankle[2]),
                      "hip_half_separation": float(abs(hip[1]))}}
    rows = []
    for sub, info in manifest["subjects"].items():
        zf = zipfile.ZipFile(ic.raw_dir() / f"{sub}.zip")
        blob = zf.read(next(n for n in zf.namelist() if n.lower() == f"osimxml/{sub.lower()}.osim"))
        thigh = thigh_length_m(blob, "r")
        shank = float(np.linalg.norm(_ankle_translation(blob)))
        ratio = retarget.leg_length_ratio(m, info["height_m"])
        rows.append((thigh, shank, info["hip_in_pelvis_os_m"][2], ratio))
    R = np.array(rows)
    bg = ankle_gain.body_geometry(c, manifest, "1.4")
    sh_ankle = bg["subjects"]["ankle_height"]
    out["subjects"] = {"thigh": R[:, 0].mean(), "shank": R[:, 1].mean(), "hip_half_separation": R[:, 2].mean(), "ankle_height": sh_ankle,
                       "knee_height_upright": sh_ankle + R[:, 1].mean(),
                       "thigh_scaled": (R[:, 0] * R[:, 3]).mean(), "shank_scaled": (R[:, 1] * R[:, 3]).mean(), "hip_half_separation_scaled": (R[:, 2] * R[:, 3]).mean(),
                       "ankle_height_scaled": bg["subjects"]["ankle_height_scaled"], "knee_height_upright_scaled": bg["subjects"]["ankle_height_scaled"] + (R[:, 1] * R[:, 3]).mean(),
                       "ratio": R[:, 3].mean()}
    return out


def _ankle_translation(osim_xml: bytes):
    """Ankle joint centre in the tibia frame (the translation of `tibia_r_offset` of `ankle_r`), metres; its length is the shank length."""
    import xml.etree.ElementTree as ET
    root = ET.fromstring(osim_xml)
    for j in root.iter("CustomJoint"):
        if j.get("name") == "ankle_r":
            for f in j.iter("PhysicalOffsetFrame"):
                if f.get("name") == "tibia_r_offset":
                    return np.array([float(v) for v in f.findtext("translation").split()[:3]])
    raise ValueError("no ankle_r tibia offset")
