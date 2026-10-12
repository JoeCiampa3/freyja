"""
Stage 2b T3: the tracked gait extract (sim/benchmarks/gait_extract.json, schema gait-extract/1). The pure functions on synthetic input with
known answers, the extract's determinism and schema, the envelope read from it (mutation: change one value, the envelope changes), and the
tracked extract against the numbers memo6 printed.

Run from the repo root:
    python -m pytest tests/test_gait_extract.py
"""
import copy
import hashlib
import json
import sys
from pathlib import Path

import numpy as np
import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "sim" / "scripts"))
sys.path.insert(0, str(REPO / "analysis"))
sys.path.insert(0, str(REPO / "tests"))

import gait_extract as ge  # noqa: E402
import runrecord  # noqa: E402
import runs_report as rp  # noqa: E402
from test_runs_report import gait_extract_fixture, gait_record, summary  # noqa: E402

SPEEDS = ("1.4", "1.6")


# ------------------------------------------------------------------------------ the pure functions

def test_joint_distribution_and_metrics_are_the_diagnostics_own():
    import gait_diag as gd
    assert gd.distribution is ge.distribution and gd.joint_metrics is ge.joint_metrics and gd.VARIANTS is ge.VARIANTS  # moved, not copied


def _rows(values_by_variant, speed="1.4"):
    """Subject-stride rows as `_lsj_task` returns them: two strides per variant, the lateral joint's torque given, the rest 0."""
    out = []
    for v, vals in values_by_variant.items():
        for k, x in enumerate(vals):
            m = {"peak_angle_deg": x / 10, "peak_torque_nm": x, "peak_speed_rad_s": 1.0, "peak_power_pos_w": 2 * x, "peak_regen_w": 0.0}
            out.append({"subject": f"AB{k}", "speed": speed, "variant": v, "metrics": {"lsj_lat": m, "lsj_ax": {k2: 0.0 for k2 in m}}})
    return out


def test_the_lumbosacral_table_is_the_distribution_of_each_metric_per_speed_joint_and_variant():
    vals = {v: list(np.arange(1.0, 101.0) * (i + 1)) for i, v in enumerate(ge.VARIANTS)}
    t = ge.lsj_table(_rows(vals), ["1.4"])
    for i, v in enumerate(ge.VARIANTS):
        d = t["1.4"]["lsj_lat"][v]["peak_torque_nm"]
        assert d["median"] == pytest.approx(50.5 * (i + 1), abs=1e-9)
        assert d["p95"] == pytest.approx(95.05 * (i + 1), abs=1e-9)
        assert d["max"] == pytest.approx(100.0 * (i + 1), abs=1e-9)
    assert t["1.4"]["lsj_ax"]["rigid"]["peak_torque_nm"]["max"] == 0.0


def test_the_lumbosacral_table_does_not_mix_speeds_or_variants():
    rows = (_rows({"rigid": [10.0, 20.0], "counter_rotate": [5000.0]}, "1.4") + _rows({"rigid": [1000.0], "counter_rotate": [7.0]}, "1.6"))
    t = ge.lsj_table(rows, ["1.4", "1.6"], variants=("rigid", "counter_rotate"))
    assert t["1.4"]["lsj_lat"]["rigid"]["peak_torque_nm"]["max"] == 20.0
    assert t["1.6"]["lsj_lat"]["rigid"]["peak_torque_nm"]["max"] == 1000.0
    assert t["1.4"]["lsj_lat"]["counter_rotate"]["peak_torque_nm"]["max"] == 5000.0
    assert t["1.6"]["lsj_lat"]["counter_rotate"]["peak_torque_nm"]["max"] == 7.0


def test_a_sagittal_rows_of_a_pure_gain_have_that_slope_and_peak_ratio_and_the_scaled_peak_is_force_by_mass_and_lever_by_leg_ratio():
    t = np.linspace(0, 2 * np.pi, 100, endpoint=False)
    S = []
    for k, (amp, ratio) in enumerate(((1.0, 0.9), (1.6, 1.0), (2.2, 1.05))):
        data = {j: amp * np.sin(t + 0.1 * i) for i, j in enumerate(ge.A_JOINTS)}
        S.append({"subject": f"AB{k}", "leg_ratio": ratio, "data": data, "tau": {j: 1.25 * 60.0 * v for j, v in data.items()}})
    r = ge.a_sagittal_rows(S, 60.0)
    assert set(r) == set(ge.A_JOINTS) | set(ge.A_STEMS)
    for j in ge.A_JOINTS:
        assert r[j]["ols_slope"] == pytest.approx(1.25, abs=1e-12)
        assert r[j]["peak_ratio"] == pytest.approx(1.25, abs=1e-12)
        peaks = np.array([np.abs(s["data"][j]).max() * 60.0 * s["leg_ratio"] for s in S])
        assert r[j]["scaled_peak_nm"] == {"mean": pytest.approx(peaks.mean()), "p95": pytest.approx(np.percentile(peaks, 95)), "max": pytest.approx(peaks.max())}
    assert r["knee"]["ols_slope"] == pytest.approx(1.25, abs=1e-12)  # the stem pools both limbs, as memo7's table does


def test_a_sagittal_rows_see_an_offset_in_the_ratio_but_not_in_the_slope():
    t = np.linspace(0, 2 * np.pi, 100, endpoint=False)
    data = {j: 2.0 * np.sin(t) for j in ge.A_JOINTS}
    S = [{"subject": "AB0", "leg_ratio": 1.0, "data": data, "tau": {j: 50.0 * (v + 1.0) for j, v in data.items()}}]
    r = ge.a_sagittal_rows(S, 50.0)["ankle_pdflex_right"]
    assert r["ols_slope"] == pytest.approx(1.0, abs=1e-12)  # a constant added to the model changes no slope
    assert r["peak_ratio"] == pytest.approx(3.0 / 2.0, abs=1e-9)  # but it changes the peak: 3 per kg (2 sin + 1 at its maximum) against the dataset's 2


def test_hip_demand_from_the_vertical_adds_the_pelvis_list_and_the_median_tilt_is_the_median_of_stride_means():
    n = 101
    t = np.linspace(0, 2 * np.pi, n)
    strides = []
    for tilt in (4.0, 6.0, 8.0):
        hip = 20.0 * np.sin(t) - 10.0 - tilt  # extension relative to the pelvis: 30 + tilt at the minimum
        strides.append({"hip_r": hip, "hip_l": hip + 3.0, "list": np.full(n, tilt)})
    d = ge.hip_demand_rows(strides)
    assert d["pelvis_relative_deg"]["median"] == pytest.approx(36.0)  # 30 + 6
    assert d["vertical_deg"]["median"] == pytest.approx(30.0)  # hip + list: the tilt cancels
    assert d["posterior_pelvic_tilt_median_deg"] == pytest.approx(6.0)
    assert d["vertical_deg"]["max"] == pytest.approx(30.0) and d["pelvis_relative_deg"]["max"] == pytest.approx(38.0)


# ------------------------------------------------------------------------------ the extract

def _extract(**kw):
    return gait_extract_fixture(**kw)


def test_the_extract_is_a_pure_function_of_its_inputs_and_byte_identical():
    a, b = ge.dumps(_extract()), ge.dumps(_extract())
    assert a == b and "\r" not in a and a.endswith("\n")
    assert hashlib.sha256(a.encode()).hexdigest() == hashlib.sha256(b.encode()).hexdigest()


def test_the_extract_validates_against_its_schema_and_a_broken_one_does_not():
    ge.validate(_extract())
    bad = _extract()
    del bad["results"]["1.4"]["rigid"]["band"]
    with pytest.raises(Exception):
        ge.validate(bad)
    bad = _extract()
    bad["schema"] = "gait-extract/2"
    with pytest.raises(Exception):
        ge.validate(bad)


def test_the_extract_is_stamped_like_the_baseline_and_carries_no_timestamp_or_absolute_path():
    e = _extract()
    for k in ("generated_by", "inputs", "schema", "snapshot_sha256", "model_sha256", "spec_sha256", "dataset_manifest_sha256", "git_commit", "git_dirty", "diff_sha256", "gait_id"):
        assert k in e, k
    text = ge.dumps(e)
    assert "C:\\" not in text and "/Users/" not in text and "T0" not in text.replace("T0.", "")


def test_the_extract_keeps_both_p95_and_max_under_each_of_the_exclusion_sets_the_record_has():
    rec = gait_record()
    e = _extract()
    j = e["results"]["1.4"]["rigid"]["joints"]["knee_right"]["A_filtered"]["peak_torque_nm"]
    src = rec["results"]["1.4"]["rigid"]["joints"]["knee_right"]["A_filtered"]["peak_torque_nm"]
    assert set(j) == set(src) == {"all", "without_offset"}
    for s in src:
        assert j[s] == {"p95": pytest.approx(src[s]["p95"]), "max": pytest.approx(src[s]["max"])}
    assert e["results"]["1.4"]["rigid"]["n_strides"] == 10 and e["results"]["1.4"]["rigid"]["n_strides_without_offset"] == 9
    assert e["spec"]["offset_subjects"] == ["AB13", "AB15"] and e["subjects"]["count"] == 10


def test_a_third_exclusion_set_in_the_record_is_carried_too():
    rec = gait_record()
    for by_mode in rec["results"].values():
        for d in by_mode.values():
            for j in d["joints"].values():
                for m in j.values():
                    for k in m:
                        m[k]["without_pitch_flagged"] = dict(m[k]["all"])
    e = ge.assemble(rec, *_extras())
    assert set(e["results"]["1.4"]["rigid"]["joints"]["knee_right"]["B"]["peak_torque_nm"]) == {"all", "without_offset", "without_pitch_flagged"}


def _extras():
    f = _extract()
    return f["lumbosacral"], f["a_filtered_sagittal"], f["hip_demand"]


def test_the_pooled_agreement_is_the_mean_of_the_two_limbs():
    rec = gait_record()
    d = rec["results"]["1.4"]["rigid"]["agreement"]["A_filtered"]
    d["hip_fe_right"]["corr"], d["hip_fe_left"]["corr"] = 0.90, 0.80
    e = ge.assemble(rec, *_extras())
    assert e["results"]["1.4"]["rigid"]["agreement"]["A_filtered"]["hip_fe"]["all"]["corr"] == pytest.approx(0.85)


# ------------------------------------------------------------------------------ the envelope reads the extract

def _env(extract):
    return rp.envelope([summary("run.20261002-0900-sweep", "sweep")], gait=extract)


def _row(text, joint, speed="1.4", method="A_filtered"):
    return next(l for l in text.splitlines() if l.startswith("| gait ") and f" {joint} " in l and f"| {speed} |" in l and f"| {method} |" in l)


def test_the_envelope_text_follows_the_extract_and_mutating_one_value_changes_it():
    base = _env(_extract())
    assert "| 40.0 |" in _row(base, "knee_right")  # the synthetic A_filtered p95
    e = _extract()
    e["results"]["1.4"]["rigid"]["joints"]["knee_right"]["A_filtered"]["peak_torque_nm"]["all"]["p95"] = 41.5
    mutated = _env(e)
    assert mutated != base and "| 41.5 |" in _row(mutated, "knee_right")
    assert _env(_extract()) == base  # and nothing else moved it


def test_the_envelope_does_not_read_a_gait_json():
    import inspect
    assert "gait.json" not in inspect.getsource(rp.gait_section) and not hasattr(rp, "load_latest_gait")
    assert "gait_extract.json" in rp.GENERATED_ENVELOPE and "untracked" not in rp.GENERATED_ENVELOPE


def test_the_lumbosacral_rows_show_all_three_trunk_modes_and_the_spread_of_the_quartile_corners():
    text = _env(_extract())
    rows = [l for l in text.splitlines() if l.startswith("| gait ") and "lsj_lat" in l and "first_harmonic" in l]
    assert rows, "no lumbosacral three-mode rows"
    for mode in ("rigid", "counter_rotate", "first_harmonic"):
        assert any(f"| {mode}" in l for l in text.splitlines() if "lsj_lat" in l and l.startswith("| gait ")), mode
        assert any(f"| {mode}" in l for l in text.splitlines() if "lsj_ax" in l and l.startswith("| gait ")), mode
    fh = next(l for l in rows if "| 1.4 |" in l)
    assert "32.1" in fh  # the fixture's first_harmonic median p95 torque, with its corners' range beside it
    assert ".." in fh


def test_the_a_filtered_comparison_columns_are_there_per_speed_and_limb_and_carry_no_flag():
    text = _env(_extract())
    row = next(l for l in text.splitlines() if l.startswith("| gait ") and "ankle_pdflex_right" in l and "dataset-direct" in l and "| 1.4 |" in l)
    assert "102.5 / 123.0 / 135.3" in row  # scaled dataset peak: mean, p95, max (the fixture's 102.5, x1.2, x1.32)
    assert "1.185" in row and "1.24" in row  # OLS slope, peak ratio
    assert "flag" not in row.lower() and "provisional" not in row
    assert "OLS slope" in text and "dataset-direct" in text  # the text says what each column is


def test_the_functional_demand_rows_have_the_vertical_and_pelvis_referenced_hip_extension_and_the_median_tilt():
    text = _env(_extract())
    line = next(l for l in text.splitlines() if "from the vertical" in l and "1.4 m/s" in l)
    assert "22.0" in line and "relative to the pelvis" in line and "7.6" in line


# ------------------------------------------------------------------------------ the tracked extract and the tracked envelope

TRACKED = REPO / "sim" / "benchmarks" / "gait_extract.json"


def test_the_tracked_extract_exists_validates_and_has_memo6s_lateral_lumbosacral_torques():
    assert TRACKED.is_file(), "run `fy gait walk_treadmill --write-extract`"
    e = json.loads(TRACKED.read_text(encoding="utf-8"))
    ge.validate(e)
    assert ge.dumps(e) == TRACKED.read_text(encoding="utf-8")  # canonical form: sorted keys, LF
    p95 = lambda sp, v: e["lumbosacral"][sp]["lsj_lat"][v]["peak_torque_nm"]["p95"]
    assert (round(p95("1.4", "first_harmonic median"), 1), round(p95("1.6", "first_harmonic median"), 1)) == (32.1, 40.7)  # memo6, T9.1
    assert (round(p95("1.4", "counter_rotate"), 1), round(p95("1.6", "counter_rotate"), 1)) == (23.5, 27.6)
    assert (round(p95("1.4", "rigid"), 1), round(p95("1.6", "rigid"), 1)) == (93.0, 110.4)
    assert e["results"]["1.4"]["rigid"]["n_strides"] == 469 and e["results"]["1.6"]["rigid"]["n_strides"] == 519


def test_the_tracked_envelope_is_what_the_tracked_extract_and_run_records_produce():
    """The clean-clone property: `fy runs envelope` needs no untracked file."""
    meta = json.loads((REPO / "params" / "snapshot.meta.json").read_text(encoding="utf-8"))
    text = rp.envelope(runrecord.load_summaries(runrecord.RUNS_DIR), meta["model_sha256"], gait=rp.load_gait_extract())
    assert text == (REPO / "sim" / "runs" / "ENVELOPE.md").read_text(encoding="utf-8")
