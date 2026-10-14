"""
The tracked gait extract (Stage 2b T3): sim/benchmarks/gait_extract.json, schema gait-extract/1 (docs/schemas/gait-extract-1.schema.json).

`sim/runs/ENVELOPE.md` used to read the newest untracked sim/gait/*/gait.json, so it could not be regenerated from a clean clone. The extract
holds exactly what the envelope's gait section prints, stamped like sim/benchmarks/walk_reference.json, and `fy runs envelope` reads it.

    fy gait <spec> --write-extract       a full run, then the extract from its record
    fy gait <spec> --extract-only        the extract from the newest existing record of that spec (no run)

It holds four things:
  results      per speed and trunk mode: stride counts, band verdicts, pooled agreement, and for every leg joint and method the 95th percentile and
               maximum of peak torque, speed, positive power and regeneration under each exclusion set the record has (all, without_offset,
               without_pitch_flagged); the joints above the pelvis for method B; the trunk peak angles and the hip extension of the retargeted record.
  lumbosacral  the lumbosacral lateral and axial joints for the three trunk modes (rigid, counter_rotate, first_harmonic at the T3c.2 median
               gain and lag, with the four quartile corners as the spread), over every subject-stride; the code is the T9.1 diagnostic's, moved here.
  a_filtered_sagittal  per speed and limb (and both limbs pooled per stem): the dataset's own peak moment scaled to Freyja (the sizing basis of the
               stage 2b brief), the OLS slope of A_filtered against the dataset per kg, and the ratio of A's mean peak per kg to the dataset's.
  hip_demand   peak hip extension from the vertical and relative to the pelvis (the dataset's inverse kinematics, no retargeting), with the median
               posterior pelvic tilt.

The functions that reduce rows to tables are pure and tested on synthetic input; the `compute_*` functions need the model and the processed arrays.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import gait  # noqa: E402
import runrecord  # noqa: E402

REPO = gait.REPO
EXTRACT_FILE = REPO / "sim" / "benchmarks" / "gait_extract.json"
SCHEMA_FILE = REPO / "docs" / "schemas" / "gait-extract-1.schema.json"
SCHEMA = "gait-extract/1"
GENERATED_BY = "sim/scripts/gait_extract.py (fy gait --write-extract)"
INPUTS = ["sim/scenarios/gait/walk_treadmill.yaml", "data/camargo2021/manifest.json", "sim/models/freyja.xml"]
SETS = ("all", "without_offset", "without_pitch_flagged")  # the exclusion sets, in the record's naming
SET_SUFFIX = {"all": "", "without_offset": "_without_offset", "without_pitch_flagged": "_without_pitch_flagged"}
JOINT_METRICS = ("peak_torque_nm", "peak_speed_rad_s", "peak_power_pos_w", "peak_regeneration_w")


# ------------------------------------------------------------------------------ the T9.1 lumbosacral computation (moved from gait_diag.py)

def joint_metrics(angle_rad, qvel, tau) -> dict:
    """Peak angle (deg), torque, speed and the positive and regenerative (magnitude of the most negative) power over one stride."""
    angle_rad, qvel, tau = (np.asarray(v, float) for v in (angle_rad, qvel, tau))
    p = tau * qvel
    return {"peak_angle_deg": float(np.degrees(np.abs(angle_rad).max())), "peak_torque_nm": float(np.abs(tau).max()), "peak_speed_rad_s": float(np.abs(qvel).max()),
            "peak_power_pos_w": float(p.max()), "peak_regen_w": float(max(0.0, -p.min()))}


def distribution(values) -> dict:
    v = np.asarray(values, float)
    return {"median": float(np.median(v)), "p95": float(np.percentile(v, 95)), "max": float(v.max())}


def quartile_corners(d) -> list:
    """The four (gain, lag) pairs that pair each gain quartile with each lag quartile of one axis's {median, q1, q3}."""
    return [(d[g][0], d[l][1]) for g in ("q1", "q3") for l in ("q1", "q3")]


LSJ = ("lsj_lat", "lsj_ax")
VARIANTS = ("rigid", "counter_rotate", "first_harmonic median", "first_harmonic q1 gain, q1 lag", "first_harmonic q1 gain, q3 lag",
            "first_harmonic q3 gain, q1 lag", "first_harmonic q3 gain, q3 lag")
LSJ_METRICS = ("peak_angle_deg", "peak_torque_nm", "peak_speed_rad_s", "peak_power_pos_w", "peak_regen_w")


def _variant_kwargs(variant: str, speed: str) -> dict:
    """Cycle keyword arguments for a variant name: rigid, counter_rotate, "first_harmonic median" or "first_harmonic q1 gain, q3 lag"."""
    import re
    import retarget
    if variant in ("rigid", "counter_rotate"):
        return {"trunk": variant}
    d = retarget.FIRST_HARMONIC_DEFAULTS[speed]
    if variant.endswith("median"):
        gq = lq = "median"
    else:
        gq, lq = re.fullmatch(r"first_harmonic (q[13]) gain, (q[13]) lag", variant).groups()
    return {"trunk": "first_harmonic", "trunk_gain": tuple(d[ax][gq][0] for ax in ("roll", "yaw")), "trunk_lag_deg": tuple(d[ax][lq][1] for ax in ("roll", "yaw"))}


def _pool(fn, tasks, workers):
    if workers <= 1 or len(tasks) < 8:
        return [fn(t) for t in tasks]
    from concurrent.futures import ProcessPoolExecutor
    with ProcessPoolExecutor(max_workers=workers) as ex:
        return list(ex.map(fn, tasks, chunksize=8))


def _lsj_task(task: dict) -> dict:
    """One subject-stride, one trunk variant: the lumbosacral lateral and axial joints' metrics. The joint torque is the joint row of
    qfrc_inverse: the ground wrench has no columns above the pelvis, so it is the same for every method."""
    import dynamics
    import retarget
    c = gait._ctx(task["model_path"])
    z = gait._subject_arrays(task["processed"], task["subject"])
    sp, i = task["speed"], task["index"]
    sub = task["subject_info"]
    hip = sub.get("hip_in_pelvis_os_m")
    cyc = retarget.Cycle(c.model, c.mapping, c.stand, z[f"{sp}_ik"][i], float(z[f"{sp}_duration_s"][i]), retarget.leg_length_ratio(c.model, sub["height_m"]),
                         cutoff_hz=retarget.CUTOFF_HZ, root_rule="pelvis_dataset", hip_in_pelvis_os=hip, root_ref="hip_midpoint" if hip is not None else "pelvis_origin",
                         pitch_mean="measured", **_variant_kwargs(task["variant"], sp))
    q, qd, qdd = cyc.grid()
    nf = gait.N_FRAMES
    qfrc = np.array([dynamics.inverse_frame(c.model, q[k], qd[k], qdd[k]) for k in range(nf)])
    out = {}
    for j in LSJ:
        adr, dof = c.hinge[j]
        out[j] = joint_metrics(q[:nf, adr], qd[:nf, dof], qfrc[:, dof])
    return {"subject": task["subject"], "speed": sp, "variant": task["variant"], "metrics": out}


def lsj_tasks(speeds, cap=0, manifest=None) -> list:
    """Every subject-stride x variant cycle of the speeds (the first `cap` strides of each subject when cap is non-zero)."""
    manifest = manifest or json.loads((REPO / "data/camargo2021/manifest.json").read_text(encoding="utf-8"))
    tasks = []
    for sp in speeds:
        for s in manifest["subjects"]:
            for i in range(manifest["subjects"][s]["strides"][sp]):
                if cap and i >= cap:
                    continue
                for v in VARIANTS:
                    tasks.append({"model_path": str(gait.simrun.MODEL_FILE), "processed": str(REPO / "data/camargo2021/processed"), "subject": s, "speed": sp,
                                  "index": i, "subject_info": manifest["subjects"][s], "variant": v})
    return tasks


def lsj_table(rows, speeds, variants=VARIANTS, joints=LSJ) -> dict:
    """{speed: {joint: {variant: {metric: {median, p95, max}}}}} across the subject-strides of `rows` (as `_lsj_task` returns them)."""
    out = {}
    for sp in speeds:
        out[sp] = {}
        for j in joints:
            out[sp][j] = {}
            for v in variants:
                R = [r["metrics"][j] for r in rows if r["speed"] == sp and r["variant"] == v]
                out[sp][j][v] = {k: distribution([x[k] for x in R]) for k in R[0]}
    return out


def compute_lumbosacral(speeds, cap=0, workers=1) -> tuple:
    """(table, rows): the lumbosacral rows of every variant over every subject-stride of the speeds."""
    rows = _pool(_lsj_task, lsj_tasks(speeds, cap), workers)
    return lsj_table(rows, speeds), rows


# ------------------------------------------------------------------------------ A_filtered against the dataset (moved from gait_diag.py, T2 and T4)

def peak_stats(values) -> dict:
    v = np.asarray(values, float)
    return {"mean": float(v.mean()), "median": float(np.median(v)), "p95": float(np.percentile(v, 95)), "max": float(v.max())}


def ols(x, y):
    """Ordinary-least-squares slope and intercept of y on x."""
    x, y = np.asarray(x, float), np.asarray(y, float)
    slope = float(np.cov(x, y, bias=True)[0, 1] / x.var())
    return slope, float(y.mean() - slope * x.mean())


A_STEMS = ("hip_fe", "knee", "ankle_pdflex")
A_JOINTS = tuple(f"{s}_{side}" for s in A_STEMS for side in ("right", "left"))


def a_sagittal_rows(S, mass) -> dict:
    """The sagittal rows of A_filtered against the dataset, for each limb joint and for each stem with both limbs pooled. S is a list of strides,
    each {subject, leg_ratio, tau: {joint: N m per frame}, data: {joint: the dataset's moment per kg of the subject per frame}}. For each row:
    `scaled_peak_nm` the dataset's own peak moment scaled to Freyja (per-kg peak x Freyja's mass x the stride's leg-length ratio: force by the mass
    ratio, lever arm by the leg ratio) as {mean, p95, max} over strides; `ols_slope` the slope of A per kg of Freyja on the dataset per kg over every
    pooled frame; `peak_ratio` the mean peak of A per kg over the mean peak of the dataset per kg."""
    groups = {j: [j] for j in A_JOINTS}
    groups.update({stem: [f"{stem}_right", f"{stem}_left"] for stem in A_STEMS})
    out = {}
    for name, js in groups.items():
        data_peak = np.array([np.abs(s["data"][j]).max() for s in S for j in js])
        a_peak = np.array([np.abs(s["tau"][j]).max() / mass for s in S for j in js])
        scale = np.array([s["leg_ratio"] for s in S for _ in js])
        scaled = peak_stats(data_peak * mass * scale)
        slope = ols(np.concatenate([np.asarray(s["data"][j], float) for s in S for j in js]),
                    np.concatenate([np.asarray(s["tau"][j], float) / mass for s in S for j in js]))[0]
        out[name] = {"scaled_peak_nm": {k: scaled[k] for k in ("mean", "p95", "max")}, "ols_slope": slope, "peak_ratio": float(a_peak.mean() / data_peak.mean())}
    return out


def a_filtered_strides(speed, workers, ignore_mapping_offset=False):
    """Every subject-stride at one speed through method A_filtered (rigid trunk: A's leg torques do not depend on the mode) with the per-frame
    joint torques kept, the dataset's own moment per kg of the subject, and the scaling factors of the stride. Returns (strides, Freyja's mass, spec)."""
    import retarget
    spec = gait.load_spec("walk_treadmill")
    processed = REPO / spec["dataset"]["processed"]
    manifest = json.loads((REPO / spec["dataset"]["manifest"]).read_text(encoding="utf-8"))
    tasks = gait._tasks(spec, manifest, gait.simrun.MODEL_FILE, processed, ["A_filtered"], float(spec["smoothing"]["cutoff_hz"]),
                        float(spec["pelvis_pitch_offset_deg"]), None, False, False, False, trunk="rigid")
    tasks = [dict(t, keep_torque=True, ignore_mapping_offset=ignore_mapping_offset) for t in tasks if t["speed"] == speed]
    rows = gait._run_tasks(tasks, workers)
    c = gait._ctx(gait.simrun.MODEL_FILE)
    out = []
    for r in rows:
        info = manifest["subjects"][r["subject"]]
        idm = gait._subject_arrays(processed, r["subject"])[f"{speed}_id"][r["index"]]
        d = {"subject": r["subject"], "leg_ratio": retarget.leg_length_ratio(c.model, info["height_m"]), "tau": r["torque"]["A_filtered"], "data": {}}
        for j, spec_j in c.mapping["joints"].items():
            d["data"][j] = spec_j["sign"] * idm[:gait.N_FRAMES, gait.ic.ID_CHANNELS.index(spec_j["dataset"] + "_moment")] / info["mass_kg"]
        out.append(d)
    return out, c.mass, spec


def compute_a_sagittal(speeds, workers=1) -> dict:
    return {sp: a_sagittal_rows(*a_filtered_strides(sp, workers)[:2]) for sp in speeds}


# ------------------------------------------------------------------------------ hip extension demand (moved from gait_diag.py, T1)

def thigh_world_deg(hip_flexion_deg, pelvis_list_deg):
    """Thigh angle from the vertical, flexion positive (planar): the hip angle minus the pelvis's anterior pitch, and anterior pitch is minus `pelvis_list`."""
    return np.asarray(hip_flexion_deg, float) + np.asarray(pelvis_list_deg, float)


def peak_extension_deg(right, left) -> float:
    """Peak hip extension of one stride in degrees, extension positive: minus the minimum hip flexion over both limbs (negative if never extended)."""
    return float(-min(np.min(right), np.min(left)))


def stride_hip_extension(hip_r, hip_l, pelvis_list) -> dict:
    """One stride of the dataset's inverse kinematics (degrees): peak extension relative to the pelvis, from the vertical, and the mean pelvis_list."""
    return {"hip_raw": peak_extension_deg(hip_r, hip_l), "thigh_world": peak_extension_deg(thigh_world_deg(hip_r, pelvis_list), thigh_world_deg(hip_l, pelvis_list)),
            "pitch": float(np.mean(pelvis_list))}


def hip_demand_rows(strides) -> dict:
    """strides: [{hip_r, hip_l, list}] arrays in degrees. {vertical_deg, pelvis_relative_deg: {median, p95, max}, posterior_pelvic_tilt_median_deg}."""
    r = [stride_hip_extension(s["hip_r"], s["hip_l"], s["list"]) for s in strides]
    return {"vertical_deg": distribution([x["thigh_world"] for x in r]), "pelvis_relative_deg": distribution([x["hip_raw"] for x in r]),
            "posterior_pelvic_tilt_median_deg": float(np.median([x["pitch"] for x in r]))}


def compute_hip_demand(speeds) -> dict:
    spec = gait.load_spec("walk_treadmill")
    processed = REPO / spec["dataset"]["processed"]
    manifest = json.loads((REPO / spec["dataset"]["manifest"]).read_text(encoding="utf-8"))
    nm = gait.ic.IK_CHANNELS
    out = {}
    for sp in speeds:
        strides = []
        for s in manifest["subjects"]:
            ik = gait._subject_arrays(processed, s)[f"{sp}_ik"]
            for i in range(len(ik)):
                ch = lambda n: ik[i][:, nm.index(n)]
                strides.append({"hip_r": ch("hip_flexion_r"), "hip_l": ch("hip_flexion_l"), "list": ch("pelvis_list")})
        out[sp] = hip_demand_rows(strides)
    return out


# ------------------------------------------------------------------------------ the extract

def _peak_p95_max(cell):
    """{set: {p95, max}} for each exclusion set the record's cell has (the record written before the pitch flags has two, a later one three)."""
    return {s: {"p95": cell[s]["p95"], "max": cell[s]["max"]} for s in SETS if s in cell}


def _pooled_agreement(d) -> dict:
    """{method: {stem: {set: {corr, rms_pct_ptp}}}}: both limbs pooled by the mean, as the envelope and the band pool them."""
    out = {}
    for m, aj in d["agreement"].items():
        out[m] = {}
        for stem in sorted({j[:-6] for j in aj if j.endswith("_right")}):
            a = [aj[f"{stem}_{side}"] for side in ("right", "left")]
            sets = [s for s in SETS if all("corr" + SET_SUFFIX[s] in x for x in a)]
            out[m][stem] = {s: {"corr": float(np.mean([x["corr" + SET_SUFFIX[s]] for x in a])), "rms_pct_ptp": float(np.mean([x["rms_pct_ptp" + SET_SUFFIX[s]] for x in a]))}
                            for s in sets}
    return out


def assemble(rec: dict, lumbosacral: dict, a_sagittal: dict, hip_demand: dict) -> dict:
    """The extract of a gait record (gait-summary/1) and the three computed tables. Pure: the same inputs give the same bytes."""
    results = {}
    for sp, by_mode in rec["results"].items():
        results[sp] = {}
        for mode, d in by_mode.items():
            joints = {}
            for j, by_method in d["joints"].items():
                above = not (j.endswith("_right") or j.endswith("_left"))
                joints[j] = {m: {k: _peak_p95_max(cell[k]) for k in JOINT_METRICS} for m, cell in by_method.items() if not above or m == "B"}
            results[sp][mode] = {
                "n_strides": d["n_strides"], "n_strides_without_offset": d["n_strides_without_offset"],
                **({"n_strides_without_pitch_flagged": d["n_strides_without_pitch_flagged"]} if "n_strides_without_pitch_flagged" in d else {}),
                "band": d["band"], "agreement": _pooled_agreement(d), "joints": joints,
                "trunk_peak_deg": d["trunk_peak_deg"], "hip_extension": d["hip_extension"]}
    spec = rec["spec"]
    body = {
        "generated_by": GENERATED_BY, "inputs": INPUTS, "schema": SCHEMA,
        "gait_id": rec["gait_id"], "gait_version": rec.get("gait_version"), "git_commit": rec["git_commit"], "git_dirty": rec["git_dirty"], "diff_sha256": rec.get("diff_sha256"),
        "snapshot_sha256": rec["snapshot_sha256"], "model_sha256": rec["model_sha256"], "spec_sha256": rec["spec_sha256"] if "spec_sha256" in rec else gait._sha(spec),
        "dataset_manifest_sha256": rec.get("dataset_manifest_sha256", ""),
        "attribution": rec.get("attribution", gait.ATTRIBUTION),
        "spec": {"name": spec["name"], "offset_subjects": list(spec["offset_subjects"]), "pitch_flag_subjects": list(spec.get("pitch_flag_subjects", [])),
                 "speeds_mps": list(spec["speeds_mps"])},
        "assumption": rec["assumptions"][0],
        "trunk": list(rec["trunk"]),
        "subjects": {"count": len(rec["subjects"]), "ids": sorted(rec["subjects"])},
        "results": results, "lumbosacral": lumbosacral, "a_filtered_sagittal": a_sagittal, "hip_demand": hip_demand,
    }
    return gait._round(body)


def dumps(extract) -> str:
    return runrecord.dumps(extract)


def validate(extract) -> None:
    import jsonschema
    jsonschema.validate(extract, json.loads(SCHEMA_FILE.read_text(encoding="utf-8")))


def build(rec: dict, workers=1) -> dict:
    """The extract of a gait record: the computed tables are those of every subject-stride of the spec's speeds."""
    speeds = [str(s) for s in rec["spec"]["speeds_mps"]]
    lsj, _ = compute_lumbosacral(speeds, 0, workers)
    return assemble(rec, lsj, compute_a_sagittal(speeds, workers), compute_hip_demand(speeds))


def write_extract(rec: dict, path=None, workers=1) -> Path:
    extract = build(rec, workers)
    validate(extract)
    path = Path(path or EXTRACT_FILE)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(dumps(extract))
    return path


def newest_record(spec_name, gait_dir=None) -> dict:
    """The newest sim/gait/*/gait.json of a spec, by id."""
    found = sorted((p for p in Path(gait_dir or gait.GAIT_DIR).glob(f"*/gait.json") if p.parent.name.endswith(f"-{spec_name}")), key=lambda p: p.parent.name)
    if not found:
        raise gait.GaitError(f"no gait record for {spec_name}: run `fy gait {spec_name}` first")
    return json.loads(found[-1].read_text(encoding="utf-8"))
