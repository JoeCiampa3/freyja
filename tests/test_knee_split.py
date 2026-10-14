"""
Stage 2e T7: the throwaway model with the knee moved along the hip to ankle line (thigh plus shank fixed). The transform acts on the text of a generated
MJCF and returns new text; nothing is written by the transform.

Run from the repo root:
    python -m pytest tests/test_knee_split.py
"""
import re
import sys
from pathlib import Path

import mujoco
import numpy as np
import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "sim" / "scripts"))
sys.path.insert(0, str(REPO / "analysis"))

import knee_split as ks  # noqa: E402

XML = (REPO / "sim" / "models" / "freyja.xml").read_text(encoding="utf-8")


def _leg(xml, side="right"):
    m = mujoco.MjModel.from_xml_string(xml)
    d = mujoco.MjData(m)
    mujoco.mj_kinematics(m, d)
    pos = lambda n: d.xpos[mujoco.mj_name2id(m, mujoco.mjtObj.mjOBJ_BODY, n)].copy()
    return m, d, pos(f"thigh_{side}"), pos(f"shank_{side}"), pos(f"foot_{side}")


def test_the_sum_stays_fixed_and_the_ratio_takes_the_requested_value():
    _, _, h0, k0, a0 = _leg(XML)
    s0 = np.linalg.norm(a0 - h0)
    for r in (0.883, 0.935, 0.977, 1.0):
        out = ks.with_thigh_to_shank_ratio(XML, r)
        _, _, h, k, a = _leg(out)
        assert np.linalg.norm(a - h) == pytest.approx(s0, abs=1e-9)  # the hip to ankle distance (the leg length) is unchanged
        assert np.linalg.norm(k - h) / np.linalg.norm(a - k) == pytest.approx(r, abs=1e-9)


def test_the_current_ratio_reproduces_the_model():
    cur = ks.current_ratio(XML)
    out = ks.with_thigh_to_shank_ratio(XML, cur)
    m0, m1 = mujoco.MjModel.from_xml_string(XML), mujoco.MjModel.from_xml_string(out)
    assert np.allclose(m0.body_pos, m1.body_pos, atol=1e-9) and np.allclose(m0.body_ipos, m1.body_ipos, atol=1e-9)
    assert np.allclose(m0.body_inertia, m1.body_inertia, rtol=1e-6)


def test_centre_of_mass_offsets_and_inertia_scale_with_the_segment_length_and_masses_are_unchanged():
    m0 = mujoco.MjModel.from_xml_string(XML)
    out = ks.with_thigh_to_shank_ratio(XML, 0.883)
    m1 = mujoco.MjModel.from_xml_string(out)
    for side in ("right", "left"):
        for seg, which in ((f"thigh_{side}", "thigh"), (f"shank_{side}", "shank")):
            i = mujoco.mj_name2id(m0, mujoco.mjtObj.mjOBJ_BODY, seg)
            f = ks.length_factor(XML, 0.883, which)
            assert np.allclose(m1.body_ipos[i], f * m0.body_ipos[i], atol=1e-12)
            assert m1.body_mass[i] == m0.body_mass[i]
            assert np.allclose(np.sort(m1.body_inertia[i]), np.sort(m0.body_inertia[i]) * f ** 2, rtol=1e-6)
    assert m1.body_mass.sum() == pytest.approx(m0.body_mass.sum())


def test_it_refuses_a_ratio_that_is_not_positive():
    with pytest.raises(ValueError):
        ks.with_thigh_to_shank_ratio(XML, 0.0)
