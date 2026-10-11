"""
Stage 2 T4: methods A and H and the measured-force conversion.

  A  the measured force and CoP, scaled to Freyja; the root rows generally do not close.
  H  Freyja's own total force (m(a+g)) applied at the measured CoP, shared between the feet as the measured force is; the
     force rows close to round-off and only the moment rows leave a residual.

Run from the repo root:
    python -m pytest tests/test_gaitloads.py
"""
import sys
from pathlib import Path

import mujoco
import numpy as np
import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "sim" / "scripts"))
sys.path.insert(0, str(REPO / "analysis"))

import dynamics  # noqa: E402
import gaitloads  # noqa: E402

G = 9.81


@pytest.fixture(scope="module")
def model():
    return mujoco.MjModel.from_xml_path(str(REPO / "sim" / "models" / "freyja.xml"))


def fp_frame(fz_r, fz_l, cop_r=(0.6, 0, -0.8), cop_l=(0.4, 0, -0.7), fx=0.0, fzlab=0.0):
    """One frame of fp (2, 7): Fx Fy Fz CoPx CoPy CoPz stance, lab axes (y up)."""
    out = np.zeros((2, 7))
    for k, (fy, c) in enumerate(((fz_r, cop_r), (fz_l, cop_l))):
        out[k, :6] = [fx, fy, fzlab, *c]
        out[k, 6] = 1.0 if fy > 0 else 0.0
        if fy <= 0:
            out[k, 3:6] = np.nan
    return out


def test_force_is_rotated_to_model_axes_and_scaled_by_the_mass_ratio():
    fp = fp_frame(700.0, 0.0, fx=10.0, fzlab=-20.0)  # lab: 10 N to the right, 20 N backward-negative = forward 20 N
    forces, _ = gaitloads.measured_to_model(fp, pelvis_lab=np.array([0.5, 1.0, -0.7]), root_xy=np.zeros(2), mass_ratio=0.5, length_ratio=1.0)
    # model x anterior = -lab z, y left = -lab x, z up = lab y
    assert forces["foot_right"] == pytest.approx(0.5 * np.array([20.0, -10.0, 700.0]))
    assert "foot_left" not in forces  # an unloaded plate carries nothing


def test_cop_is_taken_relative_to_the_pelvis_scaled_by_the_length_ratio_and_placed_at_the_model_root():
    fp = fp_frame(700.0, 0.0, cop_r=(1.0, 0.0, -2.0))
    pelvis = np.array([0.5, 1.0, -1.5])  # relative CoP in the lab: (+0.5 right, -0.5 z) = (0.5 right, 0.5 forward)
    _, cops = gaitloads.measured_to_model(fp, pelvis, root_xy=np.array([0.1, 0.2]), mass_ratio=1.0, length_ratio=0.8)
    assert cops["foot_right"] == pytest.approx([0.1 + 0.8 * 0.5, 0.2 + 0.8 * -0.5, 0.0])
    _, cops2 = gaitloads.measured_to_model(fp, pelvis, np.array([0.1, 0.2]), 1.0, 0.8, cop_scale=1.1)
    assert cops2["foot_right"] - np.array([0.1, 0.2, 0.0]) == pytest.approx(1.1 * (cops["foot_right"] - np.array([0.1, 0.2, 0.0])))


def test_method_h_closes_the_force_rows_and_leaves_only_moments(model):
    q = np.zeros(model.nq); q[3] = 1.0; q[2] = 0.965
    qd, qdd = np.zeros(model.nv), np.zeros(model.nv)
    qdd[0], qdd[2] = 0.7, 0.4
    qfrc = dynamics.inverse_frame(model, q, qd, qdd)
    fp = fp_frame(380.0, 260.0)
    meas_forces, cops = gaitloads.measured_to_model(fp, np.array([0.5, 1.0, -0.75]), q[:2], 1.0, 1.0)
    forces = gaitloads.method_h_forces(qfrc, meas_forces)
    torque, res, _ = dynamics.solve_given(model, q, qfrc, forces, cops)
    assert np.abs(res[:3]).max() < 1e-9 * model.body_mass.sum() * G  # force rows: round-off
    assert np.abs(res[3:]).max() > 1.0  # the arbitrary CoP leaves a moment residual
    assert forces["foot_right"][2] / forces["foot_left"][2] == pytest.approx(380.0 / 260.0)  # shared as the measured force is


def test_method_a_generally_leaves_both_force_and_moment_residuals(model):
    q = np.zeros(model.nq); q[3] = 1.0; q[2] = 0.965
    qd, qdd = np.zeros(model.nv), np.zeros(model.nv)
    qfrc = dynamics.inverse_frame(model, q, qd, qdd)
    fp = fp_frame(380.0, 260.0)  # 640 N against Freyja's weight 637 N: close but not equal
    forces, cops = gaitloads.measured_to_model(fp, np.array([0.5, 1.0, -0.75]), q[:2], 1.0, 1.0)
    _, res, _ = dynamics.solve_given(model, q, qfrc, forces, cops)
    assert abs(res[2]) > 1.0 and np.abs(res[3:]).max() > 1.0


def test_filtered_force_is_applied_only_where_the_dataset_has_stance():
    ph = np.linspace(0, 1, 101)
    fp = np.zeros((2, 101, 7)); fp[0, :60, 1] = 700.0 * np.sin(np.pi * ph[:60] / 0.6); fp[0, :60, 6] = 1.0
    out = gaitloads.filter_measured(fp, T=1.0, cutoff_hz=6.0)
    assert np.all(out[0, 60:, 1] == 0.0) and np.all(out[0, :60, 6] == 1.0)
    assert out[0, 30, 1] == pytest.approx(700.0 * np.sin(np.pi * 0.5), rel=0.03)
