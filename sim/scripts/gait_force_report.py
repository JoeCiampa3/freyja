"""
Stage 2 T3 first report: Freyja's total ground force from her own CoM motion, m (a + g) (root force rows of inverse dynamics),
against the measured force scaled to her weight, for both root rules. The force depends on the kinematics alone, so this tests
the root trajectory before any moment error can hide it. Prints a summary; writes nothing.

    python sim/scripts/gait_force_report.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import mujoco
import numpy as np
import yaml

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "analysis"))
sys.path.insert(0, str(REPO / "sim" / "scripts"))
import dynamics  # noqa: E402
import leanpose  # noqa: E402
import retarget  # noqa: E402

FEET = {"foot_right": "ankle_pdflex_right", "foot_left": "ankle_pdflex_left"}
OFFSET_SUBJECTS = ("AB13", "AB15")  # subject-level ankle offsets (T0); every statistic is shown with and without them
LAB_TO_MODEL = np.array([[0, 0, -1], [-1, 0, 0], [0, 1, 0]], float)


def measured_force_model(fp, mass_ratio):
    """fp (2, 101, 7): total measured ground force in the model's axes (x anterior, y left, z up), scaled by mass_ratio."""
    f_lab = fp[0, :, 0:3] + fp[1, :, 0:3]
    return mass_ratio * (f_lab @ LAB_TO_MODEL.T)


def compare(fb, fm):
    """Per stride: peak vertical ratio, per-hump peak ratios, shape error and correlation (vertical), AP peak-to-peak ratio."""
    ph = np.linspace(0, 1, fb.shape[0])
    z, zm = fb[:, 2], fm[:, 2]
    h1, h2 = ph < 0.3, (ph >= 0.3) & (ph < 0.65)
    return {"peak_ratio": z.max() / zm.max(), "hump1_ratio": z[h1].max() / zm[h1].max(), "hump2_ratio": z[h2].max() / zm[h2].max(),
            "rms_pct_of_peak": 100 * np.sqrt(np.mean((z - zm) ** 2)) / zm.max(), "corr": np.corrcoef(z, zm)[0, 1],
            "ap_ptp_ratio": np.ptp(fb[:, 0]) / np.ptp(fm[:, 0]), "ap_corr": np.corrcoef(fb[:, 0], fm[:, 0])[0, 1]}


def main():
    model = mujoco.MjModel.from_xml_path(str(REPO / "sim" / "models" / "freyja.xml"))
    stand = leanpose.solve_lean(model, 0.0, FEET).qpos
    mapping = yaml.safe_load((REPO / "sim/scenarios/gait/camargo_mapping.yaml").read_text())
    manifest = json.loads((REPO / "data/camargo2021/manifest.json").read_text())
    mass = float(model.body_mass.sum())
    print(f"Freyja mass {mass:.2f} kg")
    for speed in ("1.4", "1.6"):
        rows = {r: [] for r in retarget.ROOT_RULES}
        curves = {r: [] for r in retarget.ROOT_RULES}
        meas = []
        subj = []
        for s, d in manifest["subjects"].items():
            z = np.load(REPO / f"data/camargo2021/processed/{s}.npz")
            ratio = retarget.leg_length_ratio(model, d["height_m"])
            tilt0 = float(z["static_pelvis_tilt_deg"])
            for i in range(len(z[f"{speed}_duration_s"])):
                fm = measured_force_model(z[f"{speed}_fp"][i], mass / d["mass_kg"])
                meas.append(fm); subj.append(s)
                for rule in retarget.ROOT_RULES:
                    c = retarget.Cycle(model, mapping, stand, z[f"{speed}_ik"][i], float(z[f"{speed}_duration_s"][i]), ratio,
                                       static_tilt_deg=tilt0, root_rule=rule)
                    q, qd, qdd = c.grid()
                    fb = np.array([dynamics.inverse_frame(model, q[k], qd[k], qdd[k])[:3] for k in range(q.shape[0])])
                    rows[rule].append(compare(fb, fm)); curves[rule].append(fb)
        subj = np.array(subj)
        keep = ~np.isin(subj, OFFSET_SUBJECTS)
        print(f"\n== {speed} m/s, {len(subj)} strides ({keep.sum()} without {OFFSET_SUBJECTS}) ==")
        for rule in retarget.ROOT_RULES:
            print(f"-- root rule {rule}")
            for label, mask in (("all", np.ones_like(keep)), ("without AB13, AB15", keep)):
                line = []
                for k in rows[rule][0]:
                    v = np.array([r[k] for r in rows[rule]])[mask]
                    line.append(f"{k} {v.mean():.3f} (sd {v.std():.3f})")
                print(f"  {label:20s} " + "; ".join(line))
        meas = np.array(meas)
        print("-- mean vertical force by phase (N), measured vs each rule:")
        idx = list(range(0, 101, 10))
        print("  phase     " + " ".join(f"{i:6d}" for i in idx))
        print("  measured  " + " ".join(f"{meas[:, i, 2].mean():6.0f}" for i in idx))
        for rule in retarget.ROOT_RULES:
            cv = np.array(curves[rule])
            print(f"  {rule[:9]:9s} " + " ".join(f"{cv[:, i, 2].mean():6.0f}" for i in idx))
        print("-- mean AP force by phase (N):")
        print("  measured  " + " ".join(f"{meas[:, i, 0].mean():6.0f}" for i in idx))
        for rule in retarget.ROOT_RULES:
            cv = np.array(curves[rule])
            print(f"  {rule[:9]:9s} " + " ".join(f"{cv[:, i, 0].mean():6.0f}" for i in idx))


if __name__ == "__main__":
    main()
