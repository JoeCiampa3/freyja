"""
Stage 2 T5: the batch runner's arithmetic and its record. Synthetic cases with known answers for aggregation, agreement and
point caps; a small real-data run twice for byte-identical output.

Run from the repo root:
    python -m pytest tests/test_gait.py
"""
import datetime as dt
import sys
from pathlib import Path

import numpy as np
import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "sim" / "scripts"))
sys.path.insert(0, str(REPO / "analysis"))

import gait  # noqa: E402

PROCESSED = REPO / "data" / "camargo2021" / "processed" / "AB06.npz"


def test_aggregate_gives_mean_95th_percentile_and_maximum_with_and_without_a_subset():
    v = np.arange(1.0, 101.0)  # 1..100
    keep = np.arange(100) >= 10  # drops the first ten (values 1..10)
    a = gait.aggregate(v, keep)
    assert a["all"] == {"mean": 50.5, "p95": pytest.approx(95.05), "max": 100.0}
    assert a["without_offset"]["mean"] == pytest.approx(55.5) and a["without_offset"]["max"] == 100.0
    assert a["without_offset"]["p95"] == pytest.approx(np.percentile(v[10:], 95))


def test_peak_metrics_of_a_sinusoid():
    th = np.linspace(0, 2 * np.pi, 100, endpoint=False)
    m = gait.peak_metrics(10.0 * np.sin(th), 2.0 * np.cos(th) * 1.0)
    assert m["peak_torque_nm"] == pytest.approx(10.0, rel=1e-3)
    assert m["peak_speed_rad_s"] == pytest.approx(2.0, rel=1e-3)
    assert m["peak_power_pos_w"] == pytest.approx(10.0, rel=1e-2) and m["peak_power_neg_w"] == pytest.approx(-10.0, rel=1e-2)


def test_agreement_metrics():
    t = np.linspace(0, 2 * np.pi, 100, endpoint=False)
    d = np.sin(t)
    same = gait.agreement(d, d)
    assert same["rms_pct_ptp"] == 0.0 and same["corr"] == pytest.approx(1.0) and same["peak_diff"] == 0.0
    half = gait.agreement(0.5 * d, d)  # half the amplitude: rms diff = 0.5 * rms(sin) = 0.3536; ptp 2 -> 17.7 %
    assert half["rms_pct_ptp"] == pytest.approx(100 * 0.5 / np.sqrt(2) / 2, rel=1e-6)
    assert half["corr"] == pytest.approx(1.0) and half["peak_diff"] == pytest.approx(-0.5, abs=1e-3)
    assert gait.agreement(-d, d)["corr"] == pytest.approx(-1.0)


def test_a_numeric_pitch_mean_flags_methods_a_and_h_as_hybrid():
    spec = {"methods": ["B", "A_native", "A_filtered", "H"], "pitch_mean": "measured"}
    assert gait.hybrid_methods(spec) == []
    assert gait.hybrid_methods({**spec, "pitch_mean": 4.0}) == ["A_native", "A_filtered", "H"]  # a force and CoP of the measured posture on a different one
    assert gait.hybrid_methods({"methods": ["B"], "pitch_mean": 4.0}) == []


def test_stride_cap_keeps_the_first_n_per_subject_and_never_more():
    counts = {"AB06": 27, "AB07": 3, "AB08": 0}
    assert gait.capped_indices(counts, None) == {"AB06": list(range(27)), "AB07": [0, 1, 2], "AB08": []}
    assert gait.capped_indices(counts, 5) == {"AB06": [0, 1, 2, 3, 4], "AB07": [0, 1, 2], "AB08": []}
    assert gait.capped_indices(counts, 0) == {"AB06": [], "AB07": [], "AB08": []}


@pytest.mark.skipif(not PROCESSED.exists(), reason="processed Camargo arrays not present")
def test_two_runs_are_byte_identical_and_md_is_under_the_line_cap(tmp_path):
    spec = gait.load_spec("walk_treadmill")
    spec.update({"subjects": ["AB06"], "stride_cap_per_subject": 2, "speeds_mps": [1.4]})
    spec["sensitivity"] = {"cutoffs_hz": [4, 6], "pitch_offsets_deg": [0], "stride_cap_per_subject": 1}
    out = []
    for name in ("a", "b"):
        res = gait.run_gait(spec, gait_dir=tmp_path / name, now=dt.datetime(2026, 10, 12, 10, 0))
        out.append((res.json_path.read_bytes(), res.md_path.read_bytes()))
    assert out[0] == out[1]
    assert out[0][1].count(b"\n") <= gait.MAX_LINES
    assert b"Camargo" in out[0][1].split(b"\n", 6)[2] or b"Camargo" in out[0][1][:1500]  # attribution in the header
