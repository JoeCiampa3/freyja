"""
Stage 2 T2 report: what retargeting does to every ingested stride, without clipping anything. Prints a summary; writes nothing.

    python sim/scripts/retarget_report.py [--cutoff 6]
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import mujoco
import numpy as np
import yaml

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "analysis"))
sys.path.insert(0, str(REPO / "sim" / "scripts"))
import leanpose  # noqa: E402
import retarget  # noqa: E402

FEET = {"foot_right": "ankle_pdflex_right", "foot_left": "ankle_pdflex_left"}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cutoff", type=float, default=retarget.CUTOFF_HZ)
    args = ap.parse_args()
    model = mujoco.MjModel.from_xml_path(str(REPO / "sim" / "models" / "freyja.xml"))
    stand = leanpose.solve_lean(model, 0.0, FEET).qpos
    mapping = yaml.safe_load((REPO / "sim/scenarios/gait/camargo_mapping.yaml").read_text())
    manifest = json.loads((REPO / "data/camargo2021/manifest.json").read_text())
    mass = float(model.body_mass.sum())
    print(f"Freyja mass {mass:.2f} kg; cutoff {args.cutoff} Hz")
    print("subject  mass_kg height_m sex  leg_ratio  strides(1.4/1.6)")
    for s, d in manifest["subjects"].items():
        print(f"{s}  {d['mass_kg']:7.2f} {d['height_m']:8.2f}  {d['sex']}   {retarget.leg_length_ratio(model, d['height_m']):.3f}     {d['strides']['1.4']}/{d['strides']['1.6']}")
    for speed in ("1.4", "1.6"):
        lim, met, gap, com, root = {}, {k: [] for k in ("stance_penetration_max_m", "stance_float_max_m", "swing_clearance_min_m", "stance_slip_rms_mps", "stance_slip_max_mps")}, [], [], []
        n = 0
        for s, d in manifest["subjects"].items():
            z = np.load(REPO / f"data/camargo2021/processed/{s}.npz")
            ratio = retarget.leg_length_ratio(model, d["height_m"])
            for i in range(len(z[f"{speed}_duration_s"])):
                c = retarget.Cycle(model, mapping, stand, z[f"{speed}_ik"][i], float(z[f"{speed}_duration_s"][i]), ratio, args.cutoff)
                qs = c.grid()[0]
                for k, v in retarget.limit_fraction(model, qs).items():
                    lim.setdefault(k, []).append(v)
                m = retarget.foot_metrics(model, c, z[f"{speed}_fp"][i][:, :, 6] > 0.5, float(speed))
                for k in met:
                    met[k].append(m[k])
                gap.append(np.abs(c.wrap_gap[:c._nj]).max())
                dd = mujoco.MjData(model)
                comz, comx, rootz = [], [], []
                for q in qs:
                    dd.qpos[:] = q; mujoco.mj_kinematics(model, dd); mujoco.mj_comPos(model, dd)
                    comx.append(dd.subtree_com[0][0] - q[0]); comz.append(dd.subtree_com[0][2]); rootz.append(q[2])
                com.append((np.ptp(comz), np.ptp(comx))); root.append(np.ptp(rootz))
                n += 1
        print(f"\n== {speed} m/s, {n} strides ==")
        print("fraction of frames outside the model limit (mean over strides; max over strides):")
        for k, v in sorted(lim.items()):
            if np.mean(v) > 0:
                print(f"  {k:20s} mean {np.mean(v):.3f}  max {np.max(v):.3f}  strides affected {np.mean(np.array(v) > 0):.2f}")
        print("  (joints not listed: no frame outside)")
        for k, v in met.items():
            v = np.array(v)
            print(f"{k:26s} mean {v.mean():8.4f}  95th {np.percentile(v, 95):8.4f}  max {v.max():8.4f}")
        print(f"dataset wrap gap (largest joint, deg): median {np.degrees(np.median(gap)):.2f}  max {np.degrees(np.max(gap)):.2f}")
        com = np.array(com)
        print(f"CoM vertical range m: mean {com[:,0].mean():.4f}; CoM x range rel pelvis m: mean {com[:,1].mean():.4f}; pelvis height range m: mean {np.mean(root):.4f}")


if __name__ == "__main__":
    main()
