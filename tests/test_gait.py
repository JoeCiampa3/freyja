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
        out.append((res.json_path.read_bytes(), res.md_path.read_bytes() + res.speed_md_paths["1.4"].read_bytes()))  # the shared file and the speed's file
    assert out[0] == out[1]
    import json
    fe = json.loads(out[0][0])["results"]["1.4"]["rigid"]["feasibility"]
    assert set(fe["polygon"]) == {"B", "measured"} and set(fe["polygon"]["B"]) == {"0.01", "0.025", "0.04"}  # the polygon test at the three bands
    assert set(fe["polygon"]["B"]["0.025"]) == {"single", "double"}
    assert b"Polygon test by band" in out[0][1]
    # Stage 2e T4: the feasibility bins are bins of the stride (frame k of 100), not of each foot's stance; the heading says so
    assert b"by stride-phase bin" in out[0][1] and b"stance-foot phase" not in out[0][1]
    assert res.md_path.read_bytes().count(b"\n") <= gait.MAX_LINES and res.speed_md_paths["1.4"].read_bytes().count(b"\n") <= gait.MAX_LINES
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


def test_the_acceptance_speed_does_not_decide_what_is_baselined():
    """v1's acceptance speed (0.5 m/s) is not a sizing speed: a method that meets the band at the sizing speeds is baselined even if it misses it there.
    The band itself is untouched; an acceptance-speed miss stays in band_verdicts_full_run as a finding."""
    verdicts = {
        ("0.5", "rigid"): {"A_filtered": {"meets": False}, "B": {"meets": False}},
        ("1.4", "rigid"): {"A_filtered": {"meets": True}, "B": {"meets": False}},
        ("1.6", "rigid"): {"A_filtered": {"meets": True}, "B": {"meets": False}},
    }
    got = gait.baseline_methods(verdicts)
    assert got["baselined"] == ["A_filtered"] and got["not_baselined"] == ["B"]
    missed = dict(verdicts); missed[("1.6", "rigid")] = {"A_filtered": {"meets": False}, "B": {"meets": False}}
    assert gait.baseline_methods(missed)["baselined"] == []  # a sizing-speed miss still blocks it
    assert gait.baseline_methods({("0.5", "rigid"): {"A_filtered": {"meets": True}}})["baselined"] == []  # nothing at a sizing speed, nothing baselined


def test_the_acceptance_speeds_agree_between_the_gait_and_the_report():
    import runs_report
    assert tuple(gait.ACCEPTANCE_SPEEDS) == tuple(runs_report.GAIT_ACCEPTANCE_SPEEDS)


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


NEWEST_RECORD = REPO / "sim" / "gait" / "20261011-2317-walk_treadmill" / "gait.json"


@pytest.mark.skipif(not NEWEST_RECORD.exists(), reason="gait.json is untracked and absent on a clean clone")
def test_render_md_takes_the_trunk_mode_order_from_the_spec_not_from_the_stored_key_order():
    """Stage 2b T5b(a): a record stored with sorted keys (modes in alphabetical order) renders as a fresh one (modes in the spec's order)."""
    import json
    stored = json.loads(NEWEST_RECORD.read_text(encoding="utf-8"))
    order = gait.trunk_modes(stored["spec"])
    assert len(order) > 1
    assert list(stored["results"][next(iter(stored["results"]))]) != order  # the stored order differs, so the test can fail
    fresh = json.loads(json.dumps(stored))
    joints = list(gait.yaml.safe_load(gait.MAPPING_FILE.read_text(encoding="utf-8"))["joints"]) + list(gait.EXTRA_JOINTS)  # the model's order
    ordered = lambda d: {j: d[j] for j in joints if j in d}
    by_method = lambda d: {m: d[m] for m in gait.METHODS_ALL if m in d}

    def fresh_cell(d):
        d = dict(d, joints={j: by_method(v) for j, v in ordered(d["joints"]).items()}, residual=by_method(d["residual"]),
                 agreement={m: ordered(v) for m, v in by_method(d["agreement"]).items()})
        if d["kinematics"]:
            d["kinematics"] = dict(d["kinematics"], limit_fraction_mean=ordered(d["kinematics"]["limit_fraction_mean"]))
        return d

    fresh["results"] = {sp: {m: fresh_cell(by[m]) for m in order} for sp, by in stored["results"].items()}
    assert list(stored["results"]["1.4"]["rigid"]["joints"]) != list(fresh["results"]["1.4"]["rigid"]["joints"])  # sorted vs the model's order
    for kind, key in (("cutoff_hz", "cutoffs_hz"), ("pitch_offset_deg", "pitch_offsets_deg")):  # a fresh record: the spec's order of values, modes and joints
        fresh["sensitivity"][kind] = {str(v): {m: {sp: ordered(d) for sp, d in stored["sensitivity"][kind][str(v)][m].items()} for m in order}
                                      for v in stored["spec"]["sensitivity"][key]}
    assert list(stored["sensitivity"]["cutoff_hz"]) != list(fresh["sensitivity"]["cutoff_hz"])  # sorted as strings: '10' before '4'
    assert gait.render_files(stored) == gait.render_files(fresh)  # the shared file and every per-speed file
    cols = next(l for l in gait.render_files(stored)["GAIT-1p4.md"].splitlines() if l.startswith("| joint | B "))
    assert cols.index("B " + gait.TRUNK_SHORT[order[0]]) < cols.index("B " + gait.TRUNK_SHORT[order[1]])


def test_stride_count_counts_each_stride_once_whatever_the_number_of_trunk_modes():
    rec = {"results": {"1.4": {"rigid": {"n_strides": 5}, "counter_rotate": {"n_strides": 5}}, "1.6": {"rigid": {"n_strides": 7}, "counter_rotate": {"n_strides": 7}}}}
    assert gait.stride_count(rec) == 12


def test_the_baseline_stores_the_reproduction_metrics_unrounded(tmp_path, monkeypatch):
    # the record rounds to 6 decimals; the reproduction check compares at 1e-6 relative, so a rounded baseline would fail on small values
    monkeypatch.setattr(gait, "reference_metrics", lambda *a, **k: {"rigid/A_filtered": {"hip_fe_right": {"peak_diff": 0.0189675043, "corr": 0.9, "rms_pct_ptp": 1.0}}})
    ver = {"meets": True, "joints": {}}
    rec = {"spec": {}, "snapshot_sha256": "s", "model_sha256": "m", "spec_sha256": "p", "git_commit": "c", "git_dirty": False, "gait_id": "gait.x",
           "dataset_manifest_sha256": "d", "results": {"1.4": {"rigid": {"band": {"A_filtered": {"all": ver, "without_offset": ver}}}}}}
    path = gait.write_baseline(rec, tmp_path / "w.json")
    import json
    got = json.loads(path.read_text(encoding="utf-8"))["reproduction"]["metrics"]["rigid/A_filtered"]["hip_fe_right"]["peak_diff"]
    assert got == 0.0189675043


@pytest.mark.skipif(not PROCESSED.exists(), reason="processed Camargo arrays not present")
@pytest.mark.parametrize("mode", gait.TRUNK_MODES)
def test_torques_above_the_pelvis_are_identical_across_methods_in_each_trunk_mode(mode):
    """The foot Jacobians have no columns above the pelvis, so the ground wrench cannot reach those rows: they depend on the kinematics and the
    trunk mode alone. If this fails the envelope's above-the-pelvis rows must not be added (brief T7)."""
    import json as _json
    spec = gait.load_spec("walk_treadmill")
    spec.update({"subjects": ["AB06", "AB12"], "stride_cap_per_subject": 1, "speeds_mps": [1.4, 1.6]})
    manifest = _json.loads((REPO / spec["dataset"]["manifest"]).read_text(encoding="utf-8"))
    tasks = gait._tasks(spec, manifest, gait.simrun.MODEL_FILE, REPO / spec["dataset"]["processed"], list(spec["methods"]), 6.0, 0.0, 1, False, False, False, trunk=mode)
    assert len(tasks) == 4
    for t in tasks:
        t["keep_torque"] = True
        tor = gait.run_stride(t)["torque"]
        for j in gait.EXTRA_JOINTS:
            ref = np.array(tor["B"][j])
            assert np.abs(ref).max() > 1e-3  # the rows are not trivially zero
            for m in ("A_native", "A_filtered", "H"):
                assert np.abs(np.array(tor[m][j]) - ref).max() <= 1e-9 * max(1.0, np.abs(ref).max()), (mode, t["subject"], t["speed"], m, j)


# ------------------------------------------------------------------------------ T9.3: every statistic also without the pitch-flagged subjects

def test_aggregate_adds_a_third_set_only_when_a_pitch_subset_is_given():
    v = np.arange(1.0, 101.0)
    keep = np.arange(100) >= 10
    assert set(gait.aggregate(v, keep)) == {"all", "without_offset"}  # unchanged when no subject is pitch-flagged
    keep_pitch = np.arange(100) >= 20
    a = gait.aggregate(v, keep, keep_pitch)
    assert set(a) == {"all", "without_offset", "without_pitch_flagged"}
    assert a["without_pitch_flagged"]["mean"] == pytest.approx(60.5) and a["without_pitch_flagged"]["max"] == 100.0
    assert a["without_pitch_flagged"]["p95"] == pytest.approx(np.percentile(v[20:], 95))
    assert a["all"] == gait.aggregate(v, keep)["all"]  # the other sets are untouched


def test_agg_over_drops_the_flagged_subjects_from_the_third_set_and_the_offset_subjects_from_the_second():
    rows = [{"subject": s, "x": x} for s, x in (("AB06", 1.0), ("AB07", 2.0), ("AB13", 30.0), ("AB19", 50.0))]
    ex = gait.Exclusions(offset={"AB13"}, pitch={"AB07", "AB19"})
    a = gait._agg_over(rows, lambda r: r["x"], ex)
    assert a["without_offset"]["max"] == 50.0 and a["without_pitch_flagged"]["max"] == 30.0 and a["all"]["max"] == 50.0
    assert "without_pitch_flagged" not in gait._agg_over(rows, lambda r: r["x"], gait.Exclusions(offset={"AB13"}, pitch=set()))


@pytest.mark.skipif(not PROCESSED.exists(), reason="processed Camargo arrays not present")
def test_the_record_gives_every_statistic_and_the_band_without_the_pitch_flagged_subjects(tmp_path):
    import json
    spec = gait.load_spec("walk_treadmill")
    spec.update({"subjects": ["AB06", "AB07"], "stride_cap_per_subject": 1, "speeds_mps": [1.4], "trunk": "rigid", "pitch_flag_subjects": ["AB07"]})
    spec["sensitivity"] = {"cutoffs_hz": [6], "pitch_offsets_deg": [0], "stride_cap_per_subject": 1}
    rec = json.loads(gait.run_gait(spec, gait_dir=tmp_path, now=dt.datetime(2026, 10, 12, 10, 0)).json_path.read_text(encoding="utf-8"))
    d = rec["results"]["1.4"]["rigid"]
    assert d["n_strides_without_pitch_flagged"] == 1 and d["n_strides"] == 2
    st = d["joints"]["knee_right"]["A_filtered"]["peak_torque_nm"]
    assert set(st) == {"all", "without_offset", "without_pitch_flagged"}
    assert set(d["band"]["A_filtered"]) == {"all", "without_offset", "without_pitch_flagged"}
    md = (tmp_path / next(p.name for p in tmp_path.iterdir()) / "GAIT-1p4.md").read_text(encoding="utf-8")
    assert "Pitch-flagged subjects (kept" in md and "AB07" in md.split("Pitch-flagged subjects", 1)[1][:400]
    assert "without pitch flagged" in md  # the band row has its third verdict


def test_the_spec_lists_only_subjects_that_exist():
    import json
    spec = gait.load_spec("walk_treadmill")
    manifest = json.loads((REPO / spec["dataset"]["manifest"]).read_text(encoding="utf-8"))
    for key in ("offset_subjects", "pitch_flag_subjects"):
        assert set(spec.get(key, [])) <= set(manifest["subjects"]), key


# ------------------------------------------------------------------------------ Stage 2f: 0.5 m/s, v1's acceptance speed

def test_the_walk_spec_adds_the_acceptance_speed_and_changes_nothing_else():
    import json
    import yaml
    spec = gait.load_spec("walk_treadmill")
    assert spec["speeds_mps"] == [0.5, 1.4, 1.6]
    ingest = yaml.safe_load((REPO / "data" / "camargo2021" / "ingest_spec.yaml").read_text(encoding="utf-8"))
    manifest = json.loads((REPO / spec["dataset"]["manifest"]).read_text(encoding="utf-8"))
    assert set(spec["speeds_mps"]) <= set(ingest["speeds_mps"])  # a speed the gait run asks for was ingested
    for sp in spec["speeds_mps"]:
        assert all(s["strides"][str(sp)] > 0 for s in manifest["subjects"].values()), sp
    # everything the Stage 2f brief leaves alone
    assert spec["methods"] == ["B", "A_native", "A_filtered", "H"] and spec["trunk"] == ["rigid", "counter_rotate"]
    assert spec["smoothing"] == {"cutoff_hz": 6.0} and spec["root_rule"] == "pelvis_dataset" and spec["root_reference"] == "hip_midpoint"
    assert spec["pitch_mean"] == "measured" and spec["pelvis_pitch_offset_deg"] == 0.0 and spec["cop_mode"] == "hip_reference" and spec["cop_scale"] == 1.0
    assert spec["offset_subjects"] == ["AB13", "AB15"] and spec["pitch_flag_subjects"] == ["AB07", "AB12", "AB18", "AB19"]
    assert spec["sensitivity"] == {"cutoffs_hz": [4, 6, 10, 15], "pitch_offsets_deg": [-5, 0, 5], "stride_cap_per_subject": 4}
    assert (gait.BAND_CORR, gait.BAND_RMS_PCT, gait.BAND_STEMS) == (0.9, 15.0, ("hip_fe", "knee", "ankle_pdflex"))


@pytest.mark.skipif(not PROCESSED.exists(), reason="processed Camargo arrays not present")
def test_a_three_speed_record_is_a_shared_file_and_one_file_per_speed_each_under_the_cap(tmp_path):
    import json
    spec = gait.load_spec("walk_treadmill")
    spec.update({"subjects": ["AB06"], "stride_cap_per_subject": 1, "speeds_mps": [0.5, 1.4, 1.6]})
    spec["sensitivity"] = {"cutoffs_hz": [6], "pitch_offsets_deg": [0], "stride_cap_per_subject": 1}
    res = gait.run_gait(spec, gait_dir=tmp_path, now=dt.datetime(2026, 10, 12, 10, 0))
    rec = json.loads(res.json_path.read_text(encoding="utf-8"))
    assert list(rec["results"]) == ["0.5", "1.4", "1.6"] and len(rec["subjects"]) == 1
    for sp in ("0.5", "1.4", "1.6"):
        d = rec["results"][sp]["rigid"]
        assert d["n_strides"] == 1 and rec["subjects"]["AB06"]["strides"][sp] == 2  # one stride, two trunk modes
        for j, by_method in d["joints"].items():
            for m, stats in by_method.items():
                assert np.isfinite(stats["peak_torque_nm"]["all"]["max"]), (sp, j, m)
    assert sorted(p.name for p in res.md_path.parent.glob("GAIT*.md")) == ["GAIT-0p5.md", "GAIT-1p4.md", "GAIT-1p6.md", "GAIT.md"]
    assert set(res.speed_md_paths) == {"0.5", "1.4", "1.6"}
    shared = res.md_path.read_text(encoding="utf-8")
    assert "## 0.5 m/s" not in shared and all(f"GAIT-{t}.md" in shared for t in ("0p5", "1p4", "1p6"))  # the shared file points at the per-speed files
    assert "## Band" in shared and all(f"| {sp} |" in shared.split("## Band", 1)[1].split("\n## ", 1)[0] for sp in ("0.5", "1.4", "1.6"))  # the band table has every speed
    for sp, path in res.speed_md_paths.items():
        text = path.read_text(encoding="utf-8")
        assert f"## {sp} m/s" in text and "Assumptions:" not in text and "(truncated at" not in text and text.count("\n") <= gait.MAX_LINES
    assert shared.count("\n") <= gait.MAX_LINES and "(truncated at" not in shared


def test_every_file_of_the_newest_three_speed_record_fits_the_cap_untruncated():
    """Stage 2f D2: the shared GAIT.md and each GAIT-<speed>.md are under gait.MAX_LINES, so no speed is cut off (the old single file was 543 lines)."""
    import json
    rec_path = max((REPO / "sim" / "gait").glob("*/gait.json"), key=lambda p: p.parent.name, default=None)
    if rec_path is None:
        pytest.skip("no gait record on this machine")
    rec = json.loads(rec_path.read_text(encoding="utf-8"))
    if len(rec["results"]) < 3:
        pytest.skip("the newest record on this machine predates the 0.5 m/s layout")
    files = gait.render_files(rec)
    assert set(files) == {"GAIT.md"} | {f"GAIT-{gait.speed_tag(sp)}.md" for sp in rec["results"]}
    for name, text in files.items():
        assert "(truncated at" not in text and text.count("\n") <= gait.MAX_LINES, name
