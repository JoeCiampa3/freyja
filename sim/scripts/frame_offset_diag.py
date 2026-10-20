"""
Stage 2g T1 experiment (report only): the effect of the pelvis frame offset (`pelvis_frame_offset: none | measured`, decisions/0004) on the 1.4 m/s walking loads.

    python sim/scripts/frame_offset_diag.py [--speed 1.4] [--workers N] [--trunk rigid] [--json OUT]

Runs every subject-stride of the walk_treadmill spec's subjects at one speed with both settings, from the working tree as it is (run it on a clean commit and say
which), and prints side by side: the band table of A_filtered, B and H (correlation, RMS as a percentage of the dataset's peak-to-peak and RMS in N m, hip,
knee and ankle), the 95th percentile and maximum peak torque per joint, B's centre-of-pressure offset from the measured one in single support (median and
quartiles, hip-referenced, model axes: negative x is behind), the peak hip extension of the model's hinge, the joints above the pelvis, and the hip centre against
the lumbosacral joint in a standing frame. It writes no record and changes nothing tracked.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import mujoco
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import gait  # noqa: E402

METHODS = ("A_filtered", "B", "H")
STEMS = ("hip_fe", "knee", "ankle_pdflex")
ABOVE = ("lsj_fe", "lsj_lat", "lsj_ax", "tj_fe", "cj_fe")


def run_mode(mode, speed, workers, trunk):
    spec = dict(gait.load_spec("walk_treadmill"), pelvis_frame_offset=mode, speeds_mps=[float(speed)])
    manifest = json.loads((gait.REPO / spec["dataset"]["manifest"]).read_text(encoding="utf-8"))
    processed = gait.REPO / spec["dataset"]["processed"]
    tasks = gait._tasks(spec, manifest, gait.simrun.MODEL_FILE, processed, list(METHODS), float(spec["smoothing"]["cutoff_hz"]), float(spec["pelvis_pitch_offset_deg"]),
                        None, False, True, False, trunk=trunk)
    tasks = [dict(t, keep_torque=True) for t in tasks]
    return manifest, processed, gait._run_tasks(tasks, workers), spec


def summarise(manifest, processed, rows, spec):
    c = gait._ctx(gait.simrun.MODEL_FILE)
    sp = str(spec["speeds_mps"][0])
    out = {"n": len(rows), "agreement": {}, "peak": {}, "cop_x_mm": {}, "hip_ext": {}, "above": {}}
    for m in METHODS:
        for stem in STEMS:
            corr, pct, nm = [], [], []
            for r in rows:
                idm = gait._subject_arrays(processed, r["subject"])[f"{sp}_id"][r["index"]]
                mass = manifest["subjects"][r["subject"]]["mass_kg"]
                for side in ("right", "left"):
                    j = f"{stem}_{side}"
                    s = c.mapping["joints"][j]
                    data = s["sign"] * idm[:gait.N_FRAMES, gait.ic.ID_CHANNELS.index(s["dataset"] + "_moment")] / mass  # N m per kg of the subject
                    model = np.array(r["torque"][m][j])
                    corr.append(r["agree"][m][j]["corr"]); pct.append(r["agree"][m][j]["rms_pct_ptp"])
                    nm.append(float(np.sqrt(np.mean((model - data * c.mass) ** 2))))  # the dataset's moment per kg times Freyja's mass
            out["agreement"][f"{m}/{stem}"] = {"corr": float(np.mean(corr)), "rms_pct_ptp": float(np.mean(pct)), "rms_nm": float(np.mean(nm))}
        out["peak"][m] = {j: {"p95": float(np.percentile([r["peaks"][m][j]["peak_torque_nm"] for r in rows], 95)),
                              "max": float(max(r["peaks"][m][j]["peak_torque_nm"] for r in rows))} for j in [*c.joints[:len(c.mapping["joints"])], *ABOVE]}
    cop = np.array([e for r in rows for e in r["feas"]["cop_err_single"]]) if all("feas" in r for r in rows) else np.zeros((0, 2))
    if len(cop):
        out["cop_x_mm"] = {"median": float(np.median(cop[:, 0]) * 1000), "q1": float(np.percentile(cop[:, 0], 25) * 1000), "q3": float(np.percentile(cop[:, 0], 75) * 1000), "n": int(len(cop))}
    ext = np.array([r["hip_extension_deg"] for r in rows])
    out["hip_ext"] = {"median": float(np.median(ext)), "p95": float(np.percentile(ext, 95)), "max": float(ext.max()), "beyond_stop_fraction": float(np.mean(ext > c.hip_stop_deg))}
    return out


def standing_hip_vs_lsj(model, pitch_deg):
    """Hip centre minus the lumbosacral joint, world, mm (x ahead, z up), for a standing frame whose root is pitched forward by `pitch_deg` about the lateral axis."""
    d = mujoco.MjData(model)
    p = np.radians(pitch_deg)
    d.qpos[:] = model.qpos0
    d.qpos[3:7] = [np.cos(p / 2), 0.0, np.sin(p / 2), 0.0]
    mujoco.mj_kinematics(model, d)
    hip = 0.5 * (d.xpos[model.body("thigh_right").id] + d.xpos[model.body("thigh_left").id])
    lsj = d.xanchor[model.joint("lsj_fe").id]
    return ((hip - lsj) * 1000).tolist()


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[1])
    ap.add_argument("--speed", default="1.4")
    ap.add_argument("--workers", type=int, default=5)
    ap.add_argument("--trunk", default="rigid", choices=gait.TRUNK_MODES)
    ap.add_argument("--json")
    args = ap.parse_args(argv)
    res = {}
    for mode in gait.FRAME_OFFSETS:
        manifest, processed, rows, spec = run_mode(mode, args.speed, args.workers, args.trunk)
        res[mode] = summarise(manifest, processed, rows, spec)
        print(f"{mode}: {len(rows)} strides done", file=sys.stderr, flush=True)
    c = gait._ctx(gait.simrun.MODEL_FILE)
    tilt = [m["static_dumas_tilt_deg"] for m in manifest["subjects"].values()]
    pitch = [m["static_pelvis_pitch_deg"] for m in manifest["subjects"].values()]
    res["standing_hip_minus_lsj_mm"] = {"IK pelvis pitch, mean": standing_hip_vs_lsj(c.model, float(np.mean(pitch))),
                                        "Dumas tilt, mean": standing_hip_vs_lsj(c.model, float(np.mean(tilt)))}
    print(json.dumps(res, indent=1, sort_keys=True))
    if args.json:
        Path(args.json).write_text(json.dumps(res, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
