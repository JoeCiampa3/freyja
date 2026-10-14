"""
Stage 2b T6 (report only): where does A_filtered's ankle gain come from? The diagnostics behind docs/memos/memo9-ankle-gain.md.

    python sim/scripts/gait_diag.py ankle-gain [--speeds 1.4 1.6] [--workers 5]

Nothing here changes the model, the sheet, the mapping, the retargeting, a default or the band, and nothing is written to the repo: the
lateral-malleolus markers are read from the raw archives (the dataset's marker set has `R_Ankle_Lat` and `L_Ankle_Lat`; the ingest keeps only
heel and toe-tip) into a cache outside the tracked tree (`--ankle-cache`, default `data/camargo2021/processed/ankle_lat/`, gitignored).
The strides are the ingest's own (same code, same acceptance tests), so a stride is matched to the processed arrays by trial and start time.

This module holds the pure helpers (tested in tests/test_ankle_gain.py) and the extraction; the per-stride physics is in the same file below.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import gait  # noqa: E402

REPO = gait.REPO


def stand_pitch_deg(qpos) -> float:
    """Pitch of a pose's root orientation, degrees: the rotation about the lateral axis (+y of the model: x anterior, y left, z up), the top of the body
    tipping forward positive. `qpos[3:7]` is the free joint's quaternion (w, x, y, z)."""
    import mujoco
    R = np.zeros(9)
    mujoco.mju_quat2Mat(R, np.asarray(qpos, float)[3:7])
    R = R.reshape(3, 3)
    return float(np.degrees(np.arctan2(-R[2, 0], R[2, 2])))


def gain_factors(tA, gA, gX, gD, tD, ratio) -> dict:
    """The factors whose product is A's torque over the dataset's, both per kg of their own body, at one frame:
      inertia       tA / gA     A's total over its own ground term (the weight and inertia of the bodies distal to the joint)
      lever         gA / gX     A's ground term over the same ground term with the dataset's CoP-to-joint geometry scaled by the leg ratio
      force         gX / (ratio * gD)   A's per-kg force against the dataset's, through the same geometry
      leg_ratio     ratio       the scaling a geometrically similar body gets
      data_closure  gD / tD     the ground term from the dataset's own force and markers over the dataset's own inverse-dynamics torque
    tA and tD are the two torques, gA A's ground term, gD the dataset's from its force plate and markers, gX the ground term of A's force through the
    dataset's geometry scaled by the leg ratio (all per kg, magnitudes)."""
    return {"inertia": tA / gA, "lever": gA / gX, "force": gX / (ratio * gD), "leg_ratio": ratio, "data_closure": gD / tD}


def force_weighted_lever(fz, dx) -> float:
    """Mean of the lever dx weighted by the vertical force (frames without load count for nothing)."""
    fz, dx = np.asarray(fz, float), np.asarray(dx, float)
    w = np.clip(fz, 0.0, None)
    return float((w * dx).sum() / w.sum()) if w.sum() > 0 else float("nan")


# ------------------------------------------------------------------------------ the lateral malleolus markers, from the raw archives

def ankle_marker_reader(read_table):
    """A `read_table` that serves the lateral-malleolus marker through the slot the ingest reads as the heel marker: `<foot>_Heel_<xyz>` of the
    returned table holds `<foot>_Ankle_Lat_<xyz>`. The ingest then stores the malleolus as the "heel" of `foot_markers`, with its own acceptance
    tests (a stride whose malleolus marker has gaps is rejected, so the stride sets are compared afterwards). Tables without the marker are returned as read."""
    def read(blob):
        t = dict(read_table(blob))
        if "R_Ankle_Lat_x" in t:
            for foot in "RL":
                for c in "xyz":
                    t[f"{foot}_Heel_{c}"] = t[f"{foot}_Ankle_Lat_{c}"]
        return t
    return read


def ankle_jc_offsets(osim_xml: bytes) -> np.ndarray:
    """Ankle joint centre minus the lateral-malleolus marker, in the tibia frame (x forward, y up, z right), metres, rows right and left. The joint
    centre is the translation of `tibia_<s>_offset` in the subject's OpenSim model; the marker is fixed in the tibia."""
    import xml.etree.ElementTree as ET
    root = ET.fromstring(osim_xml)
    vec = lambda text: np.array([float(v) for v in text.split()[:3]])
    jc = {f.get("name"): vec(f.findtext("translation")) for j in root.iter("CustomJoint") if j.get("name") in ("ankle_r", "ankle_l")
          for f in j.iter("PhysicalOffsetFrame") if f.get("name") in ("tibia_r_offset", "tibia_l_offset")}
    mk = {m.get("name"): vec(m.findtext("location")) for m in root.iter("Marker") if m.get("name") in ("R_Ankle_Lat", "L_Ankle_Lat")}
    return np.stack([jc["tibia_r_offset"] - mk["R_Ankle_Lat"], jc["tibia_l_offset"] - mk["L_Ankle_Lat"]])


def segment_masses(osim_xml: bytes) -> dict:
    """Right-leg segment masses of a subject's OpenSim model, kg: femur, tibia and foot (talus + calcn + toes)."""
    import xml.etree.ElementTree as ET
    m = {b.get("name"): float(b.findtext("mass")) for b in ET.fromstring(osim_xml).iter("Body")}
    return {"femur": m["femur_r"], "tibia": m["tibia_r"], "foot": m["talus_r"] + m["calcn_r"] + m["toes_r"]}


def ground_torque(axis, anchor, cop, force) -> float:
    """Torque of a ground force at `cop` about a hinge with unit `axis` through `anchor`: axis . ((cop - anchor) x force). Linear in the force, so the
    vertical force (force x lever) and the horizontal force (force x height of the joint above the floor) add."""
    return float(np.dot(axis, np.cross(np.asarray(cop, float) - np.asarray(anchor, float), np.asarray(force, float))))


def correlation_interval(r: float, n: int, z: float = 1.96) -> tuple:
    """Approximate 95% interval of a correlation r over n points (Fisher transform; z is the normal quantile)."""
    c = np.arctanh(r)
    se = 1.0 / np.sqrt(n - 3)
    return float(np.tanh(c - z * se)), float(np.tanh(c + z * se))


def extract_subject(subject: str, out_dir: Path) -> dict:
    """Run the ingest's own stride selection for one subject with the malleolus in the heel slot; save per speed `<s>_ankle` (n, 101, 2 feet R/L, 3)
    metres in the lab frame, with `<s>_t0` and `<s>_trial` to match strides. Returns the stride counts."""
    import yaml
    sys.path.insert(0, str(REPO / "analysis"))
    import ingest_camargo as ic
    spec = yaml.safe_load((REPO / "data" / "camargo2021" / "ingest_spec.yaml").read_text())
    orig = ic.read_table
    ic.read_table = ankle_marker_reader(orig)
    try:
        res = ic.ingest_subject(ic.raw_dir(), subject, spec)
    finally:
        ic.read_table = orig
    out, counts = {}, {}
    for s, d in res["strides"].items():
        out[f"{s}_ankle"] = d["foot_markers"][:, :, :, 0, :]
        out[f"{s}_t0"], out[f"{s}_trial"] = d["t0"], d["trial"]
        counts[s] = d["n"]
    import zipfile
    zf = zipfile.ZipFile(ic.raw_dir() / f"{subject}.zip")
    osim = zf.read(next(n for n in zf.namelist() if n.lower() == f"osimxml/{subject.lower()}.osim"))
    out["jc_minus_marker_tibia_m"] = ankle_jc_offsets(osim)
    out["segment_mass_kg"] = np.array([segment_masses(osim)[k] for k in ("femur", "tibia", "foot")])
    Path(out_dir).mkdir(parents=True, exist_ok=True)
    np.savez(Path(out_dir) / f"{subject}.npz", **out)
    return counts


# ------------------------------------------------------------------------------ one stride through A_filtered, with the torque split into its terms

TERM_JOINTS = tuple(f"{stem}_{side}" for stem in ("ankle_pdflex", "knee", "hip_fe", "hip_aa") for side in ("right", "left"))


def stride_terms(task: dict) -> dict:
    """One subject-stride through method A_filtered exactly as `gait.run_stride` does it (same retargeting, same filtered and scaled measured force, same CoP
    mapping, `task["cop_mode"]`), with each joint's torque split into: `inertial` (qfrc_inverse of the joint's row: the weight and inertia of the bodies
    distal to it), `g_vert` and `g_horiz` (the Jacobian-transpose terms of the vertical and of the horizontal ground force). tau = inertial - g_vert -
    g_horiz, which is `dynamics.solve_given`'s torque. Also the joint anchors and axes in the world, and each foot's CoP and force in the model frame
    (zero when the foot is not in stance). Everything is (100, ...) over the stride's frames."""
    import mujoco
    import dynamics
    import gaitloads
    import retarget
    c = gait._ctx(task["model_path"])
    model, mapping = c.model, c.mapping
    z = gait._subject_arrays(task["processed"], task["subject"])
    sp, i = task["speed"], task["index"]
    ik, fp = z[f"{sp}_ik"][i], z[f"{sp}_fp"][i]
    T = float(z[f"{sp}_duration_s"][i])
    sub = task["subject_info"]
    ratio = retarget.leg_length_ratio(model, sub["height_m"])
    mass_ratio = c.mass / sub["mass_kg"]
    hip = sub.get("hip_in_pelvis_os_m")
    ref = task["root_reference"] if hip is not None else "pelvis_origin"
    cyc = retarget.Cycle(model, mapping, c.stand, ik, T, ratio, cutoff_hz=task["cutoff_hz"], pitch_offset_deg=task["pitch_offset_deg"],
                         root_rule=task["root_rule"], hip_in_pelvis_os=hip, root_ref=ref, pitch_mean=task["pitch_mean"], trunk=task["trunk"])
    q, qd, qdd = cyc.grid()
    nf = gait.N_FRAMES
    ref_xy = np.array([retarget.model_hip_mid(model, q[k])[:2] if ref == "hip_midpoint" else q[k, :2] for k in range(nf)])
    ref_lab = retarget.dataset_hip_mid_lab(ik, hip) if ref == "hip_midpoint" else ik[:, 3:6]
    cop_mode = task.get("cop_mode", "hip_reference")
    markers = z[f"{sp}_foot_markers"][i] if cop_mode == "foot_frame" else None
    fpf = fp if task.get("native_force") else gaitloads.filter_measured(fp, T, task["cutoff_hz"])  # native_force: A_native's unfiltered force (diagnostic)
    nv = model.nv
    jid = {j: mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_JOINT, j) for j in TERM_JOINTS}
    dof = {j: c.hinge[j][1] for j in TERM_JOINTS}
    body = {f: mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_BODY, f) for f in gaitloads.FEET}
    out = {"subject": task["subject"], "speed": sp, "index": i, "leg_ratio": ratio, "mass_ratio": mass_ratio,
           **{k: {j: np.zeros(nf) for j in TERM_JOINTS} for k in ("tau", "inertial", "g_vert", "g_horiz")},
           "anchor": {j: np.zeros((nf, 3)) for j in TERM_JOINTS}, "axis": {j: np.zeros((nf, 3)) for j in TERM_JOINTS},
           "cop": {f: np.zeros((nf, 3)) for f in gaitloads.FEET}, "force": {f: np.zeros((nf, 3)) for f in gaitloads.FEET}}
    d = mujoco.MjData(model)
    jp = np.zeros((3, nv))
    for k in range(nf):
        qfrc = dynamics.inverse_frame(model, q[k], qd[k], qdd[k])
        if cop_mode == "foot_frame":
            forces, cops = gaitloads.measured_to_model_foot(fpf[:, k, :], markers[k], dynamics.foot_floor_segments(model, q[k]), mass_ratio)
        else:
            forces, cops = gaitloads.measured_to_model(fpf[:, k, :], ref_lab[k], ref_xy[k], mass_ratio, ratio, task["cop_scale"])
        d.qpos[:] = q[k]
        mujoco.mj_kinematics(model, d)
        mujoco.mj_comPos(model, d)
        gv, gh = np.zeros(nv), np.zeros(nv)
        for f, force in forces.items():
            mujoco.mj_jac(model, d, jp, None, np.asarray(cops[f], float), body[f])
            force = np.asarray(force, float)
            gv += jp.T @ np.array([0.0, 0.0, force[2]])
            gh += jp.T @ np.array([force[0], force[1], 0.0])
            out["cop"][f][k], out["force"][f][k] = cops[f], force
        for j in TERM_JOINTS:
            out["inertial"][j][k], out["g_vert"][j][k], out["g_horiz"][j][k] = qfrc[dof[j]], gv[dof[j]], gh[dof[j]]
            out["tau"][j][k] = qfrc[dof[j]] - gv[dof[j]] - gh[dof[j]]
            out["anchor"][j][k], out["axis"][j][k] = d.xanchor[jid[j]], d.xaxis[jid[j]]
    return out


# ------------------------------------------------------------------------------ the report

ANKLE_CACHE = REPO / "data" / "camargo2021" / "processed" / "ankle_lat"


def _l2m(points_lab):
    """(n, 3) lab-frame points or vectors (x right, y up, z backward) to the model frame (x anterior, y left, z up)."""
    import gaitloads
    return np.asarray(points_lab, float) @ gaitloads.LAB_TO_MODEL.T


def run_terms(speed: str, cop_mode: str, workers: int, subjects=None, cap=None, pitch_offset_deg=None) -> list:
    """`stride_terms` for every subject-stride at one speed under one CoP mapping (the spec's smoothing and offsets, rigid trunk). `pitch_offset_deg`
    replaces the spec's pelvis pitch offset (the existing sensitivity knob, anterior positive); the spec file and every default are untouched."""
    import json
    from concurrent.futures import ProcessPoolExecutor
    spec = gait.load_spec("walk_treadmill")
    spec["cop_mode"] = cop_mode
    if pitch_offset_deg is not None:
        spec["pelvis_pitch_offset_deg"] = float(pitch_offset_deg)
    if subjects:
        spec["subjects"] = list(subjects)
    manifest = json.loads((REPO / spec["dataset"]["manifest"]).read_text(encoding="utf-8"))
    tasks = gait._tasks(spec, manifest, gait.simrun.MODEL_FILE, REPO / spec["dataset"]["processed"], ["A_filtered"], float(spec["smoothing"]["cutoff_hz"]),
                        float(spec["pelvis_pitch_offset_deg"]), cap, False, False, False, trunk="rigid")
    tasks = [t for t in tasks if t["speed"] == speed]
    if workers <= 1 or len(tasks) < 8:
        return [stride_terms(t) for t in tasks]
    with ProcessPoolExecutor(max_workers=workers) as ex:
        return list(ex.map(stride_terms, tasks, chunksize=4))


_CACHE = {}


def _ankle_cache(subject, cache_dir):
    if (subject, str(cache_dir)) not in _CACHE:
        _CACHE[(subject, str(cache_dir))] = dict(np.load(Path(cache_dir) / f"{subject}.npz"))
    return _CACHE[(subject, str(cache_dir))]


def _dataset_side(S: dict, side: str, joint_stem: str, c, manifest, cache_dir=ANKLE_CACHE) -> dict:
    """The dataset's side of one stride-limb in the model frame (x anterior, y left, z up), 100 frames: the plate force (N) and CoP of that foot (zero in
    swing), the inverse-dynamics torque of the joint in the model's sign (N m), the joint's anchor (the ankle joint centre from the malleolus marker moved by the
    subject's OpenSim model with the tibia taken as upright, or the hip joint centre from the pelvis pose with the pelvis taken as not rolled or yawed), the
    hip midpoint, and the subject's mass."""
    import gaitloads
    import retarget
    limb = 0 if side == "right" else 1
    spec_j = c.mapping["joints"][f"{joint_stem}_{side}"]
    sub = S["subject"]
    info = manifest["subjects"][sub]
    z = gait._subject_arrays(REPO / "data" / "camargo2021" / "processed", sub)
    sp, i = S["speed"], S["index"]
    nf = gait.N_FRAMES
    ik, fp, idm = z[f"{sp}_ik"][i][:nf], z[f"{sp}_fp"][i][:, :nf], z[f"{sp}_id"][i][:nf]
    stance = fp[limb, :, 6] >= gaitloads.STANCE_FLAG
    cop_lab = np.nan_to_num(fp[limb, :, 3:6])
    cache = _ankle_cache(sub, cache_dir)
    off = cache["jc_minus_marker_tibia_m"][limb]
    ankle_jc = _l2m(cache[f"{sp}_ankle"][i][:nf, limb]) + np.array([off[0], -off[2], off[1]])  # tibia frame (x forward, y up, z right) -> model
    hip = info["hip_in_pelvis_os_m"]
    hip_mid = retarget.dataset_hip_mid_lab(ik, hip)
    hip_jc = _l2m(hip_mid + np.array([hip[2] if side == "right" else -hip[2], 0.0, 0.0]))
    if joint_stem.startswith("ankle"):
        anchor = ankle_jc
    elif joint_stem == "knee":  # Stage 2d T4: the knee joint centre from the dataset's kinematics and the subject's OpenSim knee (sim/scripts/knee_gain.py)
        import knee_gain
        hip_jc = knee_gain.dataset_hip_jc(ik, hip, side)  # with the pelvis's yaw: the lateral offset swings fore-aft (memo9's planar hip centre ignored it)
        anchor = knee_gain.dataset_knee_jc(sub, side, ik, hip_jc, c.mapping)
    else:
        anchor = hip_jc
    return {"force": _l2m(fp[limb, :, 0:3]), "cop": _l2m(np.c_[cop_lab[:, 0], np.zeros(nf), cop_lab[:, 2]]) * stance[:, None], "stance": stance,
            "tau": spec_j["sign"] * idm[:, gait.ic.ID_CHANNELS.index(spec_j["dataset"] + "_moment")], "ankle_jc": ankle_jc, "hip_jc": hip_jc,
            "anchor": anchor, "hip_mid": hip_mid, "mass_kg": info["mass_kg"], "ik": ik}


def limb_record(S: dict, side: str, joint_stem: str, c, manifest, cache_dir=ANKLE_CACHE) -> dict:
    """Everything one subject-stride's limb gives for one joint, at the frame of A's largest |torque| during that limb's stance: the factors of
    `gain_factors`, the forces, levers and terms of both A and the dataset. Magnitudes; torques and forces per kg of their own body."""
    j, foot = f"{joint_stem}_{side}", f"foot_{side}"
    D = _dataset_side(S, side, joint_stem, c, manifest, cache_dir)
    mF, mS, ratio = c.mass, D["mass_kg"], S["leg_ratio"]
    Fd, copd, tau_d, anchor_d, ankle_jc, hip_jc, hip_mid = D["force"], D["cop"], D["tau"], D["anchor"], D["ankle_jc"], D["hip_jc"], D["hip_mid"]
    # A
    FA, copA = S["force"][foot], S["cop"][foot]
    stance_a = FA[:, 2] > 0
    tau = S["tau"][j]
    kp = int(np.argmax(np.where(stance_a, np.abs(tau), -1.0)))
    axis = S["axis"][j][kp]
    gA = -(S["g_vert"][j][kp] + S["g_horiz"][j][kp])
    g_d = -ground_torque(axis, anchor_d[kp], copd[kp], Fd[kp])
    gX = ground_torque(axis, np.zeros(3), ratio * (copd[kp] - anchor_d[kp]), FA[kp] / mF)
    tA, tD = abs(tau[kp]) / mF, abs(tau_d[kp]) / mS
    gA_, gD_, gX_ = abs(gA) / mF, abs(g_d) / mS, abs(gX)
    anchor_a = S["anchor"][j]
    reach_a = np.max(np.hypot(*(S["anchor"][f"ankle_pdflex_{side}"] - S["anchor"][f"hip_fe_{side}"])[:, [0, 2]].T))
    reach_d = np.max(np.hypot(*(ankle_jc - hip_jc)[:, [0, 2]].T))
    sgn = np.sign(tau[kp])
    hipmid_a = 0.5 * (S["anchor"]["hip_fe_right"] + S["anchor"]["hip_fe_left"])
    hipmid_d = _l2m(hip_mid)
    ank_a = S["anchor"][f"ankle_pdflex_{side}"]
    return {"ank_rel_A": (ank_a - hipmid_a)[kp][[0, 2]], "ank_rel_D_scaled": ratio * (ankle_jc - hipmid_d)[kp][[0, 2]],
            "cop_rel_gap_x": (copA[kp, 0] - hipmid_a[kp, 0]) - ratio * (copd[kp, 0] - hipmid_d[kp, 0]),
            "subject": S["subject"], "side": side, "kp": kp, "ratio": ratio, "tA": tA, "tD": tD, "gA": gA_, "gD": gD_, "gX": gX_,
            "factors": gain_factors(tA, gA_, gX_, gD_, tD, ratio) if min(gA_, gX_, gD_, tD) > 0 else None,
            "tau_peak_ratio": (np.abs(tau).max() / mF) / (np.abs(tau_d).max() / mS),
            "fzA": FA[kp, 2] / mF, "fzD": Fd[kp, 2] / mS, "fxA": FA[kp, 0] / mF, "fxD": Fd[kp, 0] / mS,
            "fz_peak_A": FA[:, 2].max() / mF, "fz_peak_D": Fd[:, 2].max() / mS, "fx_peak_A": np.abs(FA[:, 0]).max() / mF, "fx_peak_D": np.abs(Fd[:, 0]).max() / mS,
            "dxA": copA[kp, 0] - anchor_a[kp, 0], "dxD": copd[kp, 0] - anchor_d[kp, 0], "hA": anchor_a[kp, 2], "hD": anchor_d[kp, 2],
            "dyA": copA[kp, 1] - anchor_a[kp, 1], "dyD": copd[kp, 1] - anchor_d[kp, 1],
            "lever_w_A": force_weighted_lever(FA[:, 2], copA[:, 0] - anchor_a[:, 0]), "lever_w_D": force_weighted_lever(Fd[:, 2], copd[:, 0] - anchor_d[:, 0]),
            "lever_wy_A": force_weighted_lever(FA[:, 2], copA[:, 1] - anchor_a[:, 1]), "lever_wy_D": force_weighted_lever(Fd[:, 2], copd[:, 1] - anchor_d[:, 1]),
            "vert_A": -S["g_vert"][j][kp] / mF * sgn, "horiz_A": -S["g_horiz"][j][kp] / mF * sgn, "inert_A": S["inertial"][j][kp] / mF * sgn,
            "inert_D": (tau_d[kp] - g_d) / mS * np.sign(tau_d[kp]), "ground_D": g_d / mS * np.sign(tau_d[kp]),
            "inert_max_A": float(np.abs(S["inertial"][j][stance_a]).max() / mF) if stance_a.any() else 0.0,
            "reach_A": reach_a, "reach_D": reach_d}


def _med(v, nd=3):
    v = np.asarray(v, float)
    return f"{np.median(v):.{nd}f} [{np.percentile(v, 5):.{nd}f}, {np.percentile(v, 95):.{nd}f}]"


def _gmean(v):
    return float(np.exp(np.mean(np.log(np.asarray(v, float)))))


def subject_values(recs, fn) -> dict:
    """Mean over a subject's strides of fn(record), keyed by subject."""
    by = {}
    for r in recs:
        by.setdefault(r["subject"], []).append(fn(r))
    return {k: float(np.mean(v)) for k, v in by.items()}


def correlations(y: dict, xs: dict) -> list:
    """(name, r, lo, hi) of the subject-level y against each x (dicts keyed by subject), n = number of subjects, 95% Fisher interval."""
    keys = sorted(y)
    out = []
    for name, x in xs.items():
        r = float(np.corrcoef([y[k] for k in keys], [x[k] for k in keys])[0, 1])
        out.append((name, r) + correlation_interval(r, len(keys)))
    return out


def ankle_position_profile(S_list, manifest, n_bins=10) -> np.ndarray:
    """(n_bins, 2, 2) mean over strides, both limbs, of A's ankle position relative to the hip midpoint minus the leg ratio times the dataset's (forward, up),
    metres, in phase bins of the stride (the stride's 100 frames cut into n_bins equal parts, each represented by its middle frame), with the sd as the
    second row of the second axis: [bin][mean, sd][forward, up]. The dataset's ankle is the malleolus marker moved to the joint centre."""
    import retarget
    nf = gait.N_FRAMES
    rows = [[] for _ in range(n_bins)]
    for S in S_list:
        sub = S["subject"]
        info = manifest["subjects"][sub]
        z = gait._subject_arrays(REPO / "data" / "camargo2021" / "processed", sub)
        i = S["index"]
        cache = _ankle_cache(sub, ANKLE_CACHE)
        hm = _l2m(retarget.dataset_hip_mid_lab(z[f"{S['speed']}_ik"][i][:nf], info["hip_in_pelvis_os_m"]))
        hip_a = 0.5 * (S["anchor"]["hip_fe_right"] + S["anchor"]["hip_fe_left"])
        for limb, side in enumerate(("right", "left")):
            off = cache["jc_minus_marker_tibia_m"][limb]
            jc = _l2m(cache[f"{S['speed']}_ankle"][i][:nf, limb]) + np.array([off[0], -off[2], off[1]])
            diff = (S["anchor"][f"ankle_pdflex_{side}"] - hip_a) - S["leg_ratio"] * (jc - hm)
            for b in range(n_bins):
                rows[b].append(diff[int((b + 0.5) * nf / n_bins)][[0, 2]])
    return np.array([[np.mean(r, axis=0), np.std(r, axis=0)] for r in rows])


def leg_angle_offsets(S_list, c, manifest) -> dict:
    """Thigh and shank angle from the vertical (forward positive, sagittal, degrees), A minus the dataset, over every frame of every stride and limb.
    A's from the hip, knee and ankle joint anchors; the dataset's from its inverse kinematics: thigh = hip flexion + pelvis_list (the T1 rule), shank =
    thigh minus knee flexion. Returns {segment: (mean, sd, mean by tenth of the stride)}."""
    import gait_extract
    ch = gait.ic.IK_CHANNELS
    out = {"thigh": [], "shank": []}
    for S in S_list:
        for side in ("right", "left"):
            ik = _dataset_side(S, side, "ankle_pdflex", c, manifest)["ik"]
            sg = lambda n: c.mapping["joints"][f"{n}_{side}"]
            hip = sg("hip_fe")["sign"] * ik[:, ch.index(sg("hip_fe")["dataset"])]
            knee = sg("knee")["sign"] * ik[:, ch.index(sg("knee")["dataset"])]
            thigh_d = gait_extract.thigh_world_deg(hip, ik[:, ch.index("pelvis_list")])
            shank_d = thigh_d - knee
            h, k, a = (S["anchor"][f"{n}_{side}"] for n in ("hip_fe", "knee", "ankle_pdflex"))
            thigh_a = np.degrees(np.arctan2(k[:, 0] - h[:, 0], h[:, 2] - k[:, 2]))
            shank_a = np.degrees(np.arctan2(a[:, 0] - k[:, 0], k[:, 2] - a[:, 2]))
            out["thigh"].append(thigh_a - thigh_d)
            out["shank"].append(shank_a - shank_d)
    res = {}
    for seg, rows in out.items():
        r = np.array(rows)
        res[seg] = (float(r.mean()), float(r.std()), r.reshape(len(r), 10, -1).mean(axis=(0, 2)))
    return res


def term_slopes(S_list, c, manifest, stem: str) -> dict:
    """OLS slope of A on the dataset (per kg of each body) for a joint's torque and its terms, frames pooled over every stride and both limbs:
    total over all frames, in stance, in swing; the ground term in stance (A's from the Jacobian, the dataset's from its plate force and markers); the
    remainder (A's weight and inertia of the distal bodies; the dataset's inverse-dynamics torque minus its ground term) in stance and in swing."""
    import gait_extract
    pools = {k: ([], []) for k in ("total", "total_stance", "total_swing", "ground_stance", "remainder_stance", "remainder_swing")}
    for S in S_list:
        for side in ("right", "left"):
            D = _dataset_side(S, side, stem, c, manifest)
            j = f"{stem}_{side}"
            mF, mS = c.mass, D["mass_kg"]
            tA, iA = S["tau"][j] / mF, S["inertial"][j] / mF
            gA = -(S["g_vert"][j] + S["g_horiz"][j]) / mF
            gD = -np.einsum("ij,ij->i", S["axis"][j], np.cross(D["cop"] - D["anchor"], D["force"])) / mS
            tD = D["tau"] / mS
            st = D["stance"]
            for key, mask, a, d in (("total", slice(None), tA, tD), ("total_stance", st, tA, tD), ("total_swing", ~st, tA, tD), ("ground_stance", st, gA, gD),
                                    ("remainder_stance", st, iA, tD - gD), ("remainder_swing", ~st, iA, tD - gD)):
                pools[key][0].append(np.asarray(d)[mask])
                pools[key][1].append(np.asarray(a)[mask])
    out = {}
    for key, (d, a) in pools.items():
        d, a = np.concatenate(d), np.concatenate(a)
        slope, icpt = gait_extract.ols(d, a)
        out[key] = {"slope": slope, "intercept": icpt, "corr": float(np.corrcoef(d, a)[0, 1]), "rms_a": float(np.sqrt(np.mean(a ** 2))), "rms_d": float(np.sqrt(np.mean(d ** 2))), "n": len(d)}
    return out


def body_geometry(c, manifest, speed: str) -> dict:
    """Freyja's foot and hip geometry at stand_static against the subjects', in metres. Freyja: the ankle joint's height above the floor, its distance to the
    front and rear of the foot box on the floor (the box's long axis), the hip joints' half separation. Subjects, means over the 17: the ankle joint centre's height
    and its forward distance to the toe-tip marker in mid-stance (frames 10 to 30 of the stride, right foot, 1 x leg ratio and as measured), and the hip half separation
    from the subject's OpenSim model, times the leg ratio."""
    import mujoco
    import dynamics
    import retarget
    m = c.model
    d = mujoco.MjData(m)
    d.qpos[:] = c.stand
    mujoco.mj_kinematics(m, d)
    jid = lambda n: mujoco.mj_name2id(m, mujoco.mjtObj.mjOBJ_JOINT, n)
    ankle = d.xanchor[jid("ankle_pdflex_right")]
    rear, front = dynamics.foot_floor_segments(m, c.stand)["foot_right"]
    out = {"freyja": {"ankle_height": float(ankle[2]), "ankle_to_front": float(front[0] - ankle[0]), "ankle_to_rear": float(ankle[0] - rear[0]),
                      "hip_half_separation": float(abs(d.xanchor[jid("hip_fe_right")][1]))}}
    rows = []
    for sub, info in manifest["subjects"].items():
        z = gait._subject_arrays(REPO / "data" / "camargo2021" / "processed", sub)
        cache = _ankle_cache(sub, ANKLE_CACHE)
        off = cache["jc_minus_marker_tibia_m"][0]
        fm = z[f"{speed}_foot_markers"][:, 10:30, 0, 1, :]  # toe tip, lab
        am = cache[f"{speed}_ankle"][:, 10:30, 0, :]
        ratio = retarget.leg_length_ratio(m, info["height_m"])
        rows.append((float(np.median(-(fm[..., 2]) + am[..., 2])) - off[0], float(np.median(am[..., 1])) + off[1], info["hip_in_pelvis_os_m"][2], ratio))
    r = np.array(rows)
    seg = np.array([_ankle_cache(sub, ANKLE_CACHE)["segment_mass_kg"] / info["mass_kg"] for sub, info in manifest["subjects"].items()])
    ids = [mujoco.mj_name2id(m, mujoco.mjtObj.mjOBJ_BODY, n) for n in ("thigh_right", "shank_right", "foot_right")]
    out["segment_mass_fraction"] = {"freyja": [float(m.body_mass[i] / c.mass) for i in ids], "subjects": [float(v) for v in seg.mean(axis=0)]}
    out["subjects"] = {"ankle_to_toe": r[:, 0].mean(), "ankle_height": r[:, 1].mean(), "hip_half_separation": r[:, 2].mean(),
                       "ankle_to_toe_scaled": (r[:, 0] * r[:, 3]).mean(), "ankle_height_scaled": (r[:, 1] * r[:, 3]).mean(), "hip_half_separation_scaled": (r[:, 2] * r[:, 3]).mean()}
    return out


def _fit_rows(S_list, c, manifest, stems):
    """gait_diag.stem_fit of A_filtered against the dataset per kg for each stem, both limbs and every stride pooled, plus per-subject OLS slopes."""
    import gait_diag
    out = {}
    for stem in stems:
        model, data, subj = [], [], []
        for S in S_list:
            z = gait._subject_arrays(REPO / "data" / "camargo2021" / "processed", S["subject"])
            idm = z[f"{S['speed']}_id"][S["index"]][:gait.N_FRAMES]
            mS = manifest["subjects"][S["subject"]]["mass_kg"]
            for side in ("right", "left"):
                spec_j = c.mapping["joints"][f"{stem}_{side}"]
                model.append(S["tau"][f"{stem}_{side}"] / c.mass)
                data.append(spec_j["sign"] * idm[:, gait.ic.ID_CHANNELS.index(spec_j["dataset"] + "_moment")] / mS)
                subj.append(S["subject"])
        f = gait_diag.stem_fit(model, data)
        per = {u: gait_diag.ols(np.concatenate([data[k] for k in range(len(subj)) if subj[k] == u]),
                                np.concatenate([model[k] for k in range(len(subj)) if subj[k] == u]))[0] for u in sorted(set(subj))}
        out[stem] = (f, per)
    return out


def _print_fit_table(title, fits):
    print(title)
    print("    stem          slope  intercept   gain    corr  corr_pooled | rms % ptp  after gain | peak diff N m/kg  after gain | per-subject slope median [min, max]")
    for stem, (f, per) in fits.items():
        v = list(per.values())
        print(f"    {stem:12s} {f['slope']:6.3f} {f['intercept']:9.4f} {f['gain']:7.3f} {f['corr']:7.3f} {f['corr_pooled']:7.3f}   | {f['rms_pct_ptp']:6.1f} {f['rms_gain_removed_pct_ptp']:9.1f}"
              f"   | {f['peak_diff']:8.3f} {f['peak_diff_gain_removed']:12.3f}   | {np.median(v):.3f} [{min(v):.3f}, {max(v):.3f}]")


def _chain_lines(recs, label):
    ok = [r for r in recs if r["factors"]]
    f = {k: [r["factors"][k] for r in ok] for k in ok[0]["factors"]}
    print(f"  {label}: {len(ok)} stride-limbs. Peak-frame torque ratio A/dataset per kg (geometric mean) {_gmean([r['tA'] / r['tD'] for r in ok]):.3f}; "
          f"stride-peak ratio {_gmean([r['tau_peak_ratio'] for r in recs]):.3f}")
    print("    factor (geometric mean, median [p5, p95]): " + "; ".join(f"{k} {_gmean(v):.3f}, {_med(v)}" for k, v in f.items()))
    print(f"    product of the geometric means {np.prod([_gmean(v) for v in f.values()]):.3f}")


def ankle_gain_report(args):
    import json
    import gaitloads
    c = gait._ctx(gait.simrun.MODEL_FILE)
    manifest = json.loads((REPO / "data" / "camargo2021" / "manifest.json").read_text(encoding="utf-8"))
    subs = args.subjects or None
    for speed in args.speeds:
        runs = {mode: run_terms(speed, mode, args.workers, subjects=subs, cap=args.cap) for mode in ("hip_reference", "foot_frame")}
        sp_deg = stand_pitch_deg(c.stand)
        runs["stand_pitch_removed"] = run_terms(speed, "hip_reference", args.workers, subjects=subs, cap=args.cap, pitch_offset_deg=-sp_deg)
        S_list = runs["hip_reference"]
        print(f"\n=== {speed} m/s: {len(S_list)} subject-strides, {len({S['subject'] for S in S_list})} subjects; Freyja mass {c.mass:.2f} kg; all at the frame of A's largest |torque| in that limb's stance ===")
        recs = {stem: [limb_record(S, side, stem, c, manifest) for S in S_list for side in ("right", "left")] for stem in ("ankle_pdflex", "hip_fe", "hip_aa")}
        R = recs["ankle_pdflex"]
        print("(a) FORCE, per kg of each body. Stride-peak vertical force and peak |fore-aft| force: A (filtered, scaled) over the dataset's raw plate force; and the vertical force at the peak-torque frame")
        print(f"    vertical peak A {np.mean([r['fz_peak_A'] for r in R]):.3f} N/kg, dataset {np.mean([r['fz_peak_D'] for r in R]):.3f}; ratio {_med([r['fz_peak_A'] / r['fz_peak_D'] for r in R])}")
        print(f"    fore-aft peak A {np.mean([r['fx_peak_A'] for r in R]):.3f} N/kg, dataset {np.mean([r['fx_peak_D'] for r in R]):.3f}; ratio {_med([r['fx_peak_A'] / r['fx_peak_D'] for r in R])}")
        print(f"    vertical at the peak-torque frame: A {np.mean([r['fzA'] for r in R]):.3f}, dataset {np.mean([r['fzD'] for r in R]):.3f}; ratio {_med([r['fzA'] / r['fzD'] for r in R])}; fore-aft there A {np.mean([r['fxA'] for r in R]):.3f}, dataset {np.mean([r['fxD'] for r in R]):.3f}")
        print("(b) LEVER at the peak-torque frame, mm (the dataset's from the lateral-malleolus marker moved to the joint centre by the subject's OpenSim model, tibia taken as upright)")
        mm = lambda k: 1000 * np.array([r[k] for r in R])
        print(f"    CoP ahead of the ankle: A {mm('dxA').mean():.1f}, dataset {mm('dxD').mean():.1f}, dataset x leg ratio {1000 * np.mean([r['dxD'] * r['ratio'] for r in R]):.1f}; ratio A / (leg ratio x dataset) {_med([r['dxA'] / (r['dxD'] * r['ratio']) for r in R])}")
        print(f"    ankle height above the floor: A {mm('hA').mean():.1f}, dataset {mm('hD').mean():.1f}, dataset x leg ratio {1000 * np.mean([r['hD'] * r['ratio'] for r in R]):.1f}")
        print(f"    force-weighted CoP-ankle lever over the stance: A {1000 * np.mean([r['lever_w_A'] for r in R]):.1f}, dataset x leg ratio {1000 * np.mean([r['lever_w_D'] * r['ratio'] for r in R]):.1f}")
        ar = np.array([r["ank_rel_A"] for r in R]); ad = np.array([r["ank_rel_D_scaled"] for r in R])
        print(f"    ankle relative to the hip midpoint (forward, up) at that frame: A {1000 * ar[:, 0].mean():.1f}, {1000 * ar[:, 1].mean():.1f}; dataset x leg ratio {1000 * ad[:, 0].mean():.1f}, {1000 * ad[:, 1].mean():.1f}; "
              f"difference A minus dataset {1000 * (ar - ad)[:, 0].mean():+.1f}, {1000 * (ar - ad)[:, 1].mean():+.1f} (sd {1000 * (ar - ad)[:, 0].std():.1f}, {1000 * (ar - ad)[:, 1].std():.1f})")
        prof = ankle_position_profile(S_list, manifest)
        print("    the same difference through the stride (A's ankle relative to the hip midpoint minus leg ratio x the dataset's), mm forward / up, mean (sd) over strides and limbs, by tenth of the stride:")
        print("      " + "  ".join(f"{10 * b + 5}%: {1000 * p[0][0]:+.0f}/{1000 * p[0][1]:+.0f} ({1000 * p[1][0]:.0f}/{1000 * p[1][1]:.0f})" for b, p in enumerate(prof)))
        print(f"    CoP relative to the hip midpoint, A minus leg ratio x dataset (forward): mean {1000 * np.mean([r['cop_rel_gap_x'] for r in R]):.3f} mm, max |.| {1000 * np.max(np.abs([r['cop_rel_gap_x'] for r in R])):.3f} mm")
        print(f"    realised reach (largest hip-midpoint-to-ankle distance in the sagittal plane) A / dataset {_med([r['reach_A'] / r['reach_D'] for r in R])} against the leg ratio {_med([r['ratio'] for r in R])}")
        la = leg_angle_offsets(S_list, c, manifest)
        print("    leg orientation, A minus the dataset (forward-positive angle from the vertical, degrees; mean, sd over every frame, then by tenth of the stride): "
              + "; ".join(f"{seg} {m:+.2f} ({sd:.2f}) [" + " ".join(f"{v:+.1f}" for v in by) + "]" for seg, (m, sd, by) in la.items()))
        print("(c) TERMS of A's ankle torque at that frame, N m/kg (the sign of the torque is taken as positive)")
        print(f"    total {np.mean([r['tA'] for r in R]):.3f} = vertical-force term {np.mean([r['vert_A'] for r in R]):.3f} + horizontal-force term {np.mean([r['horiz_A'] for r in R]):.3f} + foot weight and inertia {np.mean([r['inert_A'] for r in R]):+.4f}")
        print(f"    foot weight and inertia: largest |term| anywhere in the stance {np.mean([r['inert_max_A'] for r in R]):.3f} N m/kg = {100 * np.mean([r['inert_max_A'] / r['tA'] for r in R]):.1f}% of the peak torque")
        print(f"    the dataset: inverse-dynamics torque {np.mean([r['tD'] for r in R]):.3f}; from its plate force and markers {np.mean([r['gD'] for r in R]):.3f}; the remainder (its distal inertia plus whatever the markers miss) {np.mean([r['inert_D'] for r in R]):+.3f}")
        print("    gain factors, product = A's peak-frame torque over the dataset's (inertia: A total over A's ground term; lever: A's ground term over the same with the dataset's geometry scaled by the leg ratio;")
        print("    force: that over the leg ratio times the dataset's own ground term; data_closure: the dataset's marker-and-plate ground term over its inverse-dynamics torque)")
        _chain_lines(R, "ankle")
        print("(d) THE FOOT-FRAME CoP MAPPING (T3b step 0c), A_filtered against the dataset per kg, both limbs and every stride; the hip-reference rows are the mapping in force")
        stems = ("hip_fe", "knee", "ankle_pdflex", "hip_aa")
        for mode in ("hip_reference", "foot_frame"):
            _print_fit_table(f"  cop_mode {mode}", _fit_rows(runs[mode], c, manifest, stems))
        Rf = [limb_record(S, side, "ankle_pdflex", c, manifest) for S in runs["foot_frame"] for side in ("right", "left")]
        _chain_lines(Rf, "ankle, foot-frame mapping")
        bg = body_geometry(c, manifest, speed)
        f_, s_ = bg["freyja"], bg["subjects"]
        print(f"    body geometry, mm: Freyja at stand_static: ankle {1000 * f_['ankle_height']:.1f} above the floor, {1000 * f_['ankle_to_front']:.1f} to the front of the foot box and {1000 * f_['ankle_to_rear']:.1f} to its rear, hip half separation {1000 * f_['hip_half_separation']:.1f}; "
              f"the {len(manifest['subjects'])} subjects, as measured and times their leg ratio: ankle height {1000 * s_['ankle_height']:.1f} / {1000 * s_['ankle_height_scaled']:.1f}, ankle to toe-tip marker {1000 * s_['ankle_to_toe']:.1f} / {1000 * s_['ankle_to_toe_scaled']:.1f}, hip half separation {1000 * s_['hip_half_separation']:.1f} / {1000 * s_['hip_half_separation_scaled']:.1f}")
        sm = bg["segment_mass_fraction"]
        print("    leg segment masses as a fraction of body mass (thigh or femur, shank or tibia, foot with talus and toes): Freyja "
              + " ".join(f"{v:.4f}" for v in sm["freyja"]) + "; the subjects' OpenSim models (mean of 17) " + " ".join(f"{v:.4f}" for v in sm["subjects"]))
        print(f"(d2) THE STAND POSE'S PITCH: the model's root orientation is R_stand times the dataset's pelvis rotation (retarget.py), and stand_static's root pitch is {sp_deg:+.3f} deg (forward lean positive; its ankle joint is +2.608).")
        print(f"     A run with the existing pitch-offset knob at {-sp_deg:+.3f} deg (the spec's value is untouched), hip-reference mapping, everything else as above:")
        _print_fit_table("  cop_mode hip_reference, pitch offset cancelling the stand pose's pitch", _fit_rows(runs["stand_pitch_removed"], c, manifest, stems))
        Rp = [limb_record(S, side, "ankle_pdflex", c, manifest) for S in runs["stand_pitch_removed"] for side in ("right", "left")]
        _chain_lines(Rp, "ankle, stand pitch cancelled")
        lap = leg_angle_offsets(runs["stand_pitch_removed"], c, manifest)
        print("    leg orientation, A minus the dataset: " + "; ".join(f"{seg} {m:+.2f} ({sd:.2f})" for seg, (m, sd, by) in lap.items()))
        arp, adp = (np.array([r[k] for r in Rp]) for k in ("ank_rel_A", "ank_rel_D_scaled"))
        print(f"    ankle relative to the hip midpoint at the peak-torque frame, A minus leg ratio x dataset (forward, up): {1000 * (arp - adp)[:, 0].mean():+.1f}, {1000 * (arp - adp)[:, 1].mean():+.1f} mm; "
              f"CoP ahead of the ankle: A {1000 * np.mean([r['dxA'] for r in Rp]):.1f} mm against {1000 * np.mean([r['dxD'] * r['ratio'] for r in Rp]):.1f}; ankle height A {1000 * np.mean([r['hA'] for r in Rp]):.1f} mm against {1000 * np.mean([r['hD'] * r['ratio'] for r in Rp]):.1f}")
        for stem in ("ankle_pdflex", "hip_fe", "hip_aa"):
            ts = term_slopes(runs["stand_pitch_removed"], c, manifest, stem)
            print(f"    {stem:13s} slopes by term: " + "; ".join(f"{k} {v['slope']:.3f}" for k, v in ts.items()))
        print("(e) ACROSS SUBJECTS: the correlation of each subject's ankle slope (A on the dataset, per kg, both limbs and every stride) with a subject quantity; n = subjects, interval 95% (Fisher)")
        slope = {u: v for u, v in _fit_rows(S_list, c, manifest, ("ankle_pdflex",))["ankle_pdflex"][1].items()}
        by = {}
        for S in S_list:
            by.setdefault(S["subject"], S)
        foot_len = {}
        for u in slope:
            z = gait._subject_arrays(REPO / "data" / "camargo2021" / "processed", u)
            fm = z[f"{speed}_foot_markers"][:, :gait.N_FRAMES]
            st = z[f"{speed}_fp"][:, :, :gait.N_FRAMES, 6] >= gaitloads.STANCE_FLAG
            foot_len[u] = float(np.mean([np.linalg.norm((fm[n, :, 0, 1] - fm[n, :, 0, 0])[:, [0, 2]], axis=-1)[st[n, 0]].mean() for n in range(len(fm))]))
        xs = {"leg-length ratio": {u: by[u]["leg_ratio"] for u in slope}, "mass ratio": {u: by[u]["mass_ratio"] for u in slope}, "foot length (heel to toe-tip marker, m)": foot_len,
              "mean pelvis pitch (deg, anterior +)": {u: manifest["subjects"][u]["walking_pelvis_pitch_deg"][speed] for u in slope},
              "ankle lever factor": subject_values(R, lambda r: r["factors"]["lever"] if r["factors"] else np.nan),
              "ankle height A minus dataset x ratio (m)": subject_values(R, lambda r: r["hA"] - r["hD"] * r["ratio"]),
              "ankle-forward A minus dataset x ratio (m)": subject_values(R, lambda r: r["ank_rel_A"][0] - r["ank_rel_D_scaled"][0])}
        for name, r_, lo, hi in correlations(slope, xs):
            print(f"    {name:44s} r {r_:+.2f}  [{lo:+.2f}, {hi:+.2f}]")
        print("(f) THE SAME CHAIN for the hip joints (the hip joint centre from the pelvis pose and the subject's OpenSim hip offsets, the pelvis taken as not rolled or yawed)")
        for stem in ("hip_fe", "hip_aa"):
            Rh = recs[stem]
            _chain_lines(Rh, stem)
            print(f"    A's torque at that frame {np.mean([r['tA'] for r in Rh]):.3f} N m/kg = vertical-force term {np.mean([r['vert_A'] for r in Rh]):.3f} + horizontal-force term {np.mean([r['horiz_A'] for r in Rh]):.3f} + distal weight and inertia {np.mean([r['inert_A'] for r in Rh]):+.3f}; "
                  f"the dataset's {np.mean([r['tD'] for r in Rh]):.3f}, its plate-and-marker ground term {np.mean([r['gD'] for r in Rh]):.3f}, remainder {np.mean([r['inert_D'] for r in Rh]):+.3f}")
            key = "dx" if stem == "hip_fe" else "dy"
            print(f"    CoP-to-hip distance at that frame, {'fore-aft' if stem == 'hip_fe' else 'lateral'}: A {1000 * np.mean([abs(r[key + 'A']) for r in Rh]):.1f} mm, dataset x leg ratio "
                  f"{1000 * np.mean([abs(r[key + 'D'] * r['ratio']) for r in Rh]):.1f} mm; hip height above the floor: A {1000 * np.mean([r['hA'] for r in Rh]):.0f} mm, dataset x leg ratio {1000 * np.mean([r['hD'] * r['ratio'] for r in Rh]):.0f} mm")
        print("    THE SLOPE OF A ON THE DATASET by term (per kg, frames pooled over every stride and limb; slope, correlation, rms of A / rms of the dataset in N m/kg); the remainder is A's distal weight and inertia against the dataset's inverse-dynamics torque minus its plate-and-marker ground term")
        for stem in ("ankle_pdflex", "hip_fe", "hip_aa"):
            ts = term_slopes(S_list, c, manifest, stem)
            print(f"    {stem:13s} " + "; ".join(f"{k} {v['slope']:.3f}, {v['corr']:.3f}, {v['rms_a']:.3f}/{v['rms_d']:.3f}" for k, v in ts.items()))


if __name__ == "__main__":  # python sim/scripts/ankle_gain.py extract AB06 [out_dir]
    if len(sys.argv) >= 3 and sys.argv[1] == "extract":
        out = Path(sys.argv[3]) if len(sys.argv) > 3 else REPO / "data" / "camargo2021" / "processed" / "ankle_lat"
        print(sys.argv[2], extract_subject(sys.argv[2], out), flush=True)
