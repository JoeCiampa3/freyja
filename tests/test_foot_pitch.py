"""
Stage 2d T2 (report, then one constant offset only under the brief's trigger): the foot's pitch in stance, model against dataset.
The pure helpers are tested on synthetic input, the model-dependent ones on the committed model.

Run from the repo root:
    python -m pytest tests/test_foot_pitch.py
"""
import sys
from pathlib import Path

import numpy as np
import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "sim" / "scripts"))
sys.path.insert(0, str(REPO / "analysis"))

import foot_pitch as fp  # noqa: E402


def _long_axis_rotation(pitch_deg, yaw_deg=0.0, roll_deg=0.0):
    """Rotation whose local x axis (the foot's long axis, pointing forward) is yawed by yaw_deg and raised by pitch_deg; roll is about that axis."""
    from scipy.spatial.transform import Rotation as R
    return (R.from_euler("z", yaw_deg, degrees=True) * R.from_euler("y", -pitch_deg, degrees=True) * R.from_euler("x", roll_deg, degrees=True)).as_matrix()


@pytest.mark.parametrize("pitch", [-12.0, -2.5, 0.0, 3.7, 9.0, 20.0])
@pytest.mark.parametrize("yaw,roll", [(0.0, 0.0), (35.0, 0.0), (-80.0, 14.0)])
def test_a_box_at_a_known_pitch_gives_that_pitch_toe_up_positive(pitch, yaw, roll):
    assert fp.box_pitch_deg(_long_axis_rotation(pitch, yaw, roll)) == pytest.approx(pitch, abs=1e-9)


@pytest.mark.parametrize("slope_deg", [-8.0, 0.0, 2.0, 11.0])
@pytest.mark.parametrize("heading_deg", [0.0, 90.0, 200.0])
def test_heel_and_toe_markers_at_a_known_slope_give_that_slope_whatever_the_horizontal_heading(slope_deg, heading_deg):
    """Lab frame: y up. The toe is 0.2 m along the heading from the heel and `slope_deg` above the heel's height line."""
    h = np.radians(heading_deg)
    run = 0.2
    heel = np.array([0.3, 0.05, -1.0])
    toe = heel + np.array([run * np.cos(h), run * np.tan(np.radians(slope_deg)), run * np.sin(h)])
    assert fp.marker_pitch_deg(heel, toe) == pytest.approx(slope_deg, abs=1e-9)
    # arrays of frames work the same way
    assert fp.marker_pitch_deg(np.stack([heel, heel]), np.stack([toe, toe])) == pytest.approx([slope_deg, slope_deg], abs=1e-9)


def test_marker_pitch_relative_to_the_static_trial_removes_the_marker_height_offset():
    # the toe-tip marker sits lower than the heel marker on a flat foot: a static slope of -4 degrees is flat, not toe-down
    assert fp.relative_marker_pitch_deg(np.array([-4.0, -1.0, 6.0]), -4.0) == pytest.approx([0.0, 3.0, 10.0])


def test_the_model_sole_is_flat_at_stand_static_for_both_feet():
    import gait
    c = gait._ctx(str(gait.simrun.MODEL_FILE))
    for foot in gait.FEET:
        assert fp.sole_pitch_deg(c.model, c.stand, foot) == pytest.approx(0.0, abs=1e-6)


def test_the_model_sole_follows_a_rotation_of_the_ankle():
    """A dorsiflexion of the right ankle by 7 degrees tips the toe up by 7 degrees (the ankle hinge is the foot's only rotation here)."""
    import gait
    import mujoco
    c = gait._ctx(str(gait.simrun.MODEL_FILE))
    adr = c.model.jnt_qposadr[mujoco.mj_name2id(c.model, mujoco.mjtObj.mjOBJ_JOINT, "ankle_pdflex_right")]
    q0 = c.stand.copy()
    base = fp.sole_pitch_deg(c.model, q0, "foot_right")
    q = q0.copy()
    q[adr] += np.radians(7.0)
    assert abs(fp.sole_pitch_deg(c.model, q, "foot_right") - base) == pytest.approx(7.0, abs=1e-6)
    assert abs(fp.sole_pitch_deg(c.model, q, "foot_left") - fp.sole_pitch_deg(c.model, q0, "foot_left")) < 1e-9


def test_decile_of_stance_is_taken_over_the_whole_stance_of_that_foot():
    stance = np.zeros(100, bool)
    stance[10:61] = True  # 51 frames
    dec = fp.stance_deciles(stance)
    assert dec[9] == -1 and dec[61] == -1  # not in stance
    assert dec[10] == 0 and dec[60] == 9
    assert sorted(set(dec[stance])) == list(range(10))
    assert np.all(np.diff(dec[stance]) >= 0)


def test_a_stance_that_wraps_around_the_stride_boundary_is_one_stance_not_two():
    """The contralateral foot's stance runs from about 50% of the stride to about 10% of the next (frames 51 to 99 and 0 to 11 of 100)."""
    stance = np.zeros(100, bool)
    stance[51:] = True
    stance[:12] = True  # 49 + 12 = 61 frames of one stance
    dec = fp.stance_deciles(stance)
    assert dec[51] == 0  # heel strike is the start, not frame 0
    assert dec[11] == 9  # toe-off is the end
    assert dec[0] > dec[99] and dec[0] >= 7  # the wrapped part is the late stance
    order = [(k - 51) % 100 for k in np.flatnonzero(stance)]
    pairs = sorted(zip(order, dec[stance]))
    assert [p[1] for p in pairs] == sorted(p[1] for p in pairs)  # deciles increase with time since heel strike
    assert sorted(set(dec[stance])) == list(range(10))
    assert np.all(dec[~stance] == -1)
    with pytest.raises(ValueError):
        fp.stance_deciles(np.ones(100, bool))  # no heel strike in the stride: no stance to divide
    assert np.all(fp.stance_deciles(np.zeros(100, bool)) == -1)


def test_a_flicker_of_the_force_flag_after_toe_off_is_not_part_of_the_stance():
    stance = np.zeros(100, bool)
    stance[51:] = True
    stance[:12] = True
    stance[14] = True  # a one-frame blip two frames after toe-off
    stance[16:18] = True
    dec = fp.stance_deciles(stance)
    assert dec[14] == -1 and dec[16] == -1 and dec[17] == -1
    assert np.array_equal(dec, np.where(np.arange(100) == 14, -1, np.where((np.arange(100) >= 16) & (np.arange(100) < 18), -1, fp.stance_deciles(np.r_[np.ones(12, bool), np.zeros(39, bool), np.ones(49, bool)]))))
    assert (dec >= 0).sum() == 61


def test_the_offset_trigger_fires_only_when_the_mean_is_over_one_degree_and_the_subject_spread_under_two():
    assert fp.offset_for_trigger(2.34, 1.1) == pytest.approx(-2.3)  # the negative of the mean, to 0.1 degree
    assert fp.offset_for_trigger(-1.26, 0.4) == pytest.approx(1.3)
    assert fp.offset_for_trigger(0.99, 0.5) is None  # mean not large enough
    assert fp.offset_for_trigger(-1.0, 0.5) is None  # exactly 1.0 is not "exceeds"
    assert fp.offset_for_trigger(3.0, 2.0) is None  # exactly 2.0 is not "below"
    assert fp.offset_for_trigger(3.0, 2.6) is None


def test_the_pooled_difference_by_decile_averages_subjects_equally_and_counts_the_fractions_off_flat():
    # two subjects; subject A has 3 frames in decile 3, subject B has 1: the pooled mean is the mean of the two subject means
    rows = [
        dict(subject="A", dec=3, model=2.0, data=0.0), dict(subject="A", dec=3, model=2.0, data=0.0), dict(subject="A", dec=3, model=8.0, data=0.0),
        dict(subject="B", dec=3, model=0.0, data=-2.0),
        dict(subject="A", dec=4, model=7.0, data=0.0), dict(subject="B", dec=4, model=-7.0, data=1.0),
    ]
    out = fp.by_decile(rows, off_flat_deg=6.0)
    d3 = out[3]
    assert d3["n"] == 4
    assert d3["mean_model"] == pytest.approx(0.5 * (4.0 + 0.0))
    assert d3["mean_data"] == pytest.approx(0.5 * (0.0 + -2.0))
    assert d3["mean_diff"] == pytest.approx(0.5 * (4.0 + 2.0))
    assert d3["sd_subject_means"] == pytest.approx(np.std([4.0, 2.0], ddof=1))
    assert d3["frac_model_off_flat"] == pytest.approx(1 / 4) and d3["frac_data_off_flat"] == pytest.approx(0.0)
    assert out[4]["frac_model_off_flat"] == pytest.approx(1.0) and out[4]["frac_data_off_flat"] == pytest.approx(0.0)
    window = fp.pool_window(rows, (3, 4))
    # subject means over the window: A = mean of its 5 frame diffs... frames pooled per subject, then the subjects averaged
    a = np.mean([2.0, 2.0, 8.0, 7.0])
    b = np.mean([2.0, -8.0])
    assert window["mean_diff"] == pytest.approx(0.5 * (a + b))
    assert window["sd_subject_means"] == pytest.approx(np.std([a, b], ddof=1))


def test_the_ankle_offset_counterfactual_shifts_only_the_two_ankle_channels_by_the_offset():
    import retarget
    names = retarget._channels()
    ik = np.random.default_rng(1).normal(size=(101, len(names)))
    out = fp.with_ankle_offset(ik, -4.4)
    assert out is not ik and np.array_equal(ik, ik.copy())  # a copy
    for n in ("ankle_angle_r", "ankle_angle_l"):
        i = names.index(n)
        assert np.allclose(out[:, i], ik[:, i] - 4.4)
    other = [i for i, n in enumerate(names) if n not in ("ankle_angle_r", "ankle_angle_l")]
    assert np.array_equal(out[:, other], ik[:, other])
    assert np.array_equal(fp.with_ankle_offset(ik, 0.0), ik)
