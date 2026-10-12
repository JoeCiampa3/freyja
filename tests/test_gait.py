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


def test_force_metrics_on_synthetic_forces():
    ph = np.linspace(0, 1, 101)
    meas = np.stack([100 * np.sin(2 * np.pi * ph), 50 * np.sin(2 * np.pi * ph), 700 + 200 * np.sin(4 * np.pi * ph)], axis=1)  # fore-aft, lateral, vertical
    same = gait.force_metrics(meas, meas)
    assert same["lat_ptp_ratio"] == pytest.approx(1.0) and same["lat_corr"] == pytest.approx(1.0) and same["vert_peak_ratio"] == pytest.approx(1.0)
    twice_flipped = meas.copy()
    twice_flipped[:, 1] *= -2.0  # lateral force with twice the amplitude and the wrong sign
    m = gait.force_metrics(twice_flipped, meas)
    assert m["lat_ptp_ratio"] == pytest.approx(2.0) and m["lat_corr"] == pytest.approx(-1.0) and m["ap_corr"] == pytest.approx(1.0)


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
    import json
    fe = json.loads(out[0][0])["results"]["1.4"]["rigid"]["feasibility"]
    assert set(fe["polygon"]) == {"B", "measured"} and set(fe["polygon"]["B"]) == {"0.01", "0.025", "0.04"}  # the polygon test at the three bands
    assert set(fe["polygon"]["B"]["0.025"]) == {"single", "double"}
    assert b"Polygon test by band" in out[0][1]
    assert out[0][1].count(b"\n") <= gait.MAX_LINES
    assert b"Camargo" in out[0][1].split(b"\n", 6)[2] or b"Camargo" in out[0][1][:1500]  # attribution in the header


@pytest.mark.skipif(not PROCESSED.exists(), reason="processed Camargo arrays not present")
def test_the_polygon_baseline_uses_the_foot_frame_cop_whatever_the_methods_mapping():
    import json as _json
    spec = gait.load_spec("walk_treadmill")
    spec.update({"subjects": ["AB06"], "stride_cap_per_subject": 1, "speeds_mps": [1.4]})
    manifest = _json.loads((REPO / spec["dataset"]["manifest"]).read_text(encoding="utf-8"))
    got = {}
    for mode in ("hip_reference", "foot_frame"):
        spec["cop_mode"] = mode
        task = gait._tasks(spec, manifest, gait.simrun.MODEL_FILE, REPO / spec["dataset"]["processed"], ["B"], 6.0, 0.0, 1, False, False, False)[0]
        got[mode] = gait.run_stride(task)["feas"]["polygon"]["measured"]["0.025"]
    assert got["hip_reference"] == got["foot_frame"]
    assert len(got["foot_frame"]["single"]) > 10 and len(got["foot_frame"]["double"]) > 5


# ------------------------------------------------------------------------------ T6: trunk modes in one record, the band, the baseline

def test_trunk_modes_accepts_a_name_or_a_list_and_rejects_anything_else():
    assert gait.trunk_modes({"trunk": "rigid"}) == ["rigid"]
    assert gait.trunk_modes({"trunk": ["rigid", "counter_rotate"]}) == ["rigid", "counter_rotate"]
    assert gait.trunk_modes({}) == ["rigid"]
    for bad in ("first_harmonic_typo", [], ["rigid", "rigid"], ["rigid", "x"]):
        with pytest.raises(gait.GaitError):
            gait.trunk_modes({"trunk": bad})


def _agree(corr, rms):
    return {j: {"corr": corr, "rms_pct_ptp": rms} for j in ("hip_fe_right", "hip_fe_left", "knee_right", "knee_left", "ankle_pdflex_right", "ankle_pdflex_left")}


def test_band_requires_correlation_at_least_0p9_and_rms_at_most_15_percent_for_every_sagittal_joint():
    assert (gait.BAND_CORR, gait.BAND_RMS_PCT) == (0.9, 15.0)  # the Decisions block's numbers, named constants
    ok = gait.band_verdict(_agree(0.91, 14.7))
    assert ok["meets"] and set(ok["joints"]) == {"hip_fe", "knee", "ankle_pdflex"}
    assert ok["joints"]["knee"] == {"corr": pytest.approx(0.91), "rms_pct_ptp": pytest.approx(14.7), "meets": True}
    # the band is on the pooled mean of both limbs: one limb at 0.80 and one at 1.0 pool to 0.90, which meets it
    mix = _agree(1.0, 10.0)
    mix["hip_fe_left"]["corr"] = 0.80
    assert gait.band_verdict(mix)["joints"]["hip_fe"]["corr"] == pytest.approx(0.90)


def test_mutation_the_band_fails_on_either_edge():
    assert not gait.band_verdict(_agree(0.8999, 10.0))["meets"]  # correlation just below
    assert not gait.band_verdict(_agree(0.95, 15.0001))["meets"]  # rms just above
    worse = _agree(0.95, 10.0)
    worse["ankle_pdflex_right"]["rms_pct_ptp"] = 40.0  # one joint out is enough
    v = gait.band_verdict(worse)
    assert not v["meets"] and v["joints"]["ankle_pdflex"]["meets"] is False and v["joints"]["hip_fe"]["meets"] is True
    assert not gait.band_verdict({})["meets"]  # no data is not a pass


def test_the_baseline_methods_are_those_that_meet_the_band_at_every_speed_and_mode():
    verdicts = {  # (speed, mode) -> method -> verdict
        ("1.4", "rigid"): {"A_filtered": {"meets": True}, "A_native": {"meets": False}, "B": {"meets": False}, "H": {"meets": False}},
        ("1.6", "rigid"): {"A_filtered": {"meets": True}, "A_native": {"meets": True}, "B": {"meets": False}, "H": {"meets": False}},
    }
    got = gait.baseline_methods(verdicts)
    assert got["baselined"] == ["A_filtered"] and got["not_baselined"] == ["A_native", "B", "H"]
    assert gait.baseline_methods({})["baselined"] == []


@pytest.mark.skipif(not PROCESSED.exists(), reason="processed Camargo arrays not present")
def test_one_record_holds_every_trunk_mode_and_is_byte_identical_on_a_second_run(tmp_path):
    import json
    spec = gait.load_spec("walk_treadmill")
    spec.update({"subjects": ["AB06"], "stride_cap_per_subject": 2, "speeds_mps": [1.4], "trunk": ["rigid", "counter_rotate"]})
    spec["sensitivity"] = {"cutoffs_hz": [4, 6], "pitch_offsets_deg": [0], "stride_cap_per_subject": 1}
    out = []
    for name in ("a", "b"):
        res = gait.run_gait(spec, gait_dir=tmp_path / name, now=dt.datetime(2026, 10, 12, 10, 0))
        out.append((res.json_path.read_bytes(), res.md_path.read_bytes()))
    assert out[0] == out[1]
    rec = json.loads(out[0][0])
    assert rec["trunk"] == ["rigid", "counter_rotate"]
    assert set(rec["results"]["1.4"]) == {"rigid", "counter_rotate"}
    rig, cr = rec["results"]["1.4"]["rigid"], rec["results"]["1.4"]["counter_rotate"]
    # the leg torques of A do not depend on the trunk; B's lateral rows do
    assert rig["joints"]["knee_right"]["A_filtered"] == cr["joints"]["knee_right"]["A_filtered"]
    assert rig["joints"]["hip_aa_right"]["B"] != cr["joints"]["hip_aa_right"]["B"]
    assert set(rec["sensitivity"]["cutoff_hz"]["4"]) == {"rigid", "counter_rotate"}
    assert set(rig["band"]) == {"B", "A_native", "A_filtered", "H"}
    assert out[0][1].count(b"\n") <= gait.MAX_LINES and b"counter_rotate" in out[0][1]
