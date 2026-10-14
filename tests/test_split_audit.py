"""
Stage 2e T6: the dataset-side audit of the thigh to shank split. Pure helpers on synthetic input with known answers.

Run from the repo root:
    python -m pytest tests/test_split_audit.py
"""
import sys
from pathlib import Path

import numpy as np
import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "sim" / "scripts"))
sys.path.insert(0, str(REPO / "analysis"))

import split_audit as sa  # noqa: E402


def _pelvis(width=250.0, depth=100.0):
    """ASIS and PSIS markers (mm) of an upright pelvis in a frame x right, y up, z backward (the lab's): the subject faces -z."""
    asis_r, asis_l = np.array([width / 2, 0.0, 0.0]), np.array([-width / 2, 0.0, 0.0])
    psis_r, psis_l = np.array([40.0, 0.0, depth]), np.array([-40.0, 0.0, depth])
    return asis_r, asis_l, psis_r, psis_l


def test_the_pelvis_frame_has_its_origin_at_the_asis_midpoint_and_axes_anterior_up_and_to_the_right():
    f = sa.pelvis_frame(*_pelvis())
    assert np.allclose(f["origin"], 0.0)
    assert np.allclose(f["anterior"], [0, 0, -1]) and np.allclose(f["up"], [0, 1, 0]) and np.allclose(f["right"], [1, 0, 0])
    assert f["width"] == pytest.approx(250.0) and f["depth"] == pytest.approx(100.0)


def test_harrington_hip_centres_follow_the_published_equations_in_that_frame():
    f = sa.pelvis_frame(*_pelvis(250.0, 100.0))
    r, l = sa.harrington_hjc(f)
    x = -0.24 * 100.0 - 9.9  # anterior, mm
    y = -0.30 * 250.0 - 10.9  # up, mm (negative: below the ASIS)
    z = 0.33 * 250.0 + 7.3  # lateral toward the side, mm
    assert np.allclose(r, [z, y, -x])  # lab: x right, y up, z backward, so anterior is -z
    assert np.allclose(l, [-z, y, -x])


def test_a_length_in_the_sagittal_plane_ignores_the_mediolateral_offset():
    f = sa.pelvis_frame(*_pelvis())
    a, b = np.array([100.0, 0.0, 0.0]), np.array([160.0, -300.0, 400.0])  # b is 60 mm further lateral, 300 down, 400 backward
    assert sa.length_without_lateral(a, b, f) == pytest.approx(500.0)


def test_summary_statistics_name_min_median_max_and_sd_across_subjects():
    s = sa.spread([1.0, 2.0, 3.0, 4.0])
    assert s == {"min": 1.0, "median": 2.5, "max": 4.0, "sd": pytest.approx(np.std([1, 2, 3, 4], ddof=1)), "n": 4}


def test_a_thigh_to_shank_ratio_is_thigh_over_shank():
    assert sa.ratio(380.0, 430.0) == pytest.approx(380.0 / 430.0)
