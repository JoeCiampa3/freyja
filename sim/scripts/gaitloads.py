"""
Stage 2 T4: the measured ground reaction in Freyja's frame, for methods A and H.

The dataset's lab frame is x right, y up, z backward; the model's is x anterior, y left, z up (lab_to_model in
sim/scenarios/gait/camargo_mapping.yaml). Scaling, all documented in the gait record:
  force   times mass_ratio = Freyja's mass / the subject's mass (the force scales with weight)
  CoP     relative to the subject's pelvis (lab), times length_ratio (Freyja's leg length / the subject's) and cop_scale (a
          sensitivity knob, default 1), rotated to the model axes and added to the model's hip-centre midpoint
Method A applies the scaled force and CoP as measured. Method H keeps the measured CoPs and the measured share of the
vertical force between the feet but takes the total force from Freyja's own CoM motion (the root force rows of inverse
dynamics), so the force rows close by construction and only the moments leave a residual.
"""
from __future__ import annotations

import numpy as np

import retarget

VERSION = "1"
FEET = ("foot_right", "foot_left")
LAB_TO_MODEL = np.array([[0.0, 0.0, -1.0], [-1.0, 0.0, 0.0], [0.0, 1.0, 0.0]])
STANCE_FLAG = 0.5  # the ingested stance channel is 0 or 1


def measured_to_model(fp_frame, ref_lab, ref_xy, mass_ratio, length_ratio, cop_scale=1.0):
    """fp_frame (2, 7) [Fx Fy Fz CoPx CoPy CoPz stance] for the right and left plate in the lab frame; pelvis_lab (3,) the
    subject's pelvis position in the lab; root_xy (2,) the model root's horizontal position. Returns (forces, cops) dicts for
    the loaded feet, in the model frame."""
    forces, cops = {}, {}
    for k, foot in enumerate(FEET):
        if fp_frame[k, 6] < STANCE_FLAG:
            continue
        forces[foot] = mass_ratio * (LAB_TO_MODEL @ np.asarray(fp_frame[k, 0:3], float))
        rel = np.asarray(fp_frame[k, 3:6], float) - np.asarray(ref_lab, float)
        rel_model = LAB_TO_MODEL @ np.array([rel[0], 0.0, rel[2]])
        cops[foot] = np.array([ref_xy[0] + length_ratio * cop_scale * rel_model[0],
                               ref_xy[1] + length_ratio * cop_scale * rel_model[1], 0.0])
    return forces, cops


def method_h_forces(qfrc, measured_forces):
    """Freyja's total force (root force rows) shared between the loaded feet as the measured vertical force is."""
    total = np.asarray(qfrc[:3], float)
    fz = {n: f[2] for n, f in measured_forces.items()}
    s = sum(fz.values())
    return {n: (fz[n] / s) * total for n in measured_forces} if s > 0 else {}


def filter_measured(fp, T, cutoff_hz):
    """fp (2, 101, 7) with the three force channels passed through the same drift removal and zero-lag low-pass as the
    kinematics, applied only where the dataset has stance (the filter leaks a little force into swing, which is dropped)."""
    out = np.array(fp, float, copy=True)
    for k in range(2):
        f = retarget.filter_cycle(fp[k, :, 0:3], T, cutoff_hz)
        stance = fp[k, :, 6] >= STANCE_FLAG
        f[~stance] = 0.0
        out[k, :, 0:3] = f
    return out


def cop_to_freyja_foot(cop_lab, heel_lab, toe_lab, heel_model_xy, toe_model_xy):
    """A measured CoP placed on Freyja's foot at the same normalised place: along the foot as a fraction of heel-to-toe, and
    sideways by the same fraction of the foot length ratio. The subject's foot is the line from the heel marker to the toe-tip
    marker (lab frame), Freyja's the line from the rear to the front of her foot box on the floor (model frame). Returns the
    CoP's floor position in the model's horizontal plane (x anterior, y left)."""
    to_plane = lambda p: np.array([-p[2], -p[0]])  # lab (x right, z backward) -> model (x anterior, y left)
    h, t, c = to_plane(heel_lab), to_plane(toe_lab), to_plane(cop_lab)
    length = np.linalg.norm(t - h)
    u = (t - h) / length
    v = np.array([-u[1], u[0]])
    s, lat = float(np.dot(c - h, u)), float(np.dot(c - h, v))
    hf, tf = np.asarray(heel_model_xy, float), np.asarray(toe_model_xy, float)
    lf = np.linalg.norm(tf - hf)
    uf = (tf - hf) / lf
    vf = np.array([-uf[1], uf[0]])
    return hf + (s / length) * lf * uf + (lat * lf / length) * vf


def measured_to_model_foot(fp_frame, markers_frame, foot_segments, mass_ratio):
    """Like measured_to_model, but each CoP is placed on Freyja's own foot with cop_to_freyja_foot. markers_frame is (2, 2, 3):
    foot R/L, heel/toe tip, lab frame metres. foot_segments maps a foot body to its (rear, front) floor points in the model."""
    forces, cops = {}, {}
    for k, foot in enumerate(FEET):
        if fp_frame[k, 6] < STANCE_FLAG:
            continue
        forces[foot] = mass_ratio * (LAB_TO_MODEL @ np.asarray(fp_frame[k, 0:3], float))
        xy = cop_to_freyja_foot(fp_frame[k, 3:6], markers_frame[k, 0], markers_frame[k, 1], *foot_segments[foot])
        cops[foot] = np.array([xy[0], xy[1], 0.0])
    return forces, cops
