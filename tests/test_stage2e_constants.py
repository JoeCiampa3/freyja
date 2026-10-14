"""
Stage 2e T2: constants that duplicate a value held by the loaded model, the spec or a module constant are read from there.
The first one is the hip extension stop that `gait_diag.py hipext` compared the dataset against (a literal 18.1 until Stage 2e).

Run from the repo root:
    python -m pytest tests/test_stage2e_constants.py
"""
import sys
from pathlib import Path

import mujoco
import numpy as np
import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "sim" / "scripts"))
sys.path.insert(0, str(REPO / "analysis"))

import gait_diag as gd  # noqa: E402


def _model():
    import gait
    return mujoco.MjModel.from_xml_path(str(gait.simrun.MODEL_FILE))  # a fresh copy: the tests below edit its ranges


def test_the_hip_stop_is_the_models_own_extension_range():
    m = _model()
    rng = m.jnt_range[m.joint("hip_fe_right").id]
    assert gd.hip_extension_stop_deg(m) == pytest.approx(-np.degrees(rng[0]))
    assert gd.hip_extension_stop_deg(m) == pytest.approx(31.0, abs=1e-6)  # the sheet's value at the time of writing; the test above is the contract


def test_the_hip_stop_follows_a_throwaway_models_range():
    m = _model()
    for side in ("right", "left"):
        m.jnt_range[m.joint(f"hip_fe_{side}").id][0] = np.radians(-12.5)
    assert gd.hip_extension_stop_deg(m) == pytest.approx(12.5)


def test_the_printed_fraction_beyond_the_stop_uses_that_stop_and_not_a_literal():
    m = _model()
    raw = np.array([10.0, 20.0, 30.0, 40.0])  # degrees of hip extension, one per stride
    line = gd.beyond_stop_line(m, raw)
    assert "31.0 deg stop" in line and "0.25 of strides" in line  # only 40 exceeds 31
    for side in ("right", "left"):
        m.jnt_range[m.joint(f"hip_fe_{side}").id][0] = np.radians(-15.0)
    line = gd.beyond_stop_line(m, raw)
    assert "15.0 deg stop" in line and "0.75 of strides" in line  # 20, 30 and 40 exceed 15


# ---- constants that duplicated a module constant, the spec or the model

SCRIPTS = REPO / "sim" / "scripts"


def _code_lines(name):
    """The file's lines without comments and string-only lines, so that a literal in prose does not count."""
    import re
    out = []
    for n, line in enumerate((SCRIPTS / name).read_text(encoding="utf-8").splitlines(), 1):
        code = re.sub(r"#.*$", "", line)
        if code.strip():
            out.append((n, code))
    return out


@pytest.mark.parametrize("name", ["gait_diag.py", "ankle_gain.py", "knee_gain.py", "gait_extract.py"])
def test_no_stance_flag_threshold_is_a_literal(name):
    """The stance flag's threshold lives in gaitloads.STANCE_FLAG."""
    import re
    bad = [(n, c.strip()) for n, c in _code_lines(name) if re.search(r"\]\s*>=\s*0\.5\b|>=\s*0\.5\b.*\bfp\b|\bfp\b.*>=\s*0\.5\b", c)]
    assert not bad, bad


@pytest.mark.parametrize("name", ["gait_diag.py", "gait_extract.py"])
def test_no_filter_cutoff_is_a_literal_six(name):
    """The 6 Hz kinematics and force cutoff lives in retarget.CUTOFF_HZ (and the spec's smoothing block)."""
    import re
    bad = [(n, c.strip()) for n, c in _code_lines(name) if re.search(r"cutoff_hz\s*=\s*6\.0|filter_cycle\([^)]*,\s*6\.0\)", c)]
    assert not bad, bad


def test_the_diagnostics_review_targets_are_the_gaits_band():
    import gait
    assert gd.TARGET_CORR is gait.BAND_CORR and gd.TARGET_RMS_PCT is gait.BAND_RMS_PCT


def test_the_polygon_report_takes_its_pitch_offsets_from_the_spec():
    import gait
    spec = gait.load_spec("walk_treadmill")
    offs = gd.polygon_pitch_offsets(spec)
    assert offs[0] == 0.0 and sorted(offs) == sorted(float(o) for o in spec["sensitivity"]["pitch_offsets_deg"])
    assert gd.polygon_pitch_offsets({"sensitivity": {"pitch_offsets_deg": [-2, 0, 7]}}) == [0.0, -2.0, 7.0]
