"""
Tests for the parameter snapshot (CONVENTIONS section 5): build_model() writes
params/snapshot.csv and snapshot.meta.json next to the model, and the banner of
the model carries the snapshot hash. No internet, no sheet.

Run from the repo root:
    python -m unittest discover -s tests -v
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "sim" / "scripts"))

import hashlib
import json
import os
import tempfile
import unittest
from unittest import mock

import pre_processor as pp
from test_watch import TEMPLATE, good_tables


def targets_table(mass=65, stature=1700):
    return pp.RawTable("targets", "BSIP Reference", 1, 1,
                       [["Total body mass (kg)", mass], ["Stature (mm)", stature]])


class SnapshotTests(unittest.TestCase):
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

    def build(self, tables=None, **kw):
        return pp.build_model(tables or good_tables(), template=self.template, output=self.out,
                              failed_output=self.failed, snapshot_dir=self.params, archive=False, **kw)

    def read(self):
        return {n: (self.params / n).read_bytes() for n in ("snapshot.csv", "snapshot.meta.json")} | \
               {"model.xml": self.out.read_bytes()}

    def test_build_writes_snapshot_meta_and_model(self):
        self.build()
        self.assertEqual(sorted(p.name for p in self.params.iterdir()), ["snapshot.csv", "snapshot.meta.json"])
        rows = self.read()["snapshot.csv"].decode().splitlines()
        self.assertEqual(rows[0], "placeholder,value,sheet_source")
        keys = [r.split(",")[0] for r in rows[1:]]
        self.assertEqual(keys, sorted(keys))
        self.assertIn("pelvis_mass", keys)

    def test_two_builds_are_byte_identical(self):
        self.build()
        first = self.read()
        mtimes = {p: p.stat().st_mtime_ns for p in (self.params / "snapshot.csv", self.out)}
        r = self.build()
        self.assertEqual(r.status, "unchanged")
        self.assertEqual(self.read(), first)
        self.assertEqual({p: p.stat().st_mtime_ns for p in mtimes}, mtimes)  # not even touched

    def test_snapshot_is_lf_and_has_no_timestamp(self):
        self.build()
        for data in self.read().values():
            self.assertNotIn(b"\r", data)

    def test_changing_one_value_changes_exactly_one_row(self):
        self.build()
        before = self.read()["snapshot.csv"].decode().splitlines()
        self.build(good_tables(pelvis=dict(mass=3.5)))
        after = self.read()["snapshot.csv"].decode().splitlines()
        self.assertEqual(len(before), len(after))
        self.assertEqual([a for a, b in zip(after, before) if a != b], [after[[a.split(",")[0] for a in after].index("pelvis_mass")]])

    def test_dry_run_writes_nothing(self):
        self.build()
        first = self.read()
        r = self.build(good_tables(pelvis=dict(mass=3.5)), dry_run=True)
        self.assertEqual(r.status, "checked")
        self.assertEqual(self.read(), first)
        fresh = self.dir / "fresh"
        pp.build_model(good_tables(), template=self.template, output=self.dir / "x.xml", failed_output=self.failed,
                       snapshot_dir=fresh, archive=False, dry_run=True)
        self.assertFalse(fresh.exists())

    def test_failed_build_leaves_everything_untouched(self):
        self.build()
        first = self.read()
        with self.assertRaises(pp.BuildError):
            self.build(good_tables(pelvis=dict(mass=-5)))
        self.assertEqual(self.read(), first)
        self.assertEqual(sorted(p.name for p in self.params.iterdir()), ["snapshot.csv", "snapshot.meta.json"])

    def test_install_failure_rolls_back_every_file(self):
        self.build()
        first = self.read()
        real = pp._replace_with_retry
        calls = []

        def flaky(tmp, dest, report, tries=6):
            calls.append(dest.name)
            if len(calls) == 3:  # model and snapshot are in place, the metadata fails
                raise pp.BuildError("installing", ["locked"], [], transient=True)
            return real(tmp, dest, report, tries)

        with mock.patch.object(pp, "_replace_with_retry", flaky):
            with self.assertRaises(pp.BuildError):
                self.build(good_tables(pelvis=dict(mass=3.5)))
        self.assertEqual(len(calls), 3)
        self.assertEqual(self.read(), first)

    def test_banner_hash_equals_snapshot_hash(self):
        self.build()
        digest = hashlib.sha256((self.params / "snapshot.csv").read_bytes()).hexdigest()
        self.assertIn(f"snapshot sha256:{digest[:12]})", self.out.read_text(encoding="utf-8"))
        meta = json.loads((self.params / "snapshot.meta.json").read_text(encoding="utf-8"))
        self.assertEqual(meta["snapshot_sha256"], digest)
        self.assertEqual(meta["model_sha256"], hashlib.sha256(self.out.read_bytes()).hexdigest())
        self.assertEqual(meta["schema"], "params/snapshot/1")
        self.assertEqual(sorted(meta), ["model_sha256", "pre_processor_commit", "schema", "sheet_fingerprint",
                                        "snapshot_sha256", "template_sha256"])

    def test_meta_has_no_sheet_id_credential_or_absolute_path(self):
        env = {"FREYJA_SHEET_KEY": "SECRETSHEETID123", "FREYJA_CREDENTIALS": str(self.dir / "key.json")}
        with mock.patch.dict(os.environ, env):
            self.build()
        for name in ("snapshot.meta.json", "snapshot.csv"):
            text = (self.params / name).read_text(encoding="utf-8")
            for bad in ("SECRETSHEETID123", "key.json", str(self.dir), str(self.dir).replace("\\", "/"), ":\\", "C:/"):
                self.assertNotIn(bad, text)

    def test_targets_enter_snapshot_in_si_units(self):
        tables = good_tables()
        tables["targets"] = targets_table()
        r = self.build(tables)
        rows = dict(l.split(",", 1) for l in (self.params / "snapshot.csv").read_text().splitlines()[1:])
        self.assertEqual(rows["target_mass"], "65,'BSIP Reference'!B1")
        self.assertEqual(rows["target_stature"], "1.7,'BSIP Reference'!B2")
        self.assertFalse([w for w in r.warnings if "target" in w])  # targets are not "unused sheet values"

    def test_targets_absent_means_keys_absent(self):
        self.build()
        text = (self.params / "snapshot.csv").read_text()
        self.assertNotIn("target_", text)

    def test_bad_target_is_a_warning_and_is_left_out(self):
        tables = good_tables()
        tables["targets"] = pp.RawTable("targets", "BSIP Reference", 1, 1,
                                        [["Total body mass (kg)", 65], ["Stature", 1700]])
        r = self.build(tables)
        text = (self.params / "snapshot.csv").read_text()
        self.assertIn("target_mass", text)
        self.assertNotIn("target_stature", text)
        self.assertTrue(any("target_stature" in w for w in r.warnings))

    def test_no_snapshot_dir_means_no_snapshot(self):
        pp.build_model(good_tables(), template=self.template, output=self.out, failed_output=self.failed,
                       archive=False)
        self.assertFalse(self.params.exists())
        self.assertEqual(sorted(p.name for p in self.dir.iterdir()), ["models", "t.xml"])

    def test_no_temp_files_left_behind(self):
        self.build()
        self.assertEqual(sorted(p.name for p in self.params.iterdir()), ["snapshot.csv", "snapshot.meta.json"])
        self.assertEqual(sorted(p.name for p in self.out.parent.iterdir()), ["model.xml"])


if __name__ == "__main__":
    unittest.main()
