"""Stage 2g T4: the flat-foot threshold of foot_pitch.py is derived from the model's sole, not typed (it was 6 degrees, the round number below asin(25/206) for the old box)."""
import sys
from pathlib import Path

import mujoco
import numpy as np
import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "tests"))
sys.path.insert(0, str(REPO / "analysis"))
sys.path.insert(0, str(REPO / "sim" / "scripts"))

import dynamics  # noqa: E402
import foot_help as fh  # noqa: E402
import foot_pitch as fp  # noqa: E402


def test_there_is_no_typed_constant_any_more():
    assert not hasattr(fp, "OFF_FLAT_DEG")


def test_the_threshold_is_asin_of_the_band_over_the_models_sole_length():
    for path in (REPO / "sim" / "models" / "freyja.xml", fh.fixture_model_path()):
        model = mujoco.MjModel.from_xml_path(str(path))
        sole = fp.sole_length_m(model)
        assert fp.off_flat_deg(model) == pytest.approx(np.degrees(np.arcsin(dynamics.HULL_BAND_M / sole)), abs=1e-12)


def test_the_sole_is_the_boxes_of_the_foot_and_its_toe():
    fixture = mujoco.MjModel.from_xml_path(str(fh.fixture_model_path()))
    heel, tip = fh.SPEC_DESIGN["foot_heel_behind_ankle_mm"] / 1000, fh.SPEC_DESIGN["toe_tip_ahead_ankle_mm"] / 1000
    assert fp.sole_length_m(fixture) == pytest.approx(heel + tip, abs=1e-9)  # 257 mm, the anatomical foot of the sheet spec
    old = mujoco.MjModel.from_xml_path(str(REPO / "sim" / "models" / "freyja.xml"))
    if fp.sole_length_m(old) < 0.21:  # the tracked model has the Stage 2 box, 206 mm
        assert fp.sole_length_m(old) == pytest.approx(1.25 * 0.165, abs=1e-9)
        assert fp.off_flat_deg(old) == pytest.approx(6.97, abs=0.01)
    assert fp.off_flat_deg(fixture) == pytest.approx(5.58, abs=0.01)


def test_by_decile_defaults_to_the_derived_threshold():
    rows = [dict(subject="A", dec=3, model=6.5, data=0.0), dict(subject="A", dec=3, model=5.0, data=0.0)]
    derived = fp.off_flat_deg()
    out = fp.by_decile(rows)
    expect = float(np.mean([abs(r["model"]) > derived for r in rows]))
    assert out[3]["frac_model_off_flat"] == pytest.approx(expect)
