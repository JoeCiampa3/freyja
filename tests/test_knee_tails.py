"""
Stage 2e T5: the knee's tails. Pure helpers on synthetic input with known answers: the exclusion sets, the 95th percentile / maximum / ratio of the stride
peaks, the stance percent of a frame counted from heel strike, and the split of A minus the dataset at a frame into force, lever, inertia and the rest.

Run from the repo root:
    python -m pytest tests/test_knee_tails.py
"""
import sys
from pathlib import Path

import numpy as np
import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "sim" / "scripts"))
sys.path.insert(0, str(REPO / "analysis"))

import knee_tails as kt  # noqa: E402


def test_the_three_exclusion_sets_remove_the_named_subjects_and_nothing_else():
    subs = ["AB06", "AB13", "AB15", "AB07", "AB06", "AB21"]
    m = kt.exclusion_masks(subs, offset=["AB13", "AB15"], pitch=["AB07", "AB12"])
    assert list(m) == ["all", "without_offset", "without_pitch_flagged"]
    assert m["all"].tolist() == [True] * 6
    assert m["without_offset"].tolist() == [True, False, False, True, True, True]
    assert m["without_pitch_flagged"].tolist() == [True, True, True, False, True, True]


def test_tail_row_is_the_95th_percentile_the_maximum_and_their_ratio():
    peaks = np.arange(1.0, 101.0)  # 1 .. 100
    r = kt.tail_row(peaks)
    assert r["n"] == 100 and r["max"] == 100.0
    assert r["p95"] == pytest.approx(np.percentile(peaks, 95)) and r["ratio"] == pytest.approx(100.0 / np.percentile(peaks, 95))
    assert kt.tail_row(np.array([]))["n"] == 0


def test_the_extension_peak_is_the_magnitude_of_the_most_negative_moment_and_zero_without_one():
    assert kt.extension_peak(np.array([5.0, -30.0, 2.0, -10.0])) == 30.0
    assert kt.extension_peak(np.array([5.0, 1.0])) == 0.0
    assert kt.peak_frame(np.array([5.0, -30.0, 2.0, -10.0])) == 1


def test_stance_percent_counts_from_heel_strike_over_a_wrapping_stance():
    flag = np.zeros(100, bool)
    flag[[*range(80, 100), *range(0, 20)]] = True  # 40 frames from 80, wrapping
    assert kt.stance_percent(flag, 80) == pytest.approx(0.0)
    assert kt.stance_percent(flag, 0) == pytest.approx(100 * 20 / 40)
    assert kt.stance_percent(flag, 19) == pytest.approx(100 * 39 / 40)
    assert np.isnan(kt.stance_percent(flag, 50))


def _series(k=3):
    n = 5
    z = lambda v: np.full(n, float(v))
    return {"tauA": np.array([0, -60.0, -40, 0, 0]), "tauD": np.array([0, -30.0, -30, 0, 0]),
            "FzA": z(800), "FzD": z(700), "dxA": z(-0.05), "dxD": z(-0.03), "FxA": z(-100), "FxD": z(-90), "hA": z(0.50), "hD": z(0.46),
            "inA": z(-2.0), "inD": z(-1.0)}


def test_the_split_adds_up_to_a_minus_d_with_the_remainder_called_other():
    s = _series()
    sp = kt.frame_split(s, 1)
    assert sp["total"] == pytest.approx(-60.0 - -30.0)
    # vertical term: sign +1 x Fz x lever, force part at the dataset's lever, lever part at A's force
    assert sp["vert_force"] == pytest.approx((800 - 700) * -0.03) and sp["vert_lever"] == pytest.approx(800 * (-0.05 - -0.03))
    assert sp["horiz_force"] == pytest.approx((-100 - -90) * 0.46) and sp["horiz_lever"] == pytest.approx(-100 * (0.50 - 0.46))
    assert sp["inertia"] == pytest.approx(-2.0 - -1.0)
    parts = sp["vert_force"] + sp["vert_lever"] + sp["horiz_force"] + sp["horiz_lever"] + sp["inertia"]
    assert sp["other"] == pytest.approx(sp["total"] - parts)
    assert sp["force"] == pytest.approx(sp["vert_force"] + sp["horiz_force"]) and sp["lever"] == pytest.approx(sp["vert_lever"] + sp["horiz_lever"])


def test_the_carrier_is_the_largest_magnitude_among_force_lever_inertia():
    assert kt.carrier({"force": -1.0, "lever": -9.0, "inertia": -2.0}) == "lever"
    assert kt.carrier({"force": -12.0, "lever": -9.0, "inertia": 2.0}) == "force"
    assert kt.carrier({"force": 0.0, "lever": 0.0, "inertia": -3.0}) == "inertia"


def test_a_subjects_median_ratio_is_the_median_of_a_over_d_peaks_of_its_stride_limbs():
    rows = [dict(subject="A", peakA=100.0, peakD=50.0), dict(subject="A", peakA=60.0, peakD=60.0), dict(subject="A", peakA=90.0, peakD=60.0), dict(subject="B", peakA=10.0, peakD=20.0)]
    out = kt.subject_median_ratio(rows)
    assert out["A"] == pytest.approx(1.5) and out["B"] == pytest.approx(0.5)


def test_the_low_load_peak_ignores_frames_whose_raw_force_is_below_the_fraction_of_body_weight():
    tau = np.array([0.0, -150.0, -20.0, -60.0, -10.0])
    fz = np.array([0.0, 25.0, 100.0, 500.0, 200.0])  # raw force, N
    weight = 640.0
    assert kt.extension_peak(tau) == 150.0
    assert kt.low_load_excluded_peak(tau, fz, weight, 0.10) == 60.0  # frame 1 (25 N < 64 N) is out; frame 2 (100 N) is in and smaller than frame 3
    assert kt.low_load_excluded_peak(tau, fz, weight, 0.0) == 150.0
    assert kt.low_load_excluded_peak(tau, np.zeros(5), weight, 0.10) == 0.0
    assert kt.peak_is_low_load(tau, fz, weight, 0.10) is True and kt.peak_is_low_load(tau, fz, weight, 0.02) is False
