"""
Tests for build_model() safety and for watch.py. No internet and no waiting:
the watcher is driven with a fake clock and a scripted fake sheet.

Run from the freyja-sim folder:
    freyja.venv\\Scripts\\python -m unittest discover -s scripts -v
"""
import copy
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import pre_processor as pp
import watch
from test_pre_processor import full_bsip_table, rom_table

# ---------------------------------------------------------------- fake sheet

POS_HEADER = ["Segment", "pos_x (m)", "pos_y (m)", "pos_z (m)", "jpos_z (m)"]
POS = {"Pelvis": (0, 0, 0.96, 0), "Abdomen": (0, 0, 0.12, -0.12), "Thorax": (0, 0, 0.33, -0.33),
       "Head & Neck": (0, 0, 0, 0), "Upper Arm": (0.01, -0.19, -0.07, 0), "Forearm": (0, 0, -0.24, 0),
       "Hand": (0, 0, -0.25, 0), "Thigh": (0.05, -0.09, -0.09, 0), "Shank": (0, 0, -0.4, 0),
       "Foot": (0, 0, -0.41, 0)}


def good_tables(**bsip_overrides):
    pos = pp.RawTable("pos", "Pos", 4, 1, [POS_HEADER] + [[n, *v] for n, v in POS.items()])
    rom = rom_table([["Hip", "Flexion", "", 120.0, "", "", 120.0], ["Hip", "Extension", "", 18.0, "", "", 18.0]])
    return {"bsip": full_bsip_table(**bsip_overrides), "pos": pos, "rom": rom}


TEMPLATE = """<mujoco model="t">
  <worldbody>
    <body name="pelvis" pos="!{pelvis_pos_x} !{pelvis_pos_y} !{pelvis_pos_z}">
      <inertial pos="${pelvis_com_x} ${pelvis_com_y} ${pelvis_com_z}" mass="${pelvis_mass}" fullinertia="${pelvis_ixx} ${pelvis_iyy} ${pelvis_izz} ${pelvis_ixy} ${pelvis_ixz} ${pelvis_iyz}"/>
      <geom type="sphere" size="0.1" mass="0"/>
      <joint type="free"/>
      <body name="thigh" pos="!{thigh_right_pos_x} !{thigh_right_pos_y} !{thigh_right_pos_z}">
        <inertial pos="${thigh_right_com_x} ${thigh_right_com_y} ${thigh_right_com_z}" mass="${thigh_right_mass}" fullinertia="${thigh_right_ixx} ${thigh_right_iyy} ${thigh_right_izz} ${thigh_right_ixy} ${thigh_right_ixz} ${thigh_right_iyz}"/>
        <geom type="sphere" size="0.05" mass="0"/>
        <joint name="hip" type="hinge" axis="0 -1 0" limited="true" range="!{-hip_extension} !{hip_flexion}"/>
      </body>
    </body>
  </worldbody>
</mujoco>
"""

try:
    import mujoco  # noqa: F401
    HAVE_MUJOCO = True
except ImportError:
    HAVE_MUJOCO = False


class BuildModelTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self._tmp.name)
        self.template = self.dir / "t.xml"
        self.template.write_text(TEMPLATE, encoding="utf-8")
        self.out = self.dir / "model.xml"
        self.failed = self.dir / "failed.xml"

    def tearDown(self):
        self._tmp.cleanup()

    def build(self, tables=None, **kw):
        return pp.build_model(tables or good_tables(), template=self.template, output=self.out,
                              failed_output=self.failed, archive=False, **kw)

    def files(self):
        return sorted(p.name for p in self.dir.iterdir())

    def test_create_then_unchanged_then_update(self):
        r = self.build()
        self.assertEqual(r.status, "created")
        self.assertEqual(r.placeholders, len(pp.find_placeholders(TEMPLATE)))
        first = self.out.read_bytes()
        mtime = self.out.stat().st_mtime_ns

        r = self.build()
        self.assertEqual(r.status, "unchanged")
        self.assertEqual(self.out.read_bytes(), first)
        self.assertEqual(self.out.stat().st_mtime_ns, mtime)  # not even touched

        r = self.build(good_tables(pelvis=dict(mass=3.5)))
        self.assertEqual(r.status, "updated")
        self.assertIn(b'mass="3.5"', self.out.read_bytes())

    def test_no_temp_files_left_behind(self):
        self.build()
        self.assertEqual(self.files(), ["model.xml", "t.xml"])

    def test_bad_data_leaves_good_model_untouched(self):
        self.build()
        good = self.out.read_bytes()
        with self.assertRaises(pp.BuildError) as cm:
            self.build(good_tables(pelvis=dict(mass=-5)))
        self.assertIn("mass must be > 0", cm.exception.errors[0])
        self.assertFalse(cm.exception.transient)
        self.assertEqual(self.out.read_bytes(), good)
        self.assertEqual(self.files(), ["model.xml", "t.xml"])

    def test_bad_template_leaves_good_model_untouched(self):
        self.build()
        good = self.out.read_bytes()
        self.template.write_text(TEMPLATE.replace("hip_flexion", "hip_flexon"), encoding="utf-8")
        with self.assertRaises(pp.BuildError):  # a misspelt name is an error when strict
            self.build(strict=True)
        self.assertEqual(self.out.read_bytes(), good)

    def test_missing_rom_leaves_joint_unlimited_unless_strict(self):
        tables = good_tables()
        tables["rom"] = rom_table([["Hip", "Extension", "", 18.0, "", "", 18.0]])  # no flexion row
        r = self.build(tables)
        self.assertTrue(any("hip_flexion" in w for w in r.warnings))
        self.assertNotIn(b"range=", self.out.read_bytes())
        with self.assertRaises(pp.BuildError):
            self.build(tables, strict=True)

    @unittest.skipUnless(HAVE_MUJOCO, "mujoco not installed")
    def test_mujoco_rejecting_the_model_keeps_old_file_and_parks_the_broken_one(self):
        self.build()
        good = self.out.read_bytes()
        # passes our own checks, but MuJoCo refuses a negative sphere size
        self.template.write_text(TEMPLATE.replace('size="0.05"', 'size="-0.05"'), encoding="utf-8")
        with self.assertRaises(pp.BuildError) as cm:
            self.build()
        self.assertIn("MuJoCo could not compile", cm.exception.errors[0])
        self.assertEqual(self.out.read_bytes(), good)
        self.assertTrue(self.failed.exists())
        self.assertEqual(self.files(), ["failed.xml", "model.xml", "t.xml"])

    def test_locked_output_is_a_retryable_error_and_changes_nothing(self):
        self.build()
        good = self.out.read_bytes()
        with mock.patch.object(pp.os, "replace", side_effect=PermissionError), \
                mock.patch.object(pp.time, "sleep"):
            with self.assertRaises(pp.BuildError) as cm:
                self.build(good_tables(pelvis=dict(mass=3.5)))
        self.assertTrue(cm.exception.transient)
        self.assertEqual(self.out.read_bytes(), good)
        self.assertEqual(self.files(), ["model.xml", "t.xml"])

    def test_dry_run_writes_nothing(self):
        r = self.build(dry_run=True)
        self.assertEqual(r.status, "checked")
        self.assertEqual(self.files(), ["t.xml"])

    def test_missing_template(self):
        self.template.unlink()
        with self.assertRaises(pp.BuildError):
            self.build()


# ---------------------------------------------------------------- the watcher


class FakeSource:
    """fetch() returns/raises the next scripted item, repeating the last one."""

    def __init__(self, script):
        self.script, self.calls = list(script), 0

    def fetch(self):
        item = self.script[min(self.calls, len(self.script) - 1)]
        self.calls += 1
        if isinstance(item, Exception):
            raise item
        return item


class WatcherTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.template = Path(self._tmp.name) / "t.xml"
        self.template.write_text("v1", encoding="utf-8")
        self.now, self.sleeps, self.lines, self.built = 0.0, [], [], []
        self.A, self.B, self.C = good_tables(), good_tables(pelvis=dict(mass=3.0)), good_tables(pelvis=dict(mass=4.0))

    def tearDown(self):
        self._tmp.cleanup()

    def sleep(self, s):
        self.sleeps.append(s)
        self.now += s

    def make(self, script, build=None, **kw):
        def default_build(tables):
            self.built.append(tables)
            return pp.BuildResult("updated", 42, [], "16 bodies, 32 joints, total mass 1 kg", 0.06, [])
        return watch.Watcher(FakeSource(script), build or default_build, self.template, interval=20, debounce=5,
                             sleep=self.sleep, clock=lambda: self.now, out=self.lines.append, **kw)

    def text(self):
        return "\n".join(self.lines)

    def test_builds_on_startup_then_is_silent_when_idle(self):
        w = self.make([self.A])
        for _ in range(5):
            self.assertEqual(w.step(), 20)
        self.assertEqual(len(self.built), 1)
        self.assertEqual(len(self.lines), 3)  # first build / rebuilding / OK ... and nothing for idle polls
        self.assertIn("42 placeholders substituted", self.text())

    def test_multi_cell_edit_triggers_one_rebuild_after_quiet(self):
        # startup A; then B appears; still changing to C; then C is stable
        w = self.make([self.A, self.B, self.C, self.C, self.C])
        w.step()
        w.step()  # sees B, waits, sees C (not stable), waits, sees C again (stable)
        self.assertEqual(len(self.built), 2)
        self.assertEqual(watch.sheet_fingerprint(self.built[1]), watch.sheet_fingerprint(self.C))  # built the settled data
        self.assertEqual(self.sleeps, [5, 5])
        self.assertEqual(self.text().count("change detected"), 1)

    def test_edit_that_never_settles_is_built_after_the_cap(self):
        flapping = [self.A] + [good_tables(pelvis=dict(mass=5.0 + i)) for i in range(30)]  # every read differs
        w = self.make(flapping)
        w.step()
        w.step()
        self.assertEqual(len(self.built), 2)
        self.assertIn("still being edited", self.text())

    def test_bad_edit_does_not_kill_or_retry_and_fix_rebuilds(self):
        def build(tables):
            if tables is self.B:
                raise pp.BuildError("reading the sheet", ["[bsip] mass must be > 0"], [])
            self.built.append(tables)
            return pp.BuildResult("updated", 7, [], None, None, [])
        # reads: startup A | B, B (change + settle) | B | B | C, C (the fix + settle)
        w = self.make([self.A, self.B, self.B, self.B, self.B, self.C, self.C], build=build)
        for _ in range(4):
            w.step()
        out = self.text()
        self.assertEqual(out.count("REBUILD FAILED"), 1)  # reported once, not on every poll
        self.assertIn("mass must be > 0", out)
        self.assertIn("freyja.xml was NOT changed", out)
        self.assertEqual(len(self.built), 1)
        w.step()  # the fix arrives
        self.assertEqual(len(self.built), 2)

    def test_network_errors_back_off_say_it_once_and_recover(self):
        down = pp.SheetAccessError("Could not reach Google Sheets (ConnectionError)")
        w = self.make([self.A, down, down, down, down, self.A, self.B, self.B])
        self.assertEqual(w.step(), 20)  # startup build
        delays = [w.step() for _ in range(4)]
        self.assertEqual(delays, [20, 40, 80, 160])
        self.assertEqual(self.text().count("cannot read the sheet"), 1)
        w.step()  # back, same data as before: just announces recovery, no rebuild
        self.assertIn("reachable again", self.text())
        self.assertEqual(len(self.built), 1)
        w.step()  # then a real change still gets built
        self.assertEqual(len(self.built), 2)

    def test_backoff_is_capped(self):
        down = pp.SheetAccessError("down")
        w = self.make([down])
        delays = [w.step() for _ in range(12)]
        self.assertEqual(max(delays), watch.MAX_BACKOFF_S)

    def test_unexpected_error_does_not_end_the_watcher(self):
        w = self.make([RuntimeError("boom"), self.A])
        self.assertEqual(w.step(), 20)
        self.assertIn("unexpected error", self.text())
        w.step()
        self.assertEqual(len(self.built), 1)

    def test_build_bug_is_reported_and_watching_continues(self):
        def build(tables):
            raise ValueError("oops")
        w = self.make([self.A], build=build)
        self.assertEqual(w.step(), 20)
        self.assertIn("REBUILD FAILED unexpectedly", self.text())
        w.step()  # same data is not retried forever
        self.assertEqual(self.text().count("REBUILD FAILED"), 1)

    def test_template_edit_triggers_rebuild(self):
        w = self.make([self.A])
        w.step()
        self.template.write_text("v2", encoding="utf-8")
        w.step()
        self.assertEqual(len(self.built), 2)
        self.assertIn("(template)", self.text())

    def test_locked_file_is_announced_once_and_retried_every_poll(self):
        attempts = []

        def build(tables):
            attempts.append(1)
            if len(attempts) < 4:
                raise pp.BuildError("installing model.xml", ["model.xml is in use by another program."], [], transient=True)
            return pp.BuildResult("updated", 5, [], None, None, [])
        w = self.make([self.A], build=build)
        for _ in range(4):
            w.step()
        self.assertEqual(len(attempts), 4)
        self.assertEqual(self.text().count("REBUILD BLOCKED"), 1)
        self.assertEqual(self.text().count("rebuilding"), 1)
        self.assertIn("OK: model updated", self.text())
        w.step()  # done: idle again
        self.assertEqual(len(attempts), 4)

    def test_identical_result_is_reported_as_nothing_written(self):
        def build(tables):
            return pp.BuildResult("unchanged", 9, [], None, None, [])
        w = self.make([self.A], build=build)
        w.step()
        self.assertIn("identical to the current model; nothing written", self.text())

    def test_warnings_are_listed_once_then_only_when_they_change(self):
        state = {"w": ["ROM missing for joint x"]}

        def build(tables):
            return pp.BuildResult("updated", 1, list(state["w"]), None, None, [])
        w = self.make([self.A, self.B, self.B, self.C, self.C], build=build)
        w.step()
        w.step()  # warnings unchanged
        self.assertEqual(self.text().count("WARNING ROM missing"), 1)
        state["w"] = ["ROM missing for joint x", "something new"]
        w.step()
        self.assertIn("something new", self.text())

    def test_fingerprint_ignores_nothing_it_should_notice_and_is_stable(self):
        self.assertEqual(watch.sheet_fingerprint(self.A), watch.sheet_fingerprint(copy.deepcopy(self.A)))
        self.assertNotEqual(watch.sheet_fingerprint(self.A), watch.sheet_fingerprint(self.B))


class ConfigTests(unittest.TestCase):
    def test_environment_beats_config_file(self):
        with mock.patch.dict(os.environ, {"FREYJA_SHEET_KEY": "from-env"}):
            self.assertEqual(pp.setting("FREYJA_SHEET_KEY", "sheet_key"), "from-env")

    def test_missing_config_gives_none_not_a_crash(self):
        with mock.patch.dict(os.environ, {}, clear=False), \
                mock.patch.object(pp, "CONFIG_FILE", Path("definitely/not/here.json")):
            os.environ.pop("FREYJA_X", None)
            self.assertIsNone(pp.setting("FREYJA_X", "x"))

    def test_unconfigured_google_source_is_a_clear_fatal_error(self):
        with mock.patch.object(pp, "setting", return_value=None):
            with self.assertRaises(pp.SheetAccessError) as cm:
                pp.GoogleSheetSource()
        self.assertTrue(cm.exception.fatal)
        self.assertIn("local_config.example.json", str(cm.exception))


if __name__ == "__main__":
    unittest.main()
