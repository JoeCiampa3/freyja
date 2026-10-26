"""Volume-extractor brief 6, item 5: foreign components. Poses of a part fixed to the pelvis, in the right thigh's frame, built on the MuJoCo model. Offline."""
import csv
import re
import subprocess
import sys
from pathlib import Path

import numpy as np
import pytest
import yaml
from scipy.spatial.transform import Rotation

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "tools"))

from envelope import field, foreign, oracle  # noqa: E402
from envelope.sheet import StopAndAsk  # noqa: E402
from envelope.synthetic import frustum  # noqa: E402

NAMES = ["hip_fe_right", "hip_aa_right", "hip_ier_right"]


@pytest.fixture(scope="module")
def model():
    return foreign.load_model()


def snap():
    with open(REPO / "params" / "snapshot.csv", newline="", encoding="utf-8") as fh:
        return {r["placeholder"]: float(r["value"]) for r in csv.DictReader(fh)}


def test_at_q_zero_the_host_origin_is_the_hjc_the_shank_hangs_below_it_and_a_pelvis_point_is_shifted_by_the_hip_offset(model):
    import mujoco
    s = snap()
    hip = np.array([s["thigh_right_pos_x"], s["thigh_right_pos_y"], s["thigh_right_pos_z"]])
    bid = lambda n: mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_BODY, n)
    assert np.allclose(model.body_pos[bid("thigh_right")], hip)                                  # the thigh body's origin is the HJC, in the pelvis frame
    d = mujoco.MjData(model)
    mujoco.mj_kinematics(model, d)
    L = s["thigh_right_length"]
    assert np.allclose(d.xpos[bid("shank_right")] - d.xpos[bid("thigh_right")], [0, 0, -L])        # the shank body is (0, 0, -L_thigh) from the host origin
    p = np.array([10.0, -20.0, 30.0])                                                              # mm, pelvis frame
    out = foreign.foreign_poses(model, "pelvis", "thigh_R", [*p, 0, 0, 0], NAMES, [[0, 0, 0]])[0]
    assert np.allclose(out[:3], p - hip * 1000.0, atol=1e-6) and np.allclose(out[3:], 0, atol=1e-9)


def test_hip_flexion_is_the_analytic_rotation_with_the_sign_of_the_polarity_file(model):
    hip = model.body_pos[foreign._body_id(model, "thigh_R")] * 1000.0
    p = np.array([40.0, 5.0, -25.0]) + hip                                                         # a pelvis point
    f = 35.0
    out = foreign.foreign_poses(model, "pelvis", "thigh_R", [*p, 0, 0, 0], ["hip_fe_right"], [[f]])[0]
    # flexion swings the knee forward (probe sign +1 in the file): the thigh turns about -y by f, so a pelvis point seen from the thigh turns about +y by f
    want = Rotation.from_euler("y", f, degrees=True).as_matrix() @ (p - hip)
    assert np.allclose(out[:3], want, atol=1e-6)
    assert np.allclose(Rotation.from_euler("xyz", out[3:], degrees=True).as_matrix(), Rotation.from_euler("y", f, degrees=True).as_matrix(), atol=1e-9)
    assert foreign.POLARITY["hip_fe_right"] == 1 and foreign.clinical_factor(model, "hip_fe_right") == 1
    flipped = foreign.foreign_poses(model, "pelvis", "thigh_R", [*p, 0, 0, 0], ["hip_fe_right"], [[f]], polarity={"hip_fe_right": -1})[0]      # a file that said the other way flips the sample
    assert np.allclose(flipped[:3], Rotation.from_euler("y", -f, degrees=True).as_matrix() @ (p - hip), atol=1e-6)


def test_the_hinges_compose_in_the_models_order_and_all_three_move_the_part(model):
    hj = foreign.joints_of(model, "thigh_R")
    assert [j["name"] for j in hj] == NAMES and hj[0]["range_deg"] == pytest.approx((-31.0, 133.8))
    hip = model.body_pos[foreign._body_id(model, "thigh_R")] * 1000.0
    p = np.array([40.0, 5.0, -25.0]) + hip
    a = np.array([30.0, 20.0, -15.0])
    out = foreign.foreign_poses(model, "pelvis", "thigh_R", [*p, 0, 0, 0], NAMES, [a])[0]
    # successive hinges of one body, in the order the model lists them: R_thigh_in_pelvis = Ry(-fe) Rx(aa) Rz(ier) (axes 0 -1 0, 1 0 0, 0 0 1); the part sees the inverse
    Rt = Rotation.from_euler("y", -a[0], degrees=True).as_matrix() @ Rotation.from_euler("x", a[1], degrees=True).as_matrix() @ Rotation.from_euler("z", a[2], degrees=True).as_matrix()
    assert np.allclose(out[:3], Rt.T @ (p - hip), atol=1e-6)


def test_the_default_sampling_covers_the_model_ranges_and_is_the_same_size_for_both_sides(model):
    names, s = foreign.default_samples(model, "thigh_R")
    assert names == NAMES and s.shape[1] == 3 and len(s) == len({tuple(r) for r in s.round(6)})
    rng = [j["range_deg"] for j in foreign.joints_of(model, "thigh_R")]
    for k in range(3):
        assert s[:, k].min() == pytest.approx(rng[k][0]) and s[:, k].max() == pytest.approx(rng[k][1])          # the full range, endpoints included
    sweep = np.sort(s[(s[:, 1] == 0) & (s[:, 2] == 0), 0])
    assert {-30.0, -5.0, 0.0, 5.0, 130.0} <= set(sweep) and np.allclose(np.diff(sweep)[1:-1], 5.0)             # 5 degree steps (the ends are the limits)
    assert len(s[(s[:, 0] % 15 == 0) & (s[:, 1] % 15 == 0) & (s[:, 2] % 15 == 0)]) > 100                      # and the 15 degree grid
    nl, sl = foreign.default_samples(model, "thigh_L")
    assert nl == [n.replace("right", "left") for n in NAMES] and sl.shape == s.shape                          # the mirror leaves the count unchanged


def test_the_left_side_is_an_open_item(model):
    with pytest.raises(NotImplementedError, match="right side only"):
        foreign.foreign_poses(model, "pelvis", "thigh_L", [0] * 6, ["hip_fe_left"], [[0]])


def test_the_stop_conditions_of_the_brief():
    import mujoco
    text = (REPO / "sim" / "models" / "freyja.xml").read_text(encoding="utf-8")
    off = text.replace('<joint name="hip_ier_right" type="hinge" axis="0 0 1"', '<joint name="hip_ier_right" type="hinge" pos="0 0 -0.05" axis="0 0 1"', 1)
    assert off != text
    with pytest.raises(StopAndAsk, match="not all about the body origin"):
        foreign.check_hip_chain(mujoco.MjModel.from_xml_string(off), "thigh_R")
    rot = text.replace('<body name="thigh_right" pos=', '<body name="thigh_right" quat="0.9962 0 0.0872 0" pos=', 1)
    assert rot != text
    with pytest.raises(StopAndAsk, match="rotated relative to its parent"):
        foreign.check_hip_chain(mujoco.MjModel.from_xml_string(rot), "thigh_R")
    two = text.replace('<joint name="hip_aa_right" type="hinge" axis="1 0 0" limited="true" range="-40.5 25.6"/>', "", 1)
    assert two != text
    with pytest.raises(StopAndAsk, match="three serial hip rotations"):
        foreign.check_hip_chain(mujoco.MjModel.from_xml_string(two), "thigh_R")


def test_samples_csv_in_and_poses_csv_out_round_trip_through_the_oracle(model, tmp_path):
    (tmp_path / "q.csv").write_text("# a trajectory\nhip_fe_right,hip_aa_right\n0,0\n45,10\n90,-5\n")
    names, a = foreign.read_samples(tmp_path / "q.csv")
    assert names == ["hip_fe_right", "hip_aa_right"] and a.shape == (3, 2)
    poses = foreign.foreign_poses(model, "pelvis", "thigh_R", [30, 0, -10, 0, 0, 0], names, a)
    foreign.write_poses(tmp_path / "p.csv", poses, "test")
    back = oracle.read_poses(tmp_path / "p.csv")
    assert back.shape == (3, 6) and np.allclose(back, poses, atol=1e-3)
    assert (tmp_path / "p.csv").read_text().startswith("# GENERATED by fy envelope foreign")


def test_the_helpers_output_feeds_the_check_and_reproduces_a_hand_computed_margin(model, tmp_path):
    """A sphere of radius 5 fixed to the pelvis 30 mm in front of the hip axis and 20 mm below the hip, in a thigh whose skin is a cylinder of radius 45 about the thigh's z axis. At flexion 0
    it sits at (30, 0, -20) in the thigh frame: 45 - 30 - 5 = 10 mm from the skin. At 90 degrees it is at (z, y, -x) = (-20, 0, -30): 45 - 20 - 5 = 20 mm."""
    hip = model.body_pos[foreign._body_id(model, "thigh_R")] * 1000.0
    placement = [*(hip + np.array([30.0, 0.0, -20.0])), 0, 0, 0]
    (tmp_path / "q.csv").write_text("hip_fe_right\n0\n90\n")
    names, a = foreign.read_samples(tmp_path / "q.csv")
    poses = foreign.foreign_poses(model, "pelvis", "thigh_R", placement, names, a)
    assert np.allclose(poses[0, :3], [30, 0, -20], atol=1e-6) and np.allclose(poses[1, :3], [-20, 0, -30], atol=1e-6)
    foreign.write_poses(tmp_path / "p.csv", poses, "test")
    v, f = frustum(45.0, 45.0, 60, -300 - 60)
    seg = field.build_segment(v, f, length=300.0, voxel=2.0, z_top=0.0, margin=40.0)
    seg.meta = {"inputs_sha256_12": "x"}
    seg.save(tmp_path / "thigh_R.npz")
    (tmp_path / "s.yaml").write_text(yaml.safe_dump({"shapes": [{"name": "ball", "type": "capsule", "radius": 5, "length": 0}]}))
    out = oracle.clearance(seg, oracle.read_shapes(tmp_path / "s.yaml"), oracle.read_poses(tmp_path / "p.csv"))
    assert out["margins_mm"] == pytest.approx([10.0, 20.0], abs=1.0) and out["pose_index"] == 0
    r = subprocess.run([sys.executable, str(REPO / "tools" / "fy"), "envelope", "check", "--segment", "thigh_R", "--shapes", str(tmp_path / "s.yaml"), "--poses", str(tmp_path / "p.csv"),
                        "--cache-dir", str(tmp_path)], capture_output=True, text=True, cwd=REPO)
    margins = [float(m) for m in re.findall(r"pose \d: margin\s+(-?\d+\.\d+)", r.stdout)]
    assert r.returncode == 0 and margins == pytest.approx([10.0, 20.0], abs=1.0), r.stdout + r.stderr


# ---- the worked example (item 6) --------------------------------------------------------------------------------------------------------------

EX = REPO / "data" / "envelope" / "examples" / "thigh_foreign"
CACHE = REPO / "data" / "envelope" / "cache"


def fy(*args):
    return subprocess.run([sys.executable, str(REPO / "tools" / "fy"), "envelope", *args], capture_output=True, text=True, cwd=REPO)


def test_the_committed_groin_poses_are_what_the_command_in_their_header_writes(tmp_path):
    first = (EX / "components" / "groin_poses.csv").read_text().splitlines()[0]
    assert "pelvis part 101.7188,-62.4307,-72.6824,0,0,0 in thigh_R" in first
    r = fy("foreign", "--owner", "pelvis", "--host", "thigh_R", "--placement", "101.7188,-62.4307,-72.6824,0,0,0", "--samples", "data/envelope/examples/thigh_foreign/hip_flexion_samples.csv",
           "--out", str(tmp_path / "g.csv"))
    assert r.returncode == 0, r.stderr
    assert (tmp_path / "g.csv").read_text() == (EX / "components" / "groin_poses.csv").read_text()
    poses = oracle.read_poses(EX / "components" / "groin_poses.csv")
    assert len(poses) == 14 and np.allclose(poses[0, :3], [45, 30, 25], atol=1e-3) and np.allclose(poses[:, 4], [0, 10, 20, 30, 40, 50, 60, 70, 80, 90, 80, 70, 60, 50], atol=1e-3)       # flexion 0..130
    assert np.allclose(poses[:, 1], 30.0, atol=1e-3)                          # flexion is about y: the part keeps its y


@pytest.mark.skipif(not (CACHE / "thigh_R.npz").exists(), reason="the built segments are a gitignored cache (fy envelope build)")
def test_the_committed_outputs_of_the_foreign_example_are_what_the_cli_prints(tmp_path):
    for name, code in (("feasible", 0), ("colliding", 1)):
        r = fy("check", "--segment", "thigh_R", "--shapes", "data/envelope/examples/thigh_components_shapes.yaml", "--poses", f"data/envelope/examples/thigh_foreign/pod_{name}_poses.csv",
               "--components-dir", "data/envelope/examples/thigh_foreign/components")
        assert r.returncode == code and r.stdout == (EX / f"pod_{name}.out").read_text(), name
    colliding = (EX / "pod_colliding.out").read_text()
    assert "groin unit [foreign]: margin -22.99" in colliding and "binding constraint: component groin unit" in colliding and "sweep pose 8 of 14" in colliding       # hip flexion 80 degrees
    r = fy("free", "--segment", "thigh_R", "--components-dir", "data/envelope/examples/thigh_foreign/components", "--out", str(tmp_path))
    assert (tmp_path / "free" / "thigh_R.yaml").read_text() == (EX / "free" / "thigh_R.yaml").read_text()
