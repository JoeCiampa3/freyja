"""
T4: the post_checks hook in build_model(). A failing gate check parks the new XML as the FAILED
file and leaves the last good model, snapshot and metadata in place; an advisory failure installs
the new model and is reported. No internet, no sheet.

Run from the repo root:
    python -m pytest tests
"""
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "sim" / "scripts"))
sys.path.insert(0, str(REPO / "checks"))

import json
import tempfile
import unittest

import checklib as cl
import mjcf_checks  # noqa: F401  (registers the real checks)
import pre_processor as pp
import watch
from test_watch import FakeSource, TEMPLATE, good_tables


def hook_returning(*results, warnings=(), calls=None):
    """A post_checks hook that returns a fixed report and records how it was called."""
    def hook(xml_path, snapshot_text):
        if calls is not None:
            calls.append((Path(xml_path), Path(xml_path).exists(), snapshot_text))
        return cl.RunReport(list(results), list(warnings))
    return hook


GATE_FAIL = cl.Result("check.mjcf.mirror", "gate", cl.FAIL, "left thigh mass differs")
ADV_FAIL = cl.Result("check.mjcf.com_pct_stature", "advisory", cl.FAIL, "55.26% of stature")
OK = cl.Result("check.mjcf.mass_closure", "gate", cl.PASS, "closes")


class GateTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self._tmp.name)
        self.template = self.dir / "t.xml"
        self.template.write_text(TEMPLATE, encoding="utf-8")
        self.out = self.dir / "models" / "model.xml"
        self.out.parent.mkdir()
        self.failed = self.dir / "failed.xml"
        self.params = self.dir / "params"

    def tearDown(self):
        self._tmp.cleanup()

    def build(self, tables=None, post_checks=None, **kw):
        return pp.build_model(tables or good_tables(), template=self.template, output=self.out,
                              failed_output=self.failed, snapshot_dir=self.params, archive=False,
                              post_checks=post_checks, **kw)

    def state(self):
        return {p.name: p.read_bytes() for p in (self.out, self.params / "snapshot.csv", self.params / "snapshot.meta.json")}

    def test_no_hook_changes_nothing(self):
        r = self.build()
        self.assertEqual(r.status, "created")
        self.assertIsNone(r.checks)

    def test_gate_failure_keeps_the_previous_model_and_snapshot(self):
        self.build(post_checks=hook_returning(OK))
        before = self.state()
        with self.assertRaises(pp.BuildError) as cm:
            self.build(good_tables(pelvis=dict(mass=3.5)), post_checks=hook_returning(GATE_FAIL, ADV_FAIL))
        self.assertEqual(self.state(), before)  # model, snapshot and metadata untouched
        self.assertIn("check.mjcf.mirror", cm.exception.format())  # the failing ID is printed
        self.assertIn("left thigh mass differs", cm.exception.format())
        self.assertNotIn("check.mjcf.com_pct_stature", cm.exception.format())  # advisory failures do not block
        self.assertFalse(cm.exception.transient)

    def test_gate_failure_parks_the_new_xml_as_failed(self):
        self.build(post_checks=hook_returning(OK))
        with self.assertRaises(pp.BuildError):
            self.build(good_tables(pelvis=dict(mass=3.5)), post_checks=hook_returning(GATE_FAIL))
        self.assertIn(b'mass="3.5"', self.failed.read_bytes())  # the new build, not the old one
        self.assertNotIn(b'mass="3.5"', self.out.read_bytes())

    def test_first_build_with_a_gate_failure_installs_nothing(self):
        with self.assertRaises(pp.BuildError):
            self.build(post_checks=hook_returning(GATE_FAIL))
        self.assertFalse(self.out.exists())
        self.assertFalse(self.params.exists())
        self.assertTrue(self.failed.exists())

    def test_advisory_failure_installs_the_new_model_and_is_reported(self):
        self.build(post_checks=hook_returning(OK))
        r = self.build(good_tables(pelvis=dict(mass=3.5)),
                       post_checks=hook_returning(OK, ADV_FAIL, warnings=["waiver proposed for x is not confirmed"]))
        self.assertEqual(r.status, "updated")
        self.assertIn(b'mass="3.5"', self.out.read_bytes())
        self.assertEqual([x.id for x in r.checks.results], [OK.id, ADV_FAIL.id])
        self.assertEqual(r.checks.warnings, ["waiver proposed for x is not confirmed"])

    def test_a_waived_gate_failure_does_not_block(self):
        waived = cl.Result(GATE_FAIL.id, "gate", cl.WAIVED, "known deviation")
        self.assertEqual(self.build(post_checks=hook_returning(waived)).status, "created")

    def test_hook_sees_the_temporary_xml_before_it_is_installed(self):
        calls = []
        self.build(post_checks=hook_returning(OK, calls=calls))
        (path, existed, snapshot_text), = calls
        self.assertTrue(existed)  # the file the hook was given existed ...
        self.assertNotEqual(path, self.out)  # ... and was not the installed model
        self.assertFalse(path.exists())  # and is gone afterwards
        self.assertEqual(snapshot_text.encode("utf-8"), (self.params / "snapshot.csv").read_bytes())
        self.assertEqual(path.parent, self.out.parent)  # next to the model, so the compile and the checks saw the same bytes

    def test_hook_runs_on_a_dry_run_but_nothing_is_written(self):
        calls = []
        r = self.build(dry_run=True, post_checks=hook_returning(OK, calls=calls))
        self.assertEqual(r.status, "checked")
        self.assertEqual(len(calls), 1)
        self.assertEqual(sorted(p.name for p in self.dir.iterdir()), ["models", "t.xml"])
        self.assertEqual(list(self.out.parent.iterdir()), [])
        with self.assertRaises(pp.BuildError):
            self.build(dry_run=True, post_checks=hook_returning(GATE_FAIL))
        self.assertFalse(self.failed.exists())

    def test_hook_is_not_called_when_the_build_already_failed(self):
        calls = []
        with self.assertRaises(pp.BuildError):
            self.build(good_tables(pelvis=dict(mass=-5)), post_checks=hook_returning(OK, calls=calls))
        self.assertEqual(calls, [])

    def test_unchanged_model_still_runs_the_checks(self):
        self.build(post_checks=hook_returning(OK))
        calls = []
        self.assertEqual(self.build(post_checks=hook_returning(OK, calls=calls)).status, "unchanged")
        self.assertEqual(len(calls), 1)

    def test_no_temp_files_left_behind_after_a_gate_failure(self):
        with self.assertRaises(pp.BuildError):
            self.build(post_checks=hook_returning(GATE_FAIL))
        self.assertEqual(list(self.out.parent.iterdir()), [])


class WatcherGateTests(unittest.TestCase):
    """The watcher survives a gate failure and rebuilds when the input is fixed."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self._tmp.name)
        self.template = self.dir / "t.xml"
        self.template.write_text(TEMPLATE, encoding="utf-8")
        self.out = self.dir / "model.xml"
        self.params = self.dir / "params"
        self.lines = []

    def tearDown(self):
        self._tmp.cleanup()

    def test_gate_failure_is_reported_once_and_the_fix_rebuilds(self):
        def hook(xml_path, snapshot_text):  # fails the gate while the pelvis mass is 3
            bad = "pelvis_mass,3," in snapshot_text
            return cl.RunReport([cl.Result("check.mjcf.mirror", "gate", cl.FAIL if bad else cl.PASS, "pelvis mass is 3")])

        def build(tables):
            return pp.build_model(tables, template=self.template, output=self.out, failed_output=self.dir / "f.xml",
                                  snapshot_dir=self.params, archive=False, post_checks=hook)

        good, bad, fixed = good_tables(), good_tables(pelvis=dict(mass=3.0)), good_tables(pelvis=dict(mass=4.0))
        now = [0.0]
        w = watch.Watcher(FakeSource([good, bad, bad, bad, bad, fixed, fixed]), build, self.template, interval=20, debounce=5,
                          sleep=lambda s: now.__setitem__(0, now[0] + s), clock=lambda: now[0], out=self.lines.append)
        w.step()  # startup build
        good_model = self.out.read_bytes()
        for _ in range(3):
            w.step()  # the bad edit appears, settles, then idle polls
        text = "\n".join(self.lines)
        self.assertEqual(text.count("REBUILD FAILED"), 1)
        self.assertIn("check.mjcf.mirror", text)
        self.assertIn("freyja.xml was NOT changed", text)
        self.assertEqual(self.out.read_bytes(), good_model)
        w.step()  # the fix arrives
        self.assertIn(b'mass="4"', self.out.read_bytes())
        self.assertIn("OK: model updated", "\n".join(self.lines))

    def test_advisory_results_are_logged_once_and_again_only_when_they_change(self):
        report = cl.RunReport([cl.Result("check.mjcf.com_pct_stature", "advisory", cl.FAIL, "55.26% of stature")],
                              ["waiver proposed for check.mjcf.com_pct_stature is not confirmed"])
        w = watch.Watcher(FakeSource([good_tables()]), lambda t: pp.BuildResult("updated", 1, [], None, None, [], report),
                          self.template, interval=20, debounce=5, sleep=lambda s: None, clock=lambda: 0.0, out=self.lines.append)
        w._rebuild(good_tables())
        w._rebuild(good_tables())
        text = "\n".join(self.lines)
        self.assertEqual(text.count("check.mjcf.com_pct_stature"), 2)  # the failure line and the warning, once each
        self.assertIn("55.26% of stature", text)


class DefaultHookTests(unittest.TestCase):
    """cl.make_post_checks(): the hook pre_processor and the watcher use, on the real checks."""

    def model_and_snapshot(self):
        return (cl.MODEL_FILE, cl.SNAPSHOT_FILE.read_text(encoding="utf-8"))

    def test_committed_model_passes_the_gates_and_writes_last_run(self):
        xml, snap = self.model_and_snapshot()
        with tempfile.TemporaryDirectory() as d:
            last = Path(d) / "last_run.json"
            report = cl.make_post_checks(last_run=last)(xml, snap)
            self.assertEqual(report.blocking, [])
            data = json.loads(last.read_text(encoding="utf-8"))
            self.assertIn("check.mjcf.mirror", [r["id"] for r in data["results"]])
            self.assertTrue(any("check.mjcf.com_pct_stature" in w for w in data["warnings"]))  # the proposed waiver reminder

    def test_a_broken_copy_of_the_model_is_blocked_and_recorded(self):
        xml, snap = self.model_and_snapshot()
        with tempfile.TemporaryDirectory() as d:
            bad = Path(d) / "bad.xml"
            bad.write_text(xml.read_text(encoding="utf-8").replace('name="knee_right" type="hinge" axis="0 1 0"',
                                                                   'name="knee_right" type="hinge" axis="0 -1 0"'), encoding="utf-8")
            last = Path(d) / "last_run.json"
            report = cl.make_post_checks(last_run=last)(bad, snap)
            self.assertEqual({r.id for r in report.blocking}, {"check.mjcf.joint_signs", "check.mjcf.mirror"})
            self.assertIn("knee_right", last.read_text(encoding="utf-8"))

    def test_real_build_is_blocked_by_a_real_gate(self):
        """End to end: the real template with one hinge axis flipped is refused by build_model."""
        template = (REPO / "sim" / "models" / "freyja_template.xml").read_text(encoding="utf-8")
        flipped = template.replace('name="knee_right" type="hinge" axis="0 1 0"', 'name="knee_right" type="hinge" axis="0 -1 0"')
        self.assertNotEqual(template, flipped)
        tables = rebuild_tables_from_snapshot()
        with tempfile.TemporaryDirectory() as d:
            d = Path(d)
            (d / "t.xml").write_text(flipped, encoding="utf-8")
            with self.assertRaises(pp.BuildError) as cm:
                pp.build_model(tables, template=d / "t.xml", output=d / "m.xml", failed_output=d / "f.xml",
                               snapshot_dir=d / "params", archive=False,
                               post_checks=cl.make_post_checks(last_run=d / "last.json"))
            self.assertIn("check.mjcf.joint_signs", cm.exception.format())
            self.assertFalse((d / "m.xml").exists())


def rebuild_tables_from_snapshot():
    """Raw sheet tables that reproduce the committed snapshot, built from the tracked csv (offline)."""
    import csv
    snap = {r["placeholder"]: float(r["value"]) for r in csv.DictReader((REPO / "params" / "snapshot.csv").open(encoding="utf-8"))}
    names = {"head_neck": "Head & Neck", "thorax": "Thorax", "abdomen": "Abdomen", "pelvis": "Pelvis", "upper_arm": "Upper Arm",
             "forearm": "Forearm", "hand": "Hand", "thigh": "Thigh", "shank": "Shank", "foot": "Foot"}

    def key(seg):
        return f"{seg}_right" if seg in pp.BILATERAL else seg
    bsip = [["Segment"] + [c for c in pp.BSIP_COLUMNS]] + [[names[s]] + [snap[f"{key(s)}_{c}"] for c in pp.BSIP_COLUMNS] for s in pp.EXPECTED_SEGMENTS]
    pos = [["Segment"] + pp.POS_COLUMNS] + [[names[s]] + [snap[f"{key(s)}_{c}"] for c in pp.POS_COLUMNS] for s in pp.EXPECTED_SEGMENTS]
    joints = {"hip", "knee", "ankle", "shoulder", "elbow", "wrist", "lumbosacral"}
    rom = [["Joint", "Movement", "MuJoCo limit - FINAL (deg)"]] + [
        [k.split("_")[0], k.split("_", 1)[1], v] for k, v in sorted(snap.items()) if k.split("_")[0] in joints]
    return {"bsip": pp.RawTable("bsip", "S", 1, 1, bsip), "pos": pp.RawTable("pos", "S", 1, 1, pos),
            "rom": pp.RawTable("rom", "S", 1, 1, rom)}


if __name__ == "__main__":
    unittest.main()
