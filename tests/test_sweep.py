"""
Stage 1c T5: the posture sweep tool. Grids are evaluated on an inline fixture (a heavy trunk on a hinge, a pelvis and a foot
box on a hinge ankle) where every point has an analytic or independently computed answer. No sheet, no network.

Run from the repo root:
    python -m pytest tests
"""
import copy
import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "sim" / "scripts"))

import mujoco  # noqa: E402

import leanpose  # noqa: E402
import runrecord as rr  # noqa: E402
import sweep  # noqa: E402

TRUNK = """
<mujoco model="trunk">
  <worldbody>
    <geom name="floor" type="plane" size="5 5 0.1"/>
    <body name="pelvis" pos="0 0 1.0">
      <freejoint/>
      <inertial pos="0 0 0" mass="10" diaginertia="1 1 1"/>
      <body name="abdomen" pos="0 0 0.1">
        <inertial pos="0 0 0.5" mass="30" diaginertia="1 1 1"/>
        <joint name="lsj_fe" type="hinge" axis="0 1 0" pos="0 0 -0.1"/>
      </body>
      <body name="foot_right" pos="0 0 -0.1">
        <inertial pos="0 0 0" mass="1e-6" diaginertia="1e-9 1e-9 1e-9"/>
        <joint name="ankle_pdflex_right" type="hinge" axis="0 -1 0" range="-30 30"/>
        <geom type="box" pos="0.03 0 -0.05" size="0.08 0.04 0.05" mass="0"/>
      </body>
    </body>
  </worldbody>
</mujoco>
"""
G = 9.81
WEIGHT = (10 + 30 + 1e-6) * G
BASE = {"name": "stand_static", "model": "x", "seed": 0, "support": "ground_wrench", "drive": "static_equilibrium",
        "duration_s": 0.0, "window": {"start_s": 0.0, "end_s": 0.0}, "pose": {"com_x_rel_ankle_m": 0.0}}


def sha(text):
    return hashlib.sha256(text.encode()).hexdigest()


class Workspace:
    def __init__(self, xml=TRUNK, tamper=False):
        self.tmp = tempfile.TemporaryDirectory()
        d = Path(self.tmp.name)
        self.model, self.snapshot, self.meta, self.out = d / "m.xml", d / "s.csv", d / "meta.json", d / "sweeps"
        self.model.write_text(xml, encoding="utf-8", newline="\n")
        self.snapshot.write_text("placeholder,value,sheet_source\nx,1,A1\n", encoding="utf-8", newline="\n")
        self.meta.write_text(json.dumps({"model_sha256": sha(xml), "snapshot_sha256": rr.sha256_file(self.snapshot)}), encoding="utf-8")
        if tamper:
            self.model.write_text(xml.replace("mass=\"30\"", "mass=\"31\""), encoding="utf-8", newline="\n")

    def kwargs(self, now=None):
        import datetime as dt
        return dict(model_path=self.model, snapshot_path=self.snapshot, meta_path=self.meta, sweeps_dir=self.out,
                    base_scenario=copy.deepcopy(BASE), now=now or dt.datetime(2026, 10, 12, 14, 30))

    def cleanup(self):
        self.tmp.cleanup()


def spec(grid=None, constraints=None):
    return {"name": "fixture", "base": "stand_static",
            "grid": grid or {"com_x_rel_ankle_m": {"start": -0.06, "stop": 0.14, "n": 6}, "lsj_fe_deg": {"start": -10.0, "stop": 20.0, "n": 4}},
            "constraints": constraints or {"min_support_margin_m": 0.02, "min_limit_margin_deg": 2.0}}


class Grid(unittest.TestCase):
    def test_points_are_the_cartesian_product_in_a_fixed_order(self):
        pts = sweep.grid_points({"a_deg": {"start": 0, "stop": 2, "n": 3}, "b_deg": {"start": 10, "stop": 20, "n": 2}})
        self.assertEqual(len(pts), 6)
        self.assertEqual(pts[0], {"a_deg": 0.0, "b_deg": 10.0})
        self.assertEqual(pts[1], {"a_deg": 0.0, "b_deg": 20.0})  # the last parameter varies fastest
        self.assertEqual(pts[-1], {"a_deg": 2.0, "b_deg": 20.0})

    def test_a_single_point_axis_sits_at_start(self):
        self.assertEqual(sweep.grid_points({"x_deg": {"start": 5, "stop": 9, "n": 1}}), [{"x_deg": 5.0}])

    def test_spec_checks(self):
        ok = spec()
        sweep.check_spec(ok)
        for bad in (
                {**ok, "grid": {}},
                {**ok, "grid": {f"p{i}": {"start": 0, "stop": 1, "n": 2} for i in range(4)}},  # more than three parameters
                {**ok, "grid": {"bogus_deg": {"start": 0, "stop": 1, "n": 2}}},  # not a pose parameter
                {**ok, "grid": {"lsj_fe_deg": {"start": 0, "stop": 1, "n": 0}}},
                {k: v for k, v in ok.items() if k != "base"},
        ):
            with self.assertRaises(sweep.SweepError):
                sweep.check_spec(bad)

    def test_constraint_defaults(self):
        s = spec()
        del s["constraints"]
        self.assertEqual(sweep.check_spec(s)["constraints"], {"min_support_margin_m": 0.02, "min_limit_margin_deg": 1.0})

    def test_point_cap_is_enforced_before_anything_is_created(self):
        ws = Workspace()
        self.addCleanup(ws.cleanup)
        big = spec({"com_x_rel_ankle_m": {"start": 0, "stop": 0.01, "n": 21}, "lsj_fe_deg": {"start": 0, "stop": 1, "n": 21}, "tj_fe_deg": {"start": 0, "stop": 1, "n": 5}})  # 2205
        with self.assertRaises(sweep.SweepError) as cm:
            sweep.run_sweep(big, **ws.kwargs())
        self.assertIn("2000", str(cm.exception))
        self.assertFalse(ws.out.exists())
        self.assertEqual(sweep.MAX_POINTS, 2000)


class Fixture(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.ws = Workspace()
        cls.result = sweep.run_sweep(spec(), **cls.ws.kwargs())
        cls.rec = cls.result.record
        cls.model = mujoco.MjModel.from_xml_string(TRUNK)

    @classmethod
    def tearDownClass(cls):
        cls.ws.cleanup()

    def fk(self, params):
        lean = leanpose.solve_pose(self.model, params, {"foot_right": "ankle_pdflex_right"})
        data = mujoco.MjData(self.model)
        data.qpos[:] = lean.qpos
        mujoco.mj_forward(self.model, data)
        return data

    def test_every_point_reproduces_the_analytic_ankle_torque_and_the_independent_trunk_torque(self):
        axis_y = self.model.jnt_axis[mujoco.mj_name2id(self.model, mujoco.mjtObj.mjOBJ_JOINT, "ankle_pdflex_right")][1]
        self.assertEqual(len(self.rec["points"]), 24)
        checked = 0
        for p in self.rec["points"]:
            if p["torques"] is None:
                continue
            d = p["params"]["com_x_rel_ankle_m"]
            self.assertAlmostEqual(p["torques"]["ankle_pdflex_right"], axis_y * WEIGHT * d, delta=1e-8 + 1e-6 * G * 0.1, msg=str(p["params"]))
            data = self.fk(p["params"])
            j = mujoco.mj_name2id(self.model, mujoco.mjtObj.mjOBJ_JOINT, "lsj_fe")
            b = self.model.jnt_bodyid[j]
            moment = np.cross(data.xipos[b] - data.xanchor[j], self.model.body_mass[b] * np.array([0, 0, -G]))
            self.assertAlmostEqual(p["torques"]["lsj_fe"], float(-data.xaxis[j] @ moment), delta=1e-9 * max(1.0, abs(p["torques"]["lsj_fe"])), msg=str(p["params"]))
            checked += 1
        self.assertEqual(checked, 24)

    def test_feasibility_follows_the_support_polygon_and_the_constraints(self):
        # foot box spans -0.05 to +0.11 m about the ankle; the default margin is 0.02 m
        for p in self.rec["points"]:
            d = p["params"]["com_x_rel_ankle_m"]
            inside = -0.03 <= d <= 0.09
            self.assertEqual(p["feasible"], inside and p["limit_margin_min_deg"] >= 2.0, str(p["params"]))
            if not p["feasible"]:
                self.assertTrue(p["reasons"], str(p["params"]))
        self.assertTrue(any(p["feasible"] for p in self.rec["points"]))
        self.assertTrue(any(not p["feasible"] for p in self.rec["points"]))

    def test_infeasible_points_are_excluded_from_the_ranges_and_the_minimum(self):
        feasible = [p for p in self.rec["points"] if p["feasible"]]
        every = [p for p in self.rec["points"] if p["torques"] is not None]
        for joint in ("ankle_pdflex_right", "lsj_fe"):
            vals = [p["torques"][joint] for p in feasible]
            r = self.rec["ranges"][joint]
            self.assertEqual((r["min"], r["max"]), (min(vals), max(vals)))
            self.assertAlmostEqual(r["spread"], max(vals) - min(vals), places=12)
        # the unfiltered extreme is larger, so the exclusion is real
        self.assertGreater(max(abs(p["torques"]["ankle_pdflex_right"]) for p in every), max(abs(self.rec["ranges"]["ankle_pdflex_right"][k]) for k in ("min", "max")))
        best = min(feasible, key=lambda p: p["sum_squares_nm2"])
        self.assertEqual(self.rec["minimum"]["params"], best["params"])
        self.assertAlmostEqual(self.rec["minimum"]["sum_squares_nm2"], sum(v * v for v in best["torques"].values()), places=9)
        self.assertTrue(all(p["feasible"] for p in [best]))

    def test_record_is_stamped_like_a_run_and_validates(self):
        rr_ = self.rec
        for key in ("git_commit", "git_dirty", "diff_sha256", "snapshot_sha256", "model_sha256", "env", "spec", "sweep_id"):
            self.assertIn(key, rr_)
        self.assertEqual(rr_["sweep_id"], "sweep.20261012-1430-fixture")
        self.assertEqual(rr_["model_sha256"], sha(TRUNK))
        sweep.validate(rr_)
        self.assertEqual(self.result.path, self.ws.out / "20261012-1430-fixture" / "sweep.json")
        self.assertTrue((self.result.path.parent / "SWEEP.md").is_file())
        self.assertFalse(any(self.ws.out.glob("*/*/summary.json")))  # no run directory per point

    def test_outputs_are_byte_identical_on_a_second_run(self):
        ws = Workspace()
        self.addCleanup(ws.cleanup)
        again = sweep.run_sweep(spec(), **ws.kwargs())
        self.assertEqual(again.path.read_bytes(), self.result.path.read_bytes())
        self.assertEqual((again.path.parent / "SWEEP.md").read_bytes(), (self.result.path.parent / "SWEEP.md").read_bytes())
        self.assertNotIn(b"\r", self.result.path.read_bytes())

    def test_a_corrupted_record_fails_validation(self):
        bad = copy.deepcopy(self.rec)
        del bad["points"][0]["feasible"]
        with self.assertRaises(sweep.SweepError):
            sweep.validate(bad)

    def test_ms_per_point_is_reported_but_not_recorded(self):
        self.assertGreater(self.result.ms_per_point, 0.0)
        self.assertNotIn("ms_per_point", json.dumps(self.rec))

    def test_unreachable_points_are_infeasible_with_a_reason_not_a_crash(self):
        ws = Workspace()
        self.addCleanup(ws.cleanup)
        rec = sweep.run_sweep(spec({"com_x_rel_ankle_m": {"start": 0.0, "stop": 2.0, "n": 2}}), **ws.kwargs()).record
        far = rec["points"][1]
        self.assertFalse(far["feasible"])
        self.assertIsNone(far["torques"])
        self.assertTrue(any("unreachable" in r for r in far["reasons"]))


class Markdown(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.ws = Workspace()
        cls.result = sweep.run_sweep(spec(), **cls.ws.kwargs())
        cls.text = (cls.result.path.parent / "SWEEP.md").read_text(encoding="utf-8")

    @classmethod
    def tearDownClass(cls):
        cls.ws.cleanup()

    def test_states_plainly_what_the_sum_of_squares_and_the_minimum_are(self):
        low = self.text.lower()
        self.assertIn("unnormalised", low)
        self.assertIn("property of the model", low)
        self.assertIn("not a recommended posture", low)

    def test_lists_every_point_when_the_grid_is_small_with_flag_reason_margin_and_chain_torques(self):
        rows = [l for l in self.text.splitlines() if l.startswith("| ") and "com_x" not in l and "---" not in l]
        self.assertGreaterEqual(len([l for l in rows if "yes" in l or "no" in l]), 24)
        self.assertIn("hip flexion", self.text.lower())

    def test_lists_unbounded_joints_and_the_corners(self):
        self.assertIn("lsj_fe", self.text)
        self.assertIn("unbounded", self.text.lower())
        self.assertIn("corner", self.text.lower())

    def test_stays_under_the_line_cap_for_the_largest_grids(self):
        base = json.loads(self.result.path.read_text(encoding="utf-8"))
        big = copy.deepcopy(base)
        template = big["points"][0]
        big["points"] = []
        for i in range(2000):
            p = copy.deepcopy(template)
            p["params"] = {"com_x_rel_ankle_m": i * 1e-4, "lsj_fe_deg": float(i % 7)}
            p["feasible"], p["reasons"] = (i % 3 != 0), ([] if i % 3 else ["support margin 1.0 mm < 20.0 mm"])
            big["points"].append(p)
        text = sweep.render_md(big)
        self.assertLess(len(text.splitlines()), 400)
        self.assertEqual(text, sweep.render_md(copy.deepcopy(big)))


class Staleness(unittest.TestCase):
    def test_tampered_model_is_refused_and_creates_nothing(self):
        ws = Workspace(tamper=True)
        self.addCleanup(ws.cleanup)
        with self.assertRaises(sweep.StaleModelError):
            sweep.run_sweep(spec(), **ws.kwargs())
        self.assertFalse(ws.out.exists())

    def test_cli_exits_non_zero_on_a_bad_spec(self):
        with tempfile.TemporaryDirectory() as d:
            code = sweep.main(["nothing", "--specs-dir", d])
        self.assertNotEqual(code, 0)


if __name__ == "__main__":
    unittest.main()
