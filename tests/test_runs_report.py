"""
Stage 1 T4: query (list, show, compare), digest and envelope, all on synthetic summaries. Records are built through
the schema, so they are valid by construction. No MuJoCo, no network.

Run from the repo root:
    python -m pytest tests
"""
import copy
import hashlib
import io
import json
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "sim" / "scripts"))

import runrecord as rr  # noqa: E402
import runs_report as rp  # noqa: E402


def sha(text):
    return hashlib.sha256(text.encode()).hexdigest()


def joint(tpk=10.0, trms=5.0, wpk=2.0, ppk=20.0, rom=(-5.0, 30.0), limit=(-18.0, 134.0), hit=0.0, source="applied"):
    return {"torque_source": source, "torque_peak_nm": tpk, "torque_rms_nm": trms, "speed_peak_rad_s": wpk,
            "power_peak_w": ppk, "rom_used_deg": list(rom), "rom_limit_deg": None if limit is None else list(limit),
            "limit_hit_fraction": None if limit is None else hit}


def summary(run_id, scenario, joints=None, **over):
    rec = {
        "schema": "run-summary/1", "run_id": run_id,
        "git_commit": "a" * 40, "git_dirty": False, "diff_sha256": None,
        "snapshot_sha256": sha("snap1"), "model_sha256": sha("model1"), "seed": 0,
        "env": {"mujoco": "3.10.0", "python": "3.11.9", "numpy": "2.4.6"},
        "scenario": {"name": scenario, "params": {"gain": 1.0}},
        "controller": {"name": "c", "version": "1"},
        "timestep_s": 0.002, "duration_s": 3.0, "support": "ground", "window": {"start_s": 1.0, "end_s": 3.0},
        "outcome": "completed",
        "joints": joints if joints is not None else {"hip_fe_right": joint(), "knee_right": joint(tpk=3.0)},
        "contacts": {"foot_right": {"normal_force_peak_n": 330.0, "friction_ratio_peak": 0.05}},
        "balance": {"support_margin_min_m": 0.02},
        "checks": {"passed": ["check.a.b"], "failed": [], "waived": [], "status_model_sha256": sha("model1"), "status_stale": False},
    }
    rec.update(over)
    rr.validate(rec)
    return rec


def write_all(d, records):
    for r in records:
        rr.write_summary(r, d)


LEG_STEMS = ("hip_fe", "hip_aa", "hip_ier", "knee", "ankle_pdflex", "ankle_ie")
LEG_JOINTS = [f"{s}_{side}" for s in LEG_STEMS for side in ("right", "left")]
EXTRA = ("lsj_fe", "lsj_lat", "lsj_ax", "tj_fe", "cj_fe")
MODES = ("rigid", "counter_rotate")
GAIT_METHODS = ("B", "A_native", "A_filtered", "H")


def _stats(p95):
    return {"all": {"mean": 0.8 * p95, "p95": p95, "max": 1.2 * p95}, "without_offset": {"mean": 0.8 * p95, "p95": 0.99 * p95, "max": 1.1 * p95}}


def _verdict(corr, rms, meets=None):
    ok = corr >= 0.9 and rms <= 15.0 if meets is None else meets
    return {"meets": ok, "joints": {s: {"corr": corr, "rms_pct_ptp": rms, "meets": ok} for s in ("hip_fe", "knee", "ankle_pdflex")}}


ZERO_P5_VERDICT = {"meets": False, "joints": {"hip_fe": {"corr": 0.861, "rms_pct_ptp": 20.1, "meets": False}, "knee": {"corr": 0.892, "rms_pct_ptp": 20.2, "meets": False},
                                              "ankle_pdflex": {"corr": 0.975, "rms_pct_ptp": 8.7, "meets": True}}}


def gait_record(model_sha=None, a_filtered_meets=True, h_meets=False, ids="gait.20261012-0900-walk_treadmill", acceptance=False):
    """A synthetic gait-summary: B p95 100, A_native 50, A_filtered 40, H 70 N m at every leg joint (x1.1 at 1.6 m/s); spine rows differ by trunk mode."""
    base = {"B": 100.0, "A_native": 50.0, "A_filtered": 40.0, "H": 70.0}
    results = {}
    speeds = ("0.5", "1.4", "1.6") if acceptance else ("1.4", "1.6")  # 0.5 m/s: v1's acceptance speed; A_filtered misses the band there at hip and knee, as measured
    for sp in speeds:
        k_sp = {"0.5": 0.6, "1.4": 1.0, "1.6": 1.1}[sp]
        results[sp] = {}
        for mode in MODES:
            f = 1.0 if mode == "rigid" else 0.5
            joints = {j: {m: {"peak_torque_nm": _stats(base[m] * k_sp), "peak_speed_rad_s": _stats(3.0), "peak_power_pos_w": _stats(200.0),
                              "peak_regeneration_w": _stats(120.0)} for m in GAIT_METHODS} for j in LEG_JOINTS}
            for j in EXTRA:
                joints[j] = {m: {"peak_torque_nm": _stats(60.0 * f), "peak_speed_rad_s": _stats(1.5 * f), "peak_power_pos_w": _stats(30.0 * f),
                                 "peak_regeneration_w": _stats(20.0 * f)} for m in GAIT_METHODS}
            agree = {m: {j: {"corr": c, "rms_pct_ptp": r, "peak_diff": 0.0, "corr_without_offset": c, "rms_pct_ptp_without_offset": r} for j in LEG_JOINTS}
                     for m, (c, r) in {"B": (0.3, 60.0), "A_native": (0.88, 17.0), "A_filtered": (0.95, 12.0), "H": (0.95 if h_meets else 0.7, 10.0 if h_meets else 30.0)}.items()}
            for j in LEG_JOINTS:  # the off-band stems of A_filtered, as measured: hip ab/adduction 0.97 / 18%, hip rotation 0.86 / 18%, ankle inversion -0.12 / 108%
                c, r = {"hip_aa": (0.97, 18.0), "hip_ier": (0.86, 18.0), "ankle_ie": (-0.12, 108.0)}.get(j[:-6] if j.endswith("_right") else j[:-5], (0.95, 12.0))
                agree["A_filtered"][j].update(corr=c, rms_pct_ptp=r, corr_without_offset=c, rms_pct_ptp_without_offset=r)
            if sp == "0.5":
                for j in LEG_JOINTS:
                    c, r = {"hip_fe": (0.861, 20.1), "knee": (0.892, 20.2), "ankle_pdflex": (0.975, 8.7)}.get(j[:-6] if j.endswith("_right") else j[:-5], (None, None))
                    if c is not None:
                        agree["A_filtered"][j].update(corr=c, rms_pct_ptp=r, corr_without_offset=c, rms_pct_ptp_without_offset=r)
            results[sp][mode] = {
                "n_strides": 10, "n_strides_without_offset": 9, "joints": joints, "agreement": agree,
                "band": {"B": {"all": _verdict(0.3, 60.0), "without_offset": _verdict(0.3, 60.0)}, "A_native": {"all": _verdict(0.88, 17.0), "without_offset": _verdict(0.88, 17.0)},
                         "A_filtered": ({"all": ZERO_P5_VERDICT, "without_offset": ZERO_P5_VERDICT} if sp == "0.5"
                                        else {"all": _verdict(0.95, 12.0, a_filtered_meets), "without_offset": _verdict(0.95, 12.0, a_filtered_meets)}),
                         "H": {"all": _verdict(0.95, 10.0) if h_meets else _verdict(0.7, 30.0), "without_offset": _verdict(0.7, 30.0)}},
                "trunk_peak_deg": {"lsj_lat": _stats(7.4 * f), "lsj_ax": _stats(11.9 * f)},
                "hip_extension": {"median_deg": 23.0, "p95_deg": 36.0, "max_deg": 39.0, "stop_deg": -18.1, "fraction_beyond_stop": 0.85}}
    results = {sp: dict(sorted(by.items())) for sp, by in results.items()}  # written records have sorted keys: the spec's order is rec["trunk"]
    return {"schema": "gait-summary/1", "gait_id": ids, "git_commit": "b" * 40, "git_dirty": False, "snapshot_sha256": sha("snap1"),
            "model_sha256": model_sha or sha("model1"), "trunk": list(MODES), "hybrid_methods": [],
            "spec": {"name": "walk_treadmill", "offset_subjects": ["AB13", "AB15"], "speeds_mps": [float(x) for x in speeds]},
            "assumptions": ["rigid at the standing pose, arms at the sides; arm swing is not modelled"],
            "subjects": {f"AB{i}": {"strides": {x: 1 for x in speeds}} for i in range(10)}, "results": results}


def gait_extras(acceptance=False):
    """Synthetic lumbosacral, A_filtered-sagittal and hip-demand tables in the shapes `gait_extract` computes (known numbers, no MuJoCo)."""
    import gait_extract as ge
    dist = lambda med, p95, mx: {"median": med, "p95": p95, "max": mx}
    # p95 torque by variant at 1.4 m/s: rigid 93.0, counter_rotate 23.5, first_harmonic median 32.1, the four corners 28.0 to 36.0
    p95 = {"rigid": 93.0, "counter_rotate": 23.5, "first_harmonic median": 32.1, "first_harmonic q1 gain, q1 lag": 28.0, "first_harmonic q1 gain, q3 lag": 30.0,
           "first_harmonic q3 gain, q1 lag": 34.0, "first_harmonic q3 gain, q3 lag": 36.0}
    lsj = {}
    for sp, k in ((("0.5", 0.5),) if acceptance else ()) + (("1.4", 1.0), ("1.6", 1.2)):
        lsj[sp] = {j: {v: {"peak_angle_deg": dist(5.0, 8.9 * (0.0 if v == "rigid" else 1.0), 11.0), "peak_torque_nm": dist(0.5 * x * k * s, x * k * s, 1.5 * x * k * s),
                            "peak_speed_rad_s": dist(1.0, 1.8, 2.5), "peak_power_pos_w": dist(5.0, 31.0, 60.0), "peak_regen_w": dist(4.0, 20.0, 40.0)}
                       for v, x in p95.items()} for j, s in (("lsj_lat", 1.0), ("lsj_ax", 0.1))}
    a = {}
    for sp, k in ((("0.5", 0.55),) if acceptance else ()) + (("1.4", 1.0), ("1.6", 1.02)):
        a[sp] = {}
        for stem, base in (("hip_fe", 50.0), ("knee", 48.0), ("ankle_pdflex", 102.5)):
            for side in ("right", "left"):
                a[sp][f"{stem}_{side}"] = {"scaled_peak_nm": {"mean": base * k, "p95": 1.2 * base * k, "max": 1.32 * base * k}, "ols_slope": 1.185 if stem == "ankle_pdflex" else 0.68, "peak_ratio": 1.24 if stem == "ankle_pdflex" else 0.9}
            a[sp][stem] = {"scaled_peak_nm": {"mean": base * k, "p95": 1.2 * base * k, "max": 1.32 * base * k}, "ols_slope": 1.185 if stem == "ankle_pdflex" else 0.68, "peak_ratio": 1.24 if stem == "ankle_pdflex" else 0.9}
    demand = {sp: {"vertical_deg": dist(16.9, 22.0, 25.3), "pelvis_relative_deg": dist(23.3, 37.3, 39.4), "posterior_pelvic_tilt_median_deg": 7.6} for sp in (("0.5",) if acceptance else ()) + ("1.4", "1.6")}
    assert tuple(lsj["1.4"]["lsj_lat"]) == ge.VARIANTS
    return lsj, a, demand


def gait_extract_fixture(**kw):
    import gait_extract as ge
    return ge.assemble(gait_record(**kw), *gait_extras(acceptance=kw.get("acceptance", False)))


class GaitEnvelope(unittest.TestCase):
    def rows(self, text, prefix):
        return [l for l in text.splitlines() if l.startswith(prefix)]

    def text(self, **kw):
        return rp.envelope([summary("run.20261002-0900-sweep", "sweep")], gait=gait_extract_fixture(**kw))

    def test_the_sagittal_rows_come_from_a_filtered_with_p95_and_max_flagged_provisional_naming_method_and_mode(self):
        text = self.text()
        row = next(l for l in self.rows(text, "| gait ") if "knee_right" in l and "| 1.4 |" in l)
        self.assertIn("A_filtered", row)
        self.assertIn("rigid", row)  # the trunk mode is named (A's leg rows do not depend on it)
        self.assertIn("provisional", row)
        cells = [c.strip() for c in row.strip("|").split("|")]
        self.assertIn("40.0", cells)  # 95th percentile
        self.assertIn("48.0", cells)  # maximum beside it
        self.assertIn("60.0", cells)  # A_native's maximum beside, the with-impact bound (1.2 x 50)
        self.assertNotIn("100.0", row)  # B misses the band and does not enter

    def test_a_method_enters_only_if_it_meets_the_band(self):
        text = self.text(h_meets=False)
        self.assertEqual([l for l in self.rows(text, "| gait ") if "| H " in l and "knee_right" in l], [])
        text = self.text(h_meets=True)
        h = [l for l in self.rows(text, "| gait ") if "knee_right" in l and "| H " in l]
        self.assertTrue(h and "70.0" in h[0] and "1.4" in h[0])

    def test_mutation_when_a_filtered_misses_the_band_its_rows_are_not_entered(self):
        text = self.text(a_filtered_meets=False)
        self.assertEqual([l for l in self.rows(text, "| gait ") if "knee_right" in l and "A_filtered" in l], [])
        self.assertIn("no method meets the band", text)

    def test_hip_ab_adduction_and_rotation_are_listed_outside_band_with_their_numbers(self):
        text = self.text()
        aa = next(l for l in self.rows(text, "| gait ") if "hip_aa_right" in l and "| 1.4 |" in l)
        self.assertIn("outside band", aa)
        self.assertIn("0.97", aa)
        self.assertIn("18", aa)
        ier = next(l for l in self.rows(text, "| gait ") if "hip_ier_left" in l and "| 1.6 |" in l)
        self.assertIn("outside band", ier)
        self.assertIn("0.86", ier)

    def test_ankle_inversion_is_a_load_from_a_b_and_h_flagged_unverified_and_not_comparable(self):
        text = self.text()
        row = next(l for l in self.rows(text, "| gait ") if "ankle_ie_right" in l and "| 1.4 |" in l)
        self.assertIn("unverified", row)
        self.assertIn("not comparable with the dataset", row)
        for v in ("40.0", "100.0", "70.0"):  # A_filtered, B and H p95
            self.assertIn(v, row)
        self.assertNotIn("-0.12", row)  # it is not in the agreement table

    def test_joints_above_the_pelvis_are_the_bracket_across_trunk_modes_and_arms_are_excluded(self):
        text = self.text()
        row = next(l for l in self.rows(text, "| gait ") if "lsj_lat" in l and "| 1.4 |" in l)
        self.assertIn("30.0 .. 60.0", row)  # the p95 torque of counter_rotate and rigid
        self.assertIn("72.0", row)  # the larger maximum
        self.assertIn("kinematics only", row)
        self.assertIn("arm", text.lower())
        self.assertIn("arm swing is not modelled", text)

    def test_every_joint_has_a_speed_and_the_functional_demand_findings_are_there(self):
        text = self.text()
        for j in LEG_JOINTS + list(EXTRA):
            self.assertTrue([l for l in self.rows(text, "| gait ") if f" {j} " in l and "| 1.4 |" in l], j)
        self.assertIn("lsj_lat", text)
        self.assertIn("7.4", text)  # peak lumbosacral lateral angle p95 in the rigid mode (counter_rotate: 3.7)
        self.assertIn("beyond", text)  # peak hip extension against the model's stop
        self.assertIn("85%", text)

    def test_the_lists_of_covered_and_uncovered_scenario_classes_are_updated(self):
        head = "\n".join(self.text().splitlines()[:14])
        self.assertIn("walk_treadmill", head)
        self.assertRegex(head, r"Not yet included: [^.]*stairs")
        self.assertIn("overground walking", head)
        self.assertNotRegex(head, r"Not yet included: gait")

    def test_a_gait_record_for_another_model_is_stale_and_contributes_nothing(self):
        text = rp.envelope([summary("run.20261002-0900-sweep", "sweep")], current_model_sha=sha("model1"), gait=gait_extract_fixture(model_sha=sha("other")))
        self.assertIn("stale", text.lower())
        self.assertEqual(self.rows(text, "| gait "), [])

    def test_no_gait_record_changes_nothing_about_the_run_envelope(self):
        recs = [summary("run.20261002-0900-sweep", "sweep")]
        self.assertEqual(rp.envelope(recs), rp.envelope(recs, gait=None))
        self.assertEqual(self.rows(rp.envelope(recs), "| gait "), [])

    def test_byte_identical_and_within_the_line_cap(self):
        a, b = self.text(), self.text()
        self.assertEqual(a, b)
        self.assertLessEqual(len(a.splitlines()), 399)


class Envelope(unittest.TestCase):
    def test_selects_the_driving_run_per_quantity_from_the_latest_run_of_each_scenario(self):
        recs = [
            summary("run.20261001-0900-sweep", "sweep", {"hip": joint(tpk=100.0)}),  # superseded: not the latest sweep
            summary("run.20261002-0900-sweep", "sweep", {"hip": joint(tpk=40.0, wpk=1.0, ppk=10.0)}),
            summary("run.20261002-1000-hold", "hold", {"hip": joint(tpk=55.0, wpk=0.5, ppk=99.0)}),
        ]
        text = rp.envelope(recs)
        row = next(line for line in text.splitlines() if line.startswith("| hip "))
        cells = [c.strip() for c in row.strip("|").split("|")]
        self.assertEqual(cells[1:3], ["55.00", "run.20261002-1000-hold"])  # torque: hold
        self.assertEqual(cells[3:5], ["1.000", "run.20261002-0900-sweep"])  # speed: sweep
        self.assertEqual(cells[5:7], ["99.00", "run.20261002-1000-hold"])  # power: hold
        self.assertNotIn("100.00", text)  # the older sweep never contributes

    def test_ties_are_broken_by_run_id(self):
        recs = [summary("run.20261002-1000-hold", "hold", {"hip": joint(tpk=50.0)}),
                summary("run.20261002-0900-sweep", "sweep", {"hip": joint(tpk=50.0)})]
        for ordered in (recs, list(reversed(recs))):
            row = next(l for l in rp.envelope(ordered).splitlines() if l.startswith("| hip "))
            self.assertIn("run.20261002-0900-sweep", row.split("|")[3])  # the smaller run id wins, whatever the input order

    def test_opens_with_what_is_and_is_not_included(self):
        recs = [summary("run.20261002-0900-sweep", "sweep", {"hip": joint()}), summary("run.20261002-1000-hold", "hold", {"hip": joint()})]
        head = "\n".join(rp.envelope(recs).splitlines()[:14])
        for word in ("sweep", "hold", "gait", "stairs", "sit-to-stand", "not a complete sizing basis"):
            self.assertIn(word, head)

    def test_lists_joints_with_no_rom_data_and_says_their_row_is_the_static_solve_only(self):
        sweep = summary("run.20261002-0900-sweep", "sweep", {"hip": joint()}, skipped={"lsj_fe": "unlimited", "cj_fe": "unlimited"})
        hold = summary("run.20261002-1000-hold", "hold", {"hip": joint(), "lsj_fe": joint(limit=None, tpk=30.0)})
        text = rp.envelope([sweep, hold])
        section = next(l for l in text.splitlines() if "no ROM data" in l)
        self.assertIn("cj_fe", section)
        self.assertIn("lsj_fe", section)
        self.assertIn("static standing solve only", text)
        lsj = next(l for l in text.splitlines() if l.startswith("| lsj_fe "))
        self.assertIn("30.00", lsj)
        cj = next(l for l in text.splitlines() if l.startswith("| cj_fe "))  # skipped and never measured: a row that says so
        self.assertIn("no data", cj)

    def test_a_verification_only_scenario_is_excluded_with_its_reason_and_never_drives(self):
        hold = summary("run.20261002-1000-hold", "hold", {"hip": joint(tpk=500.0)})
        hold["scenario"]["params"]["envelope"] = False
        static = summary("run.20261002-0900-static", "static", {"hip": joint(tpk=40.0), "lsj_fe": joint(limit=None, tpk=5.0)})
        text = rp.envelope([hold, static])
        self.assertNotIn("500.00", text)
        self.assertIn("verification only (envelope: false)", text)
        self.assertIn("run.20261002-1000-hold", text)
        lsj = next(l for l in text.splitlines() if l.startswith("| lsj_fe "))
        self.assertIn("5.00", lsj)  # an unlimited joint gets its row from the static run instead of 'no data'

    def test_runs_that_did_not_complete_are_listed_but_do_not_drive(self):
        recs = [summary("run.20261002-0900-sweep", "sweep", {"hip": joint(tpk=40.0)}),
                summary("run.20261002-1000-hold", "hold", {"hip": joint(tpk=500.0)}, outcome="fell")]
        text = rp.envelope(recs)
        self.assertNotIn("500.00", text)
        self.assertIn("run.20261002-1000-hold", text)
        self.assertIn("fell", text)

    def test_runs_for_another_model_are_stale_and_excluded(self):
        old = summary("run.20261002-0900-sweep", "sweep", {"hip": joint(tpk=40.0)}, model_sha256=sha("model0"))
        new = summary("run.20261002-1000-hold", "hold", {"hip": joint(tpk=20.0)})
        text = rp.envelope([old, new], current_model_sha=sha("model1"))
        self.assertNotIn("40.00", text)
        self.assertIn("stale", text.lower())

    def test_byte_identical_on_a_second_run(self):
        recs = [summary("run.20261002-0900-sweep", "sweep"), summary("run.20261002-1000-hold", "hold")]
        self.assertEqual(rp.envelope(recs), rp.envelope(copy.deepcopy(recs)))

    def test_empty_history(self):
        self.assertIn("no runs", rp.envelope([]).lower())


class Digest(unittest.TestCase):
    def two(self):
        return [summary("run.20261001-0900-hold", "hold", {"hip_fe_right": joint(tpk=10.0)}),
                summary("run.20261002-0900-hold", "hold", {"hip_fe_right": joint(tpk=12.0)},
                        git_commit="b" * 40, snapshot_sha256=sha("snap2"))]

    def test_byte_identical_on_a_second_run(self):
        self.assertEqual(rp.digest(self.two()), rp.digest(copy.deepcopy(self.two())))

    def test_shows_the_latest_run_with_a_per_joint_table_and_the_delta_against_the_previous(self):
        text = rp.digest(self.two())
        self.assertIn("run.20261002-0900-hold", text)
        row = next(l for l in text.splitlines() if l.startswith("| hip_fe_right "))
        self.assertIn("12.00", row)
        self.assertIn("+20.0%", row)  # peak torque 10 -> 12
        self.assertIn("run.20261001-0900-hold", text)  # named as the run it is compared with
        self.assertIn("snapshot", text.lower())  # and the inputs that differ are said

    def test_has_contact_balance_and_checks_status(self):
        text = rp.digest(self.two())
        for word in ("foot_right", "330", "support margin", "check.a.b"):
            self.assertIn(word, text)

    def test_shows_the_pose_lean_angle_com_offset_and_sag(self):
        rec = summary("run.20261002-0900-hold", "hold", diagnostics={
            "lean_angle_deg": 2.6077, "com_offset_commanded_m": 0.0, "com_offset_window_mean_m": -0.0109, "com_sag_m": -0.0109})
        rec["scenario"]["params"]["pose"] = {"com_x_rel_ankle_m": 0.0}
        line = next(l for l in rp.digest([rec]).splitlines() if l.startswith("Pose:"))
        for text in ("com_x_rel_ankle_m 0.0", "lean angle 2.608 deg", "window-mean CoM offset -10.9 mm", "sag -10.9 mm"):
            self.assertIn(text, line)

    def test_no_pose_line_without_a_pose(self):
        self.assertFalse(any(l.startswith("Pose:") for l in rp.digest(self.two()).splitlines()))

    def test_first_run_has_no_delta(self):
        text = rp.digest(self.two()[:1])
        row = next(l for l in text.splitlines() if l.startswith("| hip_fe_right "))
        self.assertTrue(row.rstrip().rstrip("|").rstrip().endswith("-"))

    def test_scenarios_are_sorted_and_each_appears_once(self):
        recs = [summary("run.20261002-1000-zeta", "zeta"), summary("run.20261002-0900-alpha", "alpha")]
        text = rp.digest(recs)
        self.assertLess(text.index("## alpha"), text.index("## zeta"))
        self.assertEqual(text.count("## alpha"), 1)

    def test_skipped_joints_and_outcome_are_shown(self):
        rec = summary("run.20261002-0900-sweep", "sweep", skipped={"lsj_fe": "unlimited"}, outcome="fell")
        text = rp.digest([rec])
        self.assertIn("lsj_fe", text)
        self.assertIn("unlimited", text)
        self.assertIn("fell", text)

    def test_thirty_runs_stay_under_the_line_cap(self):
        recs = []
        for i in range(30):
            recs.append(summary(f"run.202610{1 + i // 24:02d}-{i % 24:02d}00-hold", "hold",
                                {f"j{k:02d}": joint(tpk=1.0 + i + k) for k in range(31)},
                                git_commit=f"{i:040x}"))
        recs += [summary(f"run.20261020-{i:02d}00-sweep", "sweep", {f"j{k:02d}": joint(tpk=1.0 + i) for k in range(31)}) for i in range(30)]
        text = rp.digest(recs)
        self.assertLess(len(text.splitlines()), 400)
        self.assertEqual(rp.digest(recs[::-1]), text)  # the order the files were found in does not matter

    def test_cap_holds_even_with_many_scenarios(self):
        recs = [summary(f"run.20261002-0900-s{i:02d}", f"s{i:02d}", {f"j{k:02d}": joint() for k in range(31)}) for i in range(15)]
        self.assertLess(len(rp.digest(recs).splitlines()), 400)

    def test_no_timestamps_other_than_run_ids(self):
        import re
        text = rp.digest(self.two())
        stripped = re.sub(r"run\.\d{8}-\d{4}-[a-z0-9_]+", "", text)
        self.assertNotRegex(stripped, r"\d{4}-\d{2}-\d{2}")
        self.assertNotRegex(stripped, r"\d{2}:\d{2}")

    def test_empty_history(self):
        self.assertIn("no runs", rp.digest([]).lower())


class Compare(unittest.TestCase):
    def test_reports_exactly_the_inputs_that_differ(self):
        a = summary("run.20261001-0900-hold", "hold")
        b = summary("run.20261002-0900-hold", "hold", git_commit="b" * 40, seed=3,
                    env={"mujoco": "3.11.0", "python": "3.11.9", "numpy": "2.4.6"}, controller={"name": "c", "version": "2"})
        b["scenario"]["params"] = {"gain": 2.0}
        differing = rp.differing_inputs(a, b)
        self.assertEqual(sorted(differing), ["commit", "controller", "env.mujoco", "scenario parameters", "seed"])
        self.assertNotIn("snapshot", differing)
        self.assertNotIn("model", differing)

    def test_identical_inputs_report_none(self):
        a = summary("run.20261001-0900-hold", "hold")
        b = summary("run.20261002-0900-hold", "hold")
        self.assertEqual(rp.differing_inputs(a, b), {})

    def test_snapshot_and_model_hashes(self):
        a = summary("run.20261001-0900-hold", "hold")
        b = summary("run.20261002-0900-hold", "hold", snapshot_sha256=sha("s2"), model_sha256=sha("m2"))
        self.assertEqual(sorted(rp.differing_inputs(a, b)), ["model", "snapshot"])

    def test_dirty_tree_is_an_input_difference(self):
        a = summary("run.20261001-0900-hold", "hold")
        b = summary("run.20261002-0900-hold", "hold", git_dirty=True, diff_sha256=sha("d"))
        self.assertIn("working tree", rp.differing_inputs(a, b))

    def test_metric_deltas_absolute_and_percent_and_only_changes(self):
        a = summary("run.20261001-0900-hold", "hold", {"hip": joint(tpk=10.0, trms=5.0)})
        b = summary("run.20261002-0900-hold", "hold", {"hip": joint(tpk=12.5, trms=5.0)})
        text = rp.compare(a, b)
        line = next(l for l in text.splitlines() if "hip" in l and "torque_peak_nm" in l)
        self.assertIn("10.000", line)
        self.assertIn("12.500", line)
        self.assertIn("+2.500", line)
        self.assertIn("+25.0%", line)
        self.assertFalse(any("torque_rms_nm" in l for l in text.splitlines()))  # unchanged: not listed
        self.assertIn("unchanged", text)

    def test_percent_from_zero_is_not_a_division_error(self):
        a = summary("run.20261001-0900-hold", "hold", {"hip": joint(tpk=0.0)})
        b = summary("run.20261002-0900-hold", "hold", {"hip": joint(tpk=1.0)})
        self.assertIn("n/a", rp.compare(a, b))

    def test_joints_in_only_one_run_are_named(self):
        a = summary("run.20261001-0900-hold", "hold", {"hip": joint()})
        b = summary("run.20261002-0900-hold", "hold", {"hip": joint(), "knee": joint()})
        self.assertIn("only in run.20261002-0900-hold: knee", rp.compare(a, b))

    def test_without_a_repo_it_says_it_cannot_attribute(self):
        a = summary("run.20261001-0900-hold", "hold")
        b = summary("run.20261002-0900-hold", "hold", git_commit="b" * 40, snapshot_sha256=sha("s2"))
        with tempfile.TemporaryDirectory() as d:  # not a repository: the commits cannot be read
            text = rp.compare(a, b, repo=d)
        self.assertIn("cannot attribute", text)

    def test_dirty_runs_cannot_be_attributed_either(self):
        a = summary("run.20261001-0900-hold", "hold")
        b = summary("run.20261002-0900-hold", "hold", git_commit="b" * 40, snapshot_sha256=sha("s2"), git_dirty=True, diff_sha256=sha("d"))
        self.assertIn("cannot attribute", rp.compare(a, b, repo=REPO))

    def test_changed_snapshot_rows_come_from_git_show_when_both_commits_are_clean(self):
        with tempfile.TemporaryDirectory() as d:
            def git(*args):
                subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@e.x", "-c", "commit.gpgsign=false", *args], cwd=d, check=True, capture_output=True)

            def commit(csv_text):
                (Path(d) / "params").mkdir(exist_ok=True)
                (Path(d) / "params" / "snapshot.csv").write_text(csv_text, encoding="utf-8", newline="\n")
                git("add", "-A")
                git("commit", "-q", "-m", "x")
                return subprocess.run(["git", "rev-parse", "HEAD"], cwd=d, check=True, capture_output=True, text=True).stdout.strip()

            git("init", "-q")
            c1 = commit("placeholder,value,sheet_source\nhip_flexion,130,A1\nknee_flexion,140,A2\nold_key,1,A3\n")
            c2 = commit("placeholder,value,sheet_source\nhip_flexion,125,A1\nknee_flexion,140,A2\nnew_key,2,A4\n")
            a = summary("run.20261001-0900-hold", "hold", git_commit=c1)
            b = summary("run.20261002-0900-hold", "hold", git_commit=c2, snapshot_sha256=sha("s2"))
            text = rp.compare(a, b, repo=d)
        self.assertIn("hip_flexion: 130 -> 125", text)
        self.assertIn("new_key: (absent) -> 2", text)
        self.assertIn("old_key: 1 -> (absent)", text)
        self.assertNotIn("knee_flexion", text)
        self.assertNotIn("cannot attribute", text)


class Query(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.recs = [summary("run.20261001-0900-hold", "hold"), summary("run.20261002-0900-sweep", "sweep"),
                     summary("run.20261003-0900-hold", "hold", outcome="fell")]
        write_all(self.tmp.name, self.recs)

    def run_main(self, *argv):
        out = io.StringIO()
        with redirect_stdout(out):
            code = rp.main([*argv, "--runs-dir", self.tmp.name, "--extract", str(Path(self.tmp.name) / "no_extract.json")])
        return code, out.getvalue()

    def test_list_in_run_id_order_and_filtered_by_scenario(self):
        code, text = self.run_main("list")
        self.assertEqual(code, 0)
        ids = [l.split()[0] for l in text.splitlines()]
        self.assertEqual(ids, ["run.20261001-0900-hold", "run.20261002-0900-sweep", "run.20261003-0900-hold"])
        _, text = self.run_main("list", "--scenario", "hold")
        self.assertEqual([l.split()[0] for l in text.splitlines()], ["run.20261001-0900-hold", "run.20261003-0900-hold"])
        self.assertIn("fell", text)

    def test_show_accepts_the_id_with_or_without_the_prefix_and_the_directory_name(self):
        for ident in ("run.20261002-0900-sweep", "20261002-0900-sweep"):
            code, text = self.run_main("show", ident)
            self.assertEqual(code, 0)
            self.assertIn("hip_fe_right", text)
            self.assertIn("run.20261002-0900-sweep", text)

    def test_show_unknown_run_is_an_error(self):
        code, _ = self.run_main("show", "run.20990101-0000-nothing")
        self.assertNotEqual(code, 0)

    def test_compare_two_runs(self):
        code, text = self.run_main("compare", "run.20261001-0900-hold", "run.20261003-0900-hold")
        self.assertEqual(code, 0)
        self.assertIn("run.20261001-0900-hold", text)
        self.assertIn("outcome", text)  # completed -> fell is a difference worth saying

    def test_digest_and_envelope_write_their_files(self):
        for command, name in (("digest", "DIGEST.md"), ("envelope", "ENVELOPE.md")):
            code, _ = self.run_main(command)
            self.assertEqual(code, 0)
            path = Path(self.tmp.name) / name
            self.assertTrue(path.is_file())
            self.assertNotIn(b"\r", path.read_bytes())
            first = path.read_bytes()
            self.run_main(command)
            self.assertEqual(path.read_bytes(), first)  # byte-identical on a second run

    def test_the_band_constants_mirror_the_gait_module_and_the_extract_is_read(self):
        import gait
        self.assertEqual((rp.GAIT_BAND_CORR, rp.GAIT_BAND_RMS_PCT, rp.GAIT_SAGITTAL), (gait.BAND_CORR, gait.BAND_RMS_PCT, gait.BAND_STEMS))
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "gait_extract.json"
            self.assertIsNone(rp.load_gait_extract(path))  # no extract: the envelope has no gait rows
            path.write_text(json.dumps(gait_extract_fixture(model_sha=json.loads(rp.META_FILE.read_text(encoding="utf-8"))["model_sha256"])), encoding="utf-8")
            self.assertEqual(rp.load_gait_extract(path)["gait_id"], "gait.20261012-0900-walk_treadmill")
            with redirect_stdout(io.StringIO()):
                self.assertEqual(rp.main(["envelope", "--runs-dir", self.tmp.name, "--extract", str(path)]), 0)
            self.assertIn("## Gait: walk_treadmill", (Path(self.tmp.name) / "ENVELOPE.md").read_text(encoding="utf-8"))

    def test_nothing_is_written_when_there_are_no_runs(self):
        with tempfile.TemporaryDirectory() as empty:
            out = io.StringIO()
            with redirect_stdout(out):
                code = rp.main(["digest", "--runs-dir", empty])
            self.assertEqual(code, 0)
            self.assertIn("no runs", (Path(empty) / "DIGEST.md").read_text(encoding="utf-8").lower())



class AcceptanceSpeedEnvelope(unittest.TestCase):
    """Stage 2f T3: 0.5 m/s is v1's acceptance speed. Its rows are shown beside 1.4 and 1.6, labelled, and enter no sizing statistic; where A_filtered
    misses the band at hip and knee (as measured) those rows carry the existing per-row outside-band flag, as hip ab/adduction and rotation do."""

    def text(self, extract=None, **kw):
        return rp.envelope([summary("run.20261002-0900-sweep", "sweep")], gait=extract or gait_extract_fixture(acceptance=True, **kw))

    def rows(self, text, prefix="| gait "):
        return [l for l in text.splitlines() if l.startswith(prefix)]

    def test_the_extract_with_the_acceptance_speed_validates_against_the_schema_without_a_version_bump(self):
        import gait_extract as ge
        ge.validate(gait_extract_fixture(acceptance=True))  # gait-extract/1 takes any speed key
        self.assertEqual(gait_extract_fixture(acceptance=True)["schema"], "gait-extract/1")

    def test_the_acceptance_rows_are_labelled_and_a_filtered_hip_and_knee_are_outside_band_by_the_per_row_flag(self):
        t = self.text()
        for stem in ("hip_fe", "knee"):
            row = next(l for l in self.rows(t) if f"{stem}_right" in l and "| 0.5 " in l and "A_filtered" in l)
            self.assertIn("outside band", row)
            self.assertIn("acceptance speed, not for sizing", row)
        ankle = next(l for l in self.rows(t) if "ankle_pdflex_right" in l and "| 0.5 " in l and "A_filtered" in l)
        self.assertIn("within band", ankle)  # the ankle meets the band at 0.5: the flag is per row, not per speed
        self.assertIn("acceptance speed, not for sizing", ankle)
        knee = next(l for l in self.rows(t) if "knee_right" in l and "| 0.5 " in l and "A_filtered" in l)
        self.assertIn("0.89", knee)  # the row's own numbers
        self.assertIn("24.0", knee)  # the 95th percentile, 0.6 x 40 N m

    def test_every_table_labels_the_acceptance_speed_and_says_what_it_is(self):
        t = self.text()
        self.assertIn("acceptance speed", t.split("## Gait", 1)[1].split("###", 1)[0])
        for prefix_joint in ("lsj_lat", "ankle_ie_right", "hip_aa_right", "knee_right"):
            row = next(l for l in self.rows(t) if prefix_joint in l and "| 0.5 " in l)
            self.assertIn("acceptance", row, prefix_joint)
        self.assertTrue(any("0.5 m/s" in l and "acceptance" in l for l in t.splitlines() if l.startswith("- ")))  # the functional-demand findings

    def test_the_1p4_and_1p6_rows_are_unchanged_by_the_presence_of_0p5(self):
        with_05 = self.text()
        without = rp.envelope([summary("run.20261002-0900-sweep", "sweep")], gait=gait_extract_fixture())
        pick = lambda text: [l for l in text.splitlines() if "| 1.4 |" in l or "| 1.6 |" in l or l.startswith("- 1.4 m/s") or l.startswith("- 1.6 m/s")]
        self.assertEqual(pick(with_05), pick(without))
        self.assertGreater(len(pick(without)), 20)
        before, after = without.split("## Gait", 1)[0], with_05.split("## Gait", 1)[0]
        self.assertEqual(before, after)  # every worst-case row above the gait section is untouched

    def test_the_header_says_the_acceptance_speed_enters_no_sizing_statistic_and_names_the_sizing_speeds(self):
        intro = self.text().split("## Gait", 1)[1].split("###", 1)[0]
        self.assertIn("0.5, 1.4 and 1.6 m/s", intro)
        self.assertIn("acceptance speed", intro)
        self.assertIn("enter no sizing statistic", intro)
        self.assertIn("sizing speeds are 1.4 and 1.6", intro)
        self.assertNotIn("acceptance", rp.envelope([summary("run.20261002-0900-sweep", "sweep")], gait=gait_extract_fixture()))  # no acceptance speed, no such wording

    def test_mutation_changing_one_0p5_value_changes_the_envelope(self):
        ex = gait_extract_fixture(acceptance=True)
        base = self.text(extract=ex)
        ex["results"]["0.5"]["rigid"]["joints"]["knee_right"]["A_filtered"]["peak_torque_nm"]["all"]["p95"] = 41.5
        changed = self.text(extract=ex)
        self.assertNotEqual(base, changed)
        self.assertIn("41.5", next(l for l in self.rows(changed) if "knee_right" in l and "| 0.5 " in l and "A_filtered" in l))

    def test_a_sizing_speed_that_misses_the_band_still_has_its_rows_dropped(self):
        t = self.text(a_filtered_meets=False)  # 1.4 and 1.6 miss; 0.5 is listed per row, the sizing speeds are not
        self.assertEqual([l for l in self.rows(t) if "knee_right" in l and "A_filtered" in l and ("| 1.4 |" in l or "| 1.6 |" in l)], [])
        self.assertIn("no method meets the band at 1.4 m/s", t)
        self.assertTrue([l for l in self.rows(t) if "knee_right" in l and "A_filtered" in l and "| 0.5 " in l])

if __name__ == "__main__":
    unittest.main()
