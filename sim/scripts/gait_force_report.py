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
    """Per stride: vertical peak ratio, per-hump peak ratios, shape error and correlation, fore-aft peak-to-peak ratio and
    correlation, of Freyja's force fb against the measured fm (both (101, 3))."""
    ph = np.linspace(0, 1, fb.shape[0])
    z, zm = fb[:, 2], fm[:, 2]
    h1, h2 = ph < 0.3, (ph >= 0.3) & (ph < 0.65)
    return {"peak_ratio": z.max() / zm.max(), "hump1_ratio": z[h1].max() / zm[h1].max(), "hump2_ratio": z[h2].max() / zm[h2].max(),
            "rms_pct_of_peak": 100 * np.sqrt(np.mean((z - zm) ** 2)) / zm.max(), "corr": np.corrcoef(z, zm)[0, 1],
            "ap_ptp_ratio": np.ptp(fb[:, 0]) / np.ptp(fm[:, 0]), "ap_corr": np.corrcoef(fb[:, 0], fm[:, 0])[0, 1]}


THRESH = {"peak_ratio": (0.85, 1.15), "ap_ptp_ratio": (0.85, 1.15), "corr": (0.85, 1.01), "ap_corr": (0.85, 1.01)}
CUTOFFS = (6.0, 8.0, 10.0, 12.0, 15.0)


def flags(stats):
    return ", ".join(f"{k} {'ok' if lo <= stats[k] <= hi else 'MISS'}" for k, (lo, hi) in THRESH.items())


def main():
    model = mujoco.MjModel.from_xml_path(str(REPO / "sim" / "models" / "freyja.xml"))
    stand = leanpose.solve_lean(model, 0.0, FEET).qpos
    mapping = yaml.safe_load((REPO / "sim/scenarios/gait/camargo_mapping.yaml").read_text())
    manifest = json.loads((REPO / "data/camargo2021/manifest.json").read_text())
    mass = float(model.body_mass.sum())
    print(f"Freyja mass {mass:.2f} kg; root rule pelvis_dataset; review thresholds: peak ratios 0.85 to 1.15, correlations >= 0.85")
    for speed in ("1.4", "1.6"):
        like = {c: [] for c in CUTOFFS}   # Freyja vs measured filtered identically
        raw = {c: [] for c in CUTOFFS}    # Freyja vs measured unfiltered
        meas_raw = {c: [] for c in CUTOFFS}  # filtered measured peak / raw measured peak
        curves = {"measured_raw": [], "measured_6Hz": [], "freyja_6Hz": []}
        subj, legr = [], []
        for s, d in manifest["subjects"].items():
            z = np.load(REPO / f"data/camargo2021/processed/{s}.npz")
            ratio = retarget.leg_length_ratio(model, d["height_m"])
            for i in range(len(z[f"{speed}_duration_s"])):
                T = float(z[f"{speed}_duration_s"][i])
                fm = measured_force_model(z[f"{speed}_fp"][i], mass / d["mass_kg"])
                subj.append(s); legr.append(ratio)
                for cut in CUTOFFS:
                    c = retarget.Cycle(model, mapping, stand, z[f"{speed}_ik"][i], T, ratio, cutoff_hz=cut)
                    q, qd, qdd = c.grid()
                    fb = np.array([dynamics.inverse_frame(model, q[k], qd[k], qdd[k])[:3] for k in range(q.shape[0])])
                    fmf = retarget.filter_cycle(fm, T, cut)
                    like[cut].append(compare(fb, fmf)); raw[cut].append(compare(fb, fm))
                    meas_raw[cut].append(fmf[:, 2].max() / fm[:, 2].max())
                    if cut == 6.0:
                        curves["measured_raw"].append(fm); curves["measured_6Hz"].append(fmf); curves["freyja_6Hz"].append(fb)
        subj, legr = np.array(subj), np.array(legr)
        keep = ~np.isin(subj, OFFSET_SUBJECTS)
        print(f"\n== {speed} m/s, {len(subj)} strides ({keep.sum()} without {OFFSET_SUBJECTS}) ==")
        for name, rows in (("LIKE FOR LIKE (measured filtered identically), 6 Hz", like[6.0]), ("RAW measured, 6 Hz kinematics", raw[6.0])):
            print(f"-- {name}")
            for label, mask in (("all", np.ones_like(keep)), ("without AB13, AB15", keep)):
                st = {k: float(np.array([r[k] for r in rows])[mask].mean()) for k in rows[0]}
                print(f"  {label:20s} " + "; ".join(f"{k} {v:.3f}" for k, v in st.items()))
                if label == "all":
                    print(f"  {'':20s} thresholds: {flags(st)}")
        print("-- ratio versus cutoff (all strides; measured filtered identically at each cutoff)")
        print("  cutoff  meas_filtered/raw_peak  like:peak_ratio  hump1  hump2  corr   ap_ptp_ratio  ap_corr  | raw:peak_ratio")
        for cut in CUTOFFS:
            m = {k: np.mean([r[k] for r in like[cut]]) for k in like[cut][0]}
            print(f"  {cut:5.0f}   {np.mean(meas_raw[cut]):.3f}                  {m['peak_ratio']:.3f}           {m['hump1_ratio']:.3f}  {m['hump2_ratio']:.3f}  {m['corr']:.3f}  {m['ap_ptp_ratio']:.3f}         {m['ap_corr']:.3f}    | {np.mean([r['peak_ratio'] for r in raw[cut]]):.3f}")
        print("-- mean force by phase (N)")
        idx = list(range(0, 101, 10))
        print("  phase          " + " ".join(f"{i:6d}" for i in idx))
        for comp, nm in ((2, "vertical"), (0, "fore-aft")):
            for key in ("measured_raw", "measured_6Hz", "freyja_6Hz"):
                cv = np.array(curves[key])
                print(f"  {nm[:4]} {key:13s}" + " ".join(f"{cv[:, i, comp].mean():6.0f}" for i in idx))
        # diagnostic 2: does the fore-aft shortfall per subject track the leg-length ratio?
        per = {}
        for s, r, row in zip(subj, legr, like[6.0]):
            per.setdefault(s, []).append((r, row["ap_ptp_ratio"]))
        xs = np.array([np.mean([a for a, _ in v]) for v in per.values()])
        ys = np.array([np.mean([b for _, b in v]) for v in per.values()])
        print(f"-- diagnostic: per-subject AP peak-to-peak ratio (6 Hz, like for like) vs leg-length ratio: corr {np.corrcoef(xs, ys)[0, 1]:.2f}, "
              f"slope {np.polyfit(xs, ys, 1)[0]:.2f} per unit ratio; subject range {ys.min():.2f} to {ys.max():.2f}")


if __name__ == "__main__":
    main()
