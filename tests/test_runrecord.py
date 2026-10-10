"""
Stage 1 T1: the run-record library. Ids, git state, hashing, deterministic JSON, schema validation on write.
The git tests build a throwaway repository in a temporary directory. No network, no sheet.

Run from the repo root:
    python -m pytest tests
"""
import copy
import datetime as dt
import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "sim" / "scripts"))

import jsonschema  # noqa: E402
import runrecord as rr  # noqa: E402

SHA = "a" * 64


def sample(**over):
    rec = {
        "schema": "run-summary/1",
        "run_id": "run.20261012-1430-walk_1p4",
        "git_commit": "b" * 40, "git_dirty": False, "diff_sha256": None,
        "snapshot_sha256": SHA, "model_sha256": "c" * 64,
        "seed": 0,
        "env": {"mujoco": "3.10.0", "python": "3.11.9", "numpy": "2.4.6"},
        "scenario": {"name": "walk_1p4", "params": {"gain": 1.5}},
        "controller": {"name": "", "version": ""},
        "timestep_s": 0.002, "duration_s": 5.0,
        "support": "ground",
        "window": {"start_s": 1.0, "end_s": 5.0},
        "outcome": "completed",
        "joints": {"hip_fe_right": {
            "torque_source": "applied", "torque_peak_nm": 40.0, "torque_rms_nm": 20.0,
            "speed_peak_rad_s": 2.0, "power_peak_w": 50.0,
            "rom_used_deg": [-5.0, 30.0], "rom_limit_deg": [-18.1, 133.8], "limit_hit_fraction": 0.0}},
        "skipped": {"lsj_fe": "unlimited"},
        "contacts": {"foot_right": {"normal_force_peak_n": 400.0, "friction_ratio_peak": 0.1}},
        "balance": {"support_margin_min_m": 0.03},
        "diagnostics": {"settled_penetration_m": 0.0004},
        "checks": {"passed": ["check.mjcf.mirror"], "failed": [], "waived": [],
                   "status_model_sha256": "c" * 64, "status_stale": False},
    }
    rec.update(over)
    return rec


class RunId(unittest.TestCase):
    def test_form(self):
        when = dt.datetime(2026, 10, 12, 14, 30, 59)
        self.assertEqual(rr.make_run_id("walk_1p4", when), "run.20261012-1430-walk_1p4")

    def test_rejects_a_scenario_name_that_breaks_the_id(self):
        for bad in ("Walk", "a.b", "a b", ""):
            with self.assertRaises(ValueError):
                rr.make_run_id(bad, dt.datetime(2026, 10, 12, 14, 30))

    def test_directory_name_drops_the_run_prefix(self):
        self.assertEqual(rr.run_dir_name("run.20261012-1430-walk_1p4"), "20261012-1430-walk_1p4")


class Schema(unittest.TestCase):
    def test_sample_validates(self):
        rr.validate(sample())

    def test_schema_file_is_a_valid_schema_with_a_description_on_every_field(self):
        schema = rr.load_schema()
        jsonschema.Draft202012Validator.check_schema(schema)
        missing = []

        def walk(node, path):
            if not isinstance(node, dict):
                return
            for key, sub in node.get("properties", {}).items():
                if "description" not in sub:
                    missing.append(".".join(path + [key]))
                walk(sub, path + [key])
            for key in ("additionalProperties", "items"):
                if isinstance(node.get(key), dict):
                    walk(node[key], path + [key])
        walk(schema, [])
        self.assertEqual(missing, [])
        self.assertIn("actuator", schema["properties"]["joints"]["additionalProperties"]["description"])  # hinge-axis torque caveat

    def test_corrupted_copies_fail(self):
        def drop(path):
            r = copy.deepcopy(sample())
            node = r
            for k in path[:-1]:
                node = node[k]
            del node[path[-1]]
            return r

        corruptions = {
            "missing run_id": drop(["run_id"]),
            "missing joint metric": drop(["joints", "hip_fe_right", "torque_peak_nm"]),
            "wrong schema id": sample(schema="run-summary/2"),
            "bad outcome": sample(outcome="tripped"),
            "bad support": sample(support="floating"),
            "bad torque source": sample(joints={"j": {**sample()["joints"]["hip_fe_right"], "torque_source": "guess"}}),
            "string where number": sample(timestep_s="0.002"),
            "short hash": sample(snapshot_sha256="abc"),
            "bad run id": sample(run_id="walk"),
            "unknown top-level key": {**sample(), "extra": 1},
            "rom pair of three": sample(joints={"j": {**sample()["joints"]["hip_fe_right"], "rom_used_deg": [0, 1, 2]}}),
            "bad skip reason": sample(skipped={"lsj_fe": "boring"}),
        }
        for name, rec in corruptions.items():
            with self.subTest(name):
                with self.assertRaises(rr.RecordError):
                    rr.validate(rec)

    def test_nullable_fields(self):
        rec = sample()
        rec["joints"]["hip_fe_right"].update(rom_limit_deg=None, limit_hit_fraction=None)
        rec["contacts"] = {}
        rec["balance"] = {"support_margin_min_m": None}
        rec["diff_sha256"] = "d" * 64
        rec["git_dirty"] = True
        rr.validate(rec)


class Writing(unittest.TestCase):
    def test_writes_to_the_run_directory_and_returns_the_path(self):
        with tempfile.TemporaryDirectory() as d:
            path = rr.write_summary(sample(), d)
            self.assertEqual(path, Path(d) / "20261012-1430-walk_1p4" / "summary.json")
            self.assertEqual(json.loads(path.read_text(encoding="utf-8"))["run_id"], "run.20261012-1430-walk_1p4")

    def test_same_record_twice_is_byte_identical(self):
        with tempfile.TemporaryDirectory() as a, tempfile.TemporaryDirectory() as b:
            first = rr.write_summary(sample(), a).read_bytes()
            second = rr.write_summary(sample(), b).read_bytes()
            again = rr.write_summary(sample(), a).read_bytes()
            self.assertEqual(first, second)
            self.assertEqual(first, again)

    def test_key_order_of_the_input_does_not_matter(self):
        rec = sample()
        shuffled = {k: rec[k] for k in reversed(list(rec))}
        self.assertEqual(rr.dumps(rec), rr.dumps(shuffled))

    def test_sorted_keys_lf_endings_trailing_newline_no_crlf(self):
        text = rr.dumps(sample())
        self.assertTrue(text.endswith("\n"))
        self.assertNotIn("\r", text)
        top = list(json.loads(text))
        self.assertEqual(top, sorted(top))

    def test_bytes_on_disk_have_no_crlf(self):
        with tempfile.TemporaryDirectory() as d:
            self.assertNotIn(b"\r", rr.write_summary(sample(), d).read_bytes())

    def test_invalid_record_writes_nothing(self):
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaises(rr.RecordError):
                rr.write_summary(sample(outcome="tripped"), d)
            self.assertEqual(list(Path(d).iterdir()), [])

    def test_non_finite_numbers_are_refused(self):
        rec = sample()
        rec["joints"]["hip_fe_right"]["torque_peak_nm"] = float("nan")
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaises(rr.RecordError):
                rr.write_summary(rec, d)
            self.assertEqual(list(Path(d).iterdir()), [])

    def test_numpy_scalars_are_written_as_plain_numbers(self):
        import numpy as np
        rec = sample(timestep_s=np.float64(0.002), seed=np.int64(3))
        text = rr.dumps(rec)
        self.assertEqual(json.loads(text)["seed"], 3)


class FileHash(unittest.TestCase):
    def test_sha256_file(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "x.bin"
            p.write_bytes(b"freyja\n")
            self.assertEqual(rr.sha256_file(p), hashlib.sha256(b"freyja\n").hexdigest())


def git(cwd, *args):
    subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@example.com", "-c", "commit.gpgsign=false", *args],
                   cwd=cwd, check=True, capture_output=True)


class GitState(unittest.TestCase):
    def make_repo(self, d):
        git(d, "init", "-q")
        (Path(d) / "a.txt").write_text("one\n", encoding="utf-8", newline="\n")
        git(d, "add", "a.txt")
        git(d, "commit", "-q", "-m", "first")

    def head(self, d):
        return subprocess.run(["git", "rev-parse", "HEAD"], cwd=d, check=True, capture_output=True, text=True).stdout.strip()

    def test_clean_tree(self):
        with tempfile.TemporaryDirectory() as d:
            self.make_repo(d)
            state = rr.git_state(d)
            self.assertEqual(state, {"git_commit": self.head(d), "git_dirty": False, "diff_sha256": None})

    def test_dirty_tree_sets_flag_and_hash_of_the_diff(self):
        with tempfile.TemporaryDirectory() as d:
            self.make_repo(d)
            (Path(d) / "a.txt").write_text("two\n", encoding="utf-8", newline="\n")
            state = rr.git_state(d)
            self.assertTrue(state["git_dirty"])
            diff = subprocess.run(["git", "diff", "HEAD"], cwd=d, check=True, capture_output=True).stdout
            self.assertEqual(state["diff_sha256"], hashlib.sha256(diff).hexdigest())
            self.assertEqual(len(state["diff_sha256"]), 64)

    def test_staged_change_also_counts(self):
        with tempfile.TemporaryDirectory() as d:
            self.make_repo(d)
            (Path(d) / "a.txt").write_text("two\n", encoding="utf-8", newline="\n")
            git(d, "add", "a.txt")
            self.assertTrue(rr.git_state(d)["git_dirty"])

    def test_different_edits_give_different_hashes(self):
        with tempfile.TemporaryDirectory() as d:
            self.make_repo(d)
            (Path(d) / "a.txt").write_text("two\n", encoding="utf-8", newline="\n")
            h1 = rr.git_state(d)["diff_sha256"]
            (Path(d) / "a.txt").write_text("three\n", encoding="utf-8", newline="\n")
            self.assertNotEqual(h1, rr.git_state(d)["diff_sha256"])

    def test_untracked_files_do_not_make_the_tree_dirty(self):
        with tempfile.TemporaryDirectory() as d:
            self.make_repo(d)
            (Path(d) / "new.txt").write_text("x\n", encoding="utf-8")
            self.assertFalse(rr.git_state(d)["git_dirty"])

    def test_returns_to_clean_after_revert(self):
        with tempfile.TemporaryDirectory() as d:
            self.make_repo(d)
            (Path(d) / "a.txt").write_text("two\n", encoding="utf-8", newline="\n")
            (Path(d) / "a.txt").write_text("one\n", encoding="utf-8", newline="\n")
            self.assertIsNone(rr.git_state(d)["diff_sha256"])


class Environment(unittest.TestCase):
    def test_versions(self):
        env = rr.env_versions()
        self.assertEqual(set(env), {"mujoco", "python", "numpy"})
        self.assertTrue(all(isinstance(v, str) and v for v in env.values()))
        self.assertEqual(env["python"].count("."), 2)


if __name__ == "__main__":
    unittest.main()
