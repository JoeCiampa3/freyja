"""
Stage 2d T4 and T5 (report only): the pure arithmetic of the knee diagnostics in sim/scripts/knee_gain.py, on synthetic input with known answers.
The report itself prints numbers to the memo and writes nothing; it is reproduced by running it, not by a test.

Run from the repo root:
    python -m pytest tests/test_knee_gain.py
"""
import sys
from pathlib import Path

import numpy as np
import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "sim" / "scripts"))
sys.path.insert(0, str(REPO / "analysis"))

import knee_gain as kg  # noqa: E402

OSIM = """<OpenSimDocument><Model><JointSet><objects>
<CustomJoint name="knee_r"><SpatialTransform>
  <TransformAxis name="translation1"><coordinates>knee_angle_r</coordinates><MultiplierFunction><function><SimmSpline>
    <x> -2.0 -1.0 0.0 1.0 2.0</x><y> -0.01 0.0 0.004 0.0 -0.01</y></SimmSpline></function><scale>2.0</scale></MultiplierFunction></TransformAxis>
  <TransformAxis name="translation2"><coordinates>knee_angle_r</coordinates><MultiplierFunction><function><SimmSpline>
    <x> -2.0 -1.0 0.0 1.0 2.0</x><y> -0.42 -0.41 -0.40 -0.40 -0.40</y></SimmSpline></function><scale>1.05</scale></MultiplierFunction></TransformAxis>
</SpatialTransform></CustomJoint>
</objects></JointSet></Model></OpenSimDocument>"""


def test_the_knee_translation_reads_the_spline_through_its_knots_with_the_multiplier_scale():
    f = kg.knee_translation_fn(OSIM.encode(), "r")
    tx, ty = f(0.0)
    assert tx == pytest.approx(0.004 * 2.0) and ty == pytest.approx(-0.40 * 1.05)
    tx, ty = f(-1.0)
    assert tx == pytest.approx(0.0) and ty == pytest.approx(-0.41 * 1.05)
    assert f(-3.0) == pytest.approx(f(-2.0))  # outside the spline's range the end value is held, not extrapolated
    assert np.hypot(*f(0.0)) == pytest.approx(kg.thigh_length_m(OSIM.encode(), "r"))


@pytest.mark.parametrize("phi,expected", [(0.0, (0.0, -0.4)), (90.0, (0.4, 0.0)), (30.0, (0.4 * 0.5, -0.4 * np.cos(np.radians(30))))])
def test_the_planar_knee_offset_swings_forward_with_thigh_flexion(phi, expected):
    dx, dz = kg.planar_knee_offset(phi, (0.0, -0.4))
    assert (dx, dz) == pytest.approx(expected, abs=1e-12)


def test_the_planar_knee_offset_keeps_the_translations_x_part_in_the_femur_frame():
    dx, dz = kg.planar_knee_offset(0.0, (0.01, -0.4))
    assert (dx, dz) == pytest.approx((0.01, -0.4))  # the knee sits 10 mm anterior of the femur's long axis at zero flexion
    dx, dz = kg.planar_knee_offset(90.0, (0.01, -0.4))
    assert (dx, dz) == pytest.approx((0.4, 0.01), abs=1e-12)


def test_log_shares_split_an_excess_in_proportion_to_each_factors_logarithm_and_sum_to_it():
    factors = {"lever": 1.25, "force": 0.98, "closure": 1.02, "leg_ratio": 0.96, "inertia": 1.0}
    shares = kg.log_shares(factors, 30.0)
    assert sum(shares.values()) == pytest.approx(30.0)
    assert shares["inertia"] == pytest.approx(0.0)
    assert shares["leg_ratio"] < 0 and shares["lever"] > shares["closure"] > 0
    prod = np.prod(list(factors.values()))
    assert shares["lever"] == pytest.approx(30.0 * np.log(1.25) / np.log(prod))
    assert kg.log_shares({"a": 1.0, "b": 1.0}, 5.0) == {"a": 0.0, "b": 0.0}  # a product of one has no excess to share


def test_direction_peaks_are_the_largest_flexion_and_extension_moments_of_a_stride():
    tau = np.array([-5.0, -40.0, -12.0, 3.0, 18.0, 7.0, -1.0])
    assert kg.direction_peaks(tau) == (18.0, 40.0)  # (flexion, extension) magnitudes; flexion positive
    assert kg.direction_peaks(np.array([-2.0, -3.0])) == (0.0, 3.0)  # no flexion moment in the stride
    assert kg.direction_peaks(np.array([2.0, 3.0])) == (3.0, 0.0)


def test_the_p95_band_selects_the_strides_between_the_92_5th_and_97_5th_percentile_of_the_stride_peaks():
    peaks = np.arange(1.0, 201.0)
    band = kg.p95_band(peaks)
    assert band.sum() == pytest.approx(10, abs=1)
    assert peaks[band].min() >= np.percentile(peaks, 92.5) - 1e-9 and peaks[band].max() <= np.percentile(peaks, 97.5) + 1e-9
    assert not band[:150].any() and not band[-4:].any()  # a band, not a tail: nothing below the 92.5th or above the 97.5th percentile


def test_the_angle_bins_count_frames_and_take_each_directions_median_p95_and_max_of_the_moment_magnitude():
    # frames in the 10 to 15 degree bin: moments +10..+50 (flexion) in steps of 10 and two extension frames -5, -8
    angle = np.array([11, 12, 13, 14, 14.9, 12, 13, 40.0])
    tau = np.array([10, 20, 30, 40, 50, -5, -8, 100.0])
    speed = np.array([1.0, 2.0, 3.0, 4.0, 5.0, -1.0, -2.0, 9.0])
    bins = kg.angle_bins(angle, tau, speed, width_deg=5.0)
    b = next(x for x in bins if x["lo"] == 10)
    assert b["n"] == 7
    assert b["flexion"]["n"] == 5 and b["flexion"]["median"] == pytest.approx(30.0) and b["flexion"]["max"] == pytest.approx(50.0)
    assert b["flexion"]["p95"] == pytest.approx(np.percentile([10, 20, 30, 40, 50], 95))
    assert b["extension"]["n"] == 2 and b["extension"]["max"] == pytest.approx(8.0) and b["extension"]["median"] == pytest.approx(6.5)
    assert b["max_abs_speed"] == pytest.approx(5.0)
    # the speed at the frames of the 95th-percentile moment: the median speed of the frames at or above it (here only the 50 N m frame)
    assert b["flexion"]["speed_at_p95"] == pytest.approx(5.0)
    assert b["extension"]["speed_at_p95"] == pytest.approx(-2.0)  # the -8 frame, signed speed
    assert [x["lo"] for x in bins] == sorted(x["lo"] for x in bins)
    assert next(x for x in bins if x["lo"] == 40)["n"] == 1


def test_powers_are_moment_times_speed_with_positive_and_negative_peaks():
    tau = np.array([10.0, -20.0, 5.0])
    speed = np.array([2.0, 3.0, -4.0])
    pos, neg = kg.power_peaks(tau, speed)
    assert (pos, neg) == (20.0, -60.0)  # 10*2, -20*3, 5*-4 = 20, -60, -20
    assert kg.power_peaks(np.array([1.0]), np.array([1.0])) == (1.0, 1.0)  # a stride with no negative power reports the smallest power, not zero


def test_the_dataset_knee_centre_is_the_hip_centre_plus_the_translation_swung_by_the_thigh_flexion(monkeypatch):
    import gait
    monkeypatch.setattr(kg, "_osim_fn", lambda subject, side: (lambda q: (0.004, -0.4)))
    ch = gait.ic.IK_CHANNELS
    c = gait._ctx(str(gait.simrun.MODEL_FILE))
    ik = np.zeros((100, len(ch)))
    ik[:, ch.index("hip_flexion_r")] = np.linspace(-20.0, 40.0, 100)
    ik[:, ch.index("pelvis_list")] = 5.0  # list is minus the anterior pitch: the thigh from the vertical is hip + list
    hip_jc = np.tile(np.array([0.1, -0.09, 0.9]), (100, 1))
    jc = kg.dataset_knee_jc("AB06", "right", ik, hip_jc, c.mapping)
    phi = np.radians(np.linspace(-20.0, 40.0, 100) + 5.0)
    assert jc[:, 0] == pytest.approx(0.1 + 0.004 * np.cos(phi) + 0.4 * np.sin(phi))
    assert jc[:, 2] == pytest.approx(0.9 + 0.004 * np.sin(phi) - 0.4 * np.cos(phi))
    assert jc[:, 1] == pytest.approx(-0.09)  # the lateral position is the hip's: the diagnostic is planar
    assert np.hypot(jc[:, 0] - 0.1, jc[:, 2] - 0.9) == pytest.approx(np.hypot(0.004, 0.4))  # the thigh length does not depend on the flexion


def test_the_dataset_hip_centre_of_each_side_is_rotated_with_the_pelvis_including_its_yaw():
    import gait
    ch = gait.ic.IK_CHANNELS
    ik = np.zeros((4, len(ch)))
    ik[:, ch.index("pelvis_rotation")] = 90.0  # the lab's baseline: the pelvis faces forward (lab minus z)
    ik[:, ch.index("pelvis_tx")], ik[:, ch.index("pelvis_ty")], ik[:, ch.index("pelvis_tz")] = 1.0, 2.0, 3.0
    hip = [0.05, -0.07, 0.09]  # x forward, y up, half separation (OpenSim pelvis frame)
    right = kg.dataset_hip_jc(ik, hip, "right")
    left = kg.dataset_hip_jc(ik, hip, "left")
    # model frame: x anterior, y left, z up; lab x right, y up, z backward
    assert right[0] == pytest.approx([0.05 - 3.0, -(1.0 + 0.09), 2.0 - 0.07])
    assert left[0] == pytest.approx([0.05 - 3.0, -(1.0 - 0.09), 2.0 - 0.07])
    # yawing the pelvis by 10 degrees swings the lateral offset into the fore-aft direction: the right hip moves back, the left forward (or the reverse)
    ik[:, ch.index("pelvis_rotation")] = 100.0
    r2, l2 = kg.dataset_hip_jc(ik, hip, "right"), kg.dataset_hip_jc(ik, hip, "left")
    dx = 0.09 * np.sin(np.radians(10.0))
    assert abs((r2 - l2)[0, 0] - (right - left)[0, 0]) == pytest.approx(2 * dx)  # the two sides swing apart fore-aft by twice the lateral offset times sin(yaw)
    # the midpoint is what the CoP is referenced to: it is the dataset's own hip midpoint, with the yaw included
    import retarget
    from gaitloads import LAB_TO_MODEL
    mid_lab = retarget.dataset_hip_mid_lab(ik, hip)
    assert 0.5 * (r2[0] + l2[0]) == pytest.approx(LAB_TO_MODEL @ mid_lab[0], abs=1e-9)


def test_the_force_part_and_the_lever_part_add_up_to_the_difference_of_the_two_force_times_lever_products():
    rng = np.random.default_rng(7)
    fa, fd = rng.uniform(300, 900, 50), rng.uniform(300, 900, 50)
    la, ld = rng.uniform(-0.08, 0.08, 50), rng.uniform(-0.08, 0.08, 50)
    for sign in (1.0, -1.0):
        f, l = kg.force_lever_split(fa, fd, la, ld, sign)
        assert f + l == pytest.approx(sign * (fa * la - fd * ld))
    f, l = kg.force_lever_split(fa, fa, la, ld, 1.0)
    assert f == pytest.approx(0.0) and l == pytest.approx(fa * (la - ld))  # equal forces: the whole difference is lever
    f, l = kg.force_lever_split(fa, fd, la, la, 1.0)
    assert l == pytest.approx(0.0) and f == pytest.approx((fa - fd) * la)  # equal levers: the whole difference is force


def test_the_term_sign_is_the_sign_of_the_torque_per_unit_force_times_lever():
    fz, dx = np.array([700.0, 650.0, 800.0]), np.array([-0.04, -0.05, -0.03])
    assert kg.term_sign(-fz * dx, fz, dx) == -1.0  # a term that is minus force times lever
    assert kg.term_sign(2.0 * fz * dx, fz, dx) == 1.0
