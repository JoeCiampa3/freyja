"""Volume-extractor brief 1, steps 6-9: the thigh frame, the required stretch, the axial-only conform, the region and the sensitivity."""
import sys
from pathlib import Path

import numpy as np
import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "tools"))
sys.path.insert(0, str(REPO / "tests"))

from envelope import field, thigh  # noqa: E402
from envelope.synthetic import frustum  # noqa: E402


def test_segment_frame_has_origin_at_hjc_z_up_the_axis_and_x_anterior():
    hjc, kjc = np.array([50.0, -90.0, 900.0]), np.array([30.0, -95.0, 500.0])
    fr = thigh.segment_frame(hjc, kjc, pelvis_x=np.array([1.0, 0, 0]))
    assert np.isclose(np.linalg.det(fr.R), 1)
    assert np.allclose(fr.to_segment(hjc[None])[0], 0)
    L = np.linalg.norm(hjc - kjc)
    assert np.allclose(fr.to_segment(kjc[None])[0], [0, 0, -L])
    assert fr.R[:, 0] @ np.array([1.0, 0, 0]) > 0.99          # x stays anterior
    assert abs(fr.R[:, 0] @ fr.R[:, 2]) < 1e-12


def test_required_stretch_is_sheet_length_over_mesh_length():
    hjc, kjc = np.array([0.0, 0, 900]), np.array([0.0, 0, 520])
    assert np.isclose(thigh.required_stretch(hjc, kjc, 398.0), 398.0 / 380.0)


def test_conform_is_axial_only_and_puts_the_knee_at_the_sheet_length():
    pts = np.array([[10.0, 20.0, -100.0], [-5.0, 7.0, -380.0], [0, 0, 50.0]])
    out = thigh.conform(pts, 1.05)
    assert np.allclose(out[:, :2], pts[:, :2])                  # cross-sections untouched
    assert np.allclose(out[:, 2], pts[:, 2] * 1.05)
    assert np.isclose(thigh.conform(np.array([[0, 0, -380.0]]), 398.0 / 380.0)[0, 2], -398.0)


def test_conform_rejects_a_non_positive_stretch():
    with pytest.raises(ValueError):
        thigh.conform(np.zeros((1, 3)), 0.0)


def test_stretching_a_cylinder_keeps_the_section_areas_and_scales_the_volume():
    R, H = 40.0, 300.0
    v, f = frustum(R, R, 60, -H - 60)
    a = field.build_segment(v, f, length=H, voxel=2.0, z_top=0.0, margin=20.0)
    s = 1.06
    b = field.build_segment(thigh.conform(v, s), f, length=H * s, voxel=2.0, z_top=0.0, margin=20.0)
    for u in (0.1, 0.5, 0.9):
        assert abs(a.section(u * H).area() - b.section(u * H * s).area()) / a.section(u * H).area() < 0.01
    assert abs(b.volume() / a.volume() - s) < 0.01


def test_sensitivity_of_the_stretch_to_a_landmark_shift_is_first_order():
    hjc, kjc = np.array([0.0, 0, 900]), np.array([0.0, 0, 520])
    s0 = thigh.required_stretch(hjc, kjc, 398.0)
    s1 = thigh.required_stretch(hjc, kjc + [0, 0, -5.0], 398.0)
    assert np.isclose((s0 - s1) / s0, 5.0 / 385.0, rtol=0.02)
