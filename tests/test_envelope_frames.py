"""Volume-extractor brief 7, item 1: the registry and the oracle use the model body frames. The pelvis origin is the lumbosacral joint, the abdomen's the TJC, the thorax's and the head and
neck's the CJC; the legs are as before. The mesh-to-model trunk shift is computed (the mesh hip line x less the model's HJC x relative to the pelvis origin), not typed."""
import subprocess
import sys
from pathlib import Path

import numpy as np
import pytest
import yaml

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "tools"))

from envelope import field, frames, oracle, sheet  # noqa: E402
from envelope.synthetic import frustum  # noqa: E402

ENV = REPO / "data" / "envelope"
CACHE = ENV / "cache"
EX = ENV / "examples"
SNAPSHOT = REPO / "params" / "snapshot.csv"
HJC_X = sheet.read_snapshot(SNAPSHOT)["thigh_right_pos_x"] * 1000.0          # the model's HJC ahead of its pelvis origin, mm
built = pytest.mark.skipif(not (CACHE / "head_neck.npz").exists() or "model_to_segment_mm" not in field.Segment.load(CACHE / "head_neck.npz").meta,
                           reason="the built segments are a gitignored cache (fy envelope build)")


def cli(*args):
    return subprocess.run([sys.executable, str(REPO / "tools" / "fy"), "envelope", *args], capture_output=True, text=True, cwd=REPO)


# ---- the offsets -------------------------------------------------------------------------------------------------------------------------

def test_the_hip_x_is_the_models_and_is_read_from_the_snapshot():
    import mujoco
    m = mujoco.MjModel.from_xml_path(str(REPO / "sim" / "models" / "freyja.xml"))
    d = mujoco.MjData(m)
    mujoco.mj_forward(m, d)
    pel, thigh = (d.xpos[mujoco.mj_name2id(m, mujoco.mjtObj.mjOBJ_BODY, n)] for n in ("pelvis", "thigh_right"))
    assert frames.hjc_x_in_pelvis_mm(SNAPSHOT) == pytest.approx((thigh[0] - pel[0]) * 1000.0, abs=1e-6)
    assert 56.0 < HJC_X < 57.5                                                 # 56.7 mm: ADR 0004's "56.6 now"


def test_the_trunk_bodies_shift_by_the_hip_x_and_the_legs_do_not_move():
    for name in ("pelvis", "abdomen", "thorax"):
        assert frames.model_to_segment_mm(name, HJC_X, 100.0) == (-HJC_X, 0.0, 0.0)
    assert frames.model_to_segment_mm("head_neck", HJC_X, 265.7) == (-HJC_X, 0.0, -265.7)        # the oracle puts its origin at the vertex, the model's at the CJC below
    for name in ("thigh_R", "shank_R", "foot_R"):
        assert frames.model_to_segment_mm(name, HJC_X, 400.0) == (0.0, 0.0, 0.0)
    with pytest.raises(ValueError):
        frames.model_to_segment_mm("arm", HJC_X, 1.0)


def test_the_mesh_to_model_shift_is_the_hip_line_less_the_model_hip_x():
    assert frames.mesh_to_model_trunk_shift_mm(50.0, 56.7) == pytest.approx(-6.7)


def test_a_segment_without_the_key_is_a_leg_or_a_stop():
    seg = field.Segment.load(CACHE / "thigh_R.npz") if (CACHE / "thigh_R.npz").exists() else None
    assert frames.segment_offset_mm("thigh_R", {}) == (0.0, 0.0, 0.0)
    with pytest.raises(sheet.StopAndAsk, match="fy envelope build"):
        frames.segment_offset_mm("pelvis", {"segment": "pelvis"})
    assert frames.segment_offset_mm("pelvis", {"model_to_segment_mm": [-1.0, 0.0, 0.0]}) == (-1.0, 0.0, 0.0)
    assert seg is None or "model_to_segment_mm" not in seg.meta


# ---- the oracle applies it ---------------------------------------------------------------------------------------------------------------

def cylinder_segment():
    v, f = frustum(45, 45, 60, -360)
    return field.build_segment(v, f, length=300.0, voxel=2.0, z_top=0.0, margin=40.0)


def test_the_oracle_applies_the_shift_and_reports_in_the_frame_the_poses_were_given_in():
    seg = cylinder_segment()
    shapes = [{"name": "rod", "type": "cylinder", "radius": 10, "length": 60}]
    off = (-56.7, 0.0, 0.0)
    plain = oracle.clearance(seg, shapes, [[10.0, 5.0, -150.0]])
    model = oracle.clearance(seg, shapes, [[10.0 + 56.7, 5.0, -150.0]], frame_offset_mm=off)
    assert model["margin_mm"] == pytest.approx(plain["margin_mm"], abs=1e-9) and model["slab_overrun_mm"] == plain["slab_overrun_mm"]
    assert model["point_mm"] == pytest.approx([plain["point_mm"][0] + 56.7, *plain["point_mm"][1:]], abs=1e-9)        # the binding point in the model frame
    assert model["frame_offset_mm"] == list(off) and "frame_offset_mm" in plain and plain["frame_offset_mm"] == [0.0, 0.0, 0.0]
    wrong = oracle.clearance(seg, shapes, [[10.0 + 56.7, 5.0, -150.0]])
    assert wrong["margin_mm"] < plain["margin_mm"] - 20.0                    # without the shift the same pose is 56.7 mm off in x: a different answer


def test_the_union_applies_the_shift_to_the_first_bodys_frame():
    upper, lower = cylinder_segment(), cylinder_segment()
    shapes = [{"name": "rod", "type": "cylinder", "radius": 10, "length": 60}]
    parts = [(upper, (0.0, 0.0, 0.0)), (lower, (0.0, 0.0, -100.0))]
    plain = oracle.clearance_union(parts, shapes, [[10.0, 0.0, -150.0]])
    model = oracle.clearance_union(parts, shapes, [[10.0 + 56.7, 0.0, -150.0]], frame_offset_mm=(-56.7, 0.0, 0.0))
    assert model["margin_mm"] == pytest.approx(plain["margin_mm"], abs=1e-9) and model["point_mm"][0] == pytest.approx(plain["point_mm"][0] + 56.7)


# ---- the command line ----------------------------------------------------------------------------------------------------------------------

@pytest.fixture(scope="module")
def world(tmp_path_factory):
    root = tmp_path_factory.mktemp("frames")
    (root / "cache").mkdir()
    seg = cylinder_segment()
    seg.meta = {"inputs_sha256_12": "abc", "segment": "pelvis", "origin_xyz": [50.0, -16.8, 968.0]}
    seg.save(root / "cache" / "pelvis.npz")                                         # a trunk body from a build before brief 7: no model frame
    seg.meta = {**seg.meta, **frames.meta("abdomen", 50.0, HJC_X, 127.0)}
    seg.save(root / "cache" / "abdomen.npz")                                       # named like a trunk body but carries the key
    (root / "s.yaml").write_text(yaml.safe_dump({"shapes": [{"name": "rod", "type": "cylinder", "radius": 10, "length": 60}]}))
    (root / "p.csv").write_text(f"tx,ty,tz\n{10 + HJC_X},0,-150\n")
    return root


def test_a_trunk_cache_from_before_the_model_frames_stops_and_says_to_rebuild(world):
    r = cli("check", "--segment", "pelvis", "--shapes", str(world / "s.yaml"), "--poses", str(world / "p.csv"), "--cache-dir", str(world / "cache"))
    assert r.returncode == 3 and "fy envelope build" in r.stderr


def test_a_trunk_check_prints_the_frame_and_the_shift(world):
    r = cli("check", "--segment", "abdomen", "--shapes", str(world / "s.yaml"), "--poses", str(world / "p.csv"), "--cache-dir", str(world / "cache"))
    assert r.returncode == 0, r.stdout + r.stderr
    line = next(l for l in r.stdout.splitlines() if l.startswith("frame:"))
    assert f"{HJC_X:.3f}" in line and "mesh hip line x 50.000" in line and f"mesh-to-model trunk shift {50.0 - HJC_X:.3f}" in line, line
    margin = float(r.stdout.split("binds at pose")[1].split("margin ")[1].split(" mm")[0])
    assert margin == pytest.approx(25.0, abs=0.5)               # a radius-45 cylinder, a radius-10 rod at x = 10 in the oracle frame (HJC_X + 10 in the model frame): 45 - 10 - 10


def test_a_leg_check_prints_no_frame_line(world):
    seg = cylinder_segment()
    seg.meta = {"inputs_sha256_12": "abc", "segment": "thigh_R"}
    seg.save(world / "cache" / "thigh_R.npz")
    (world / "pl.csv").write_text("tx,ty,tz\n10,0,-150\n")
    r = cli("check", "--segment", "thigh_R", "--shapes", str(world / "s.yaml"), "--poses", str(world / "pl.csv"), "--cache-dir", str(world / "cache"))
    assert r.returncode == 0 and "frame:" not in r.stdout


# ---- the built segments and the migrated examples -------------------------------------------------------------------------------------------

@built
def test_the_model_lsj_origin_maps_to_the_expected_mesh_position():
    """The model's pelvis origin (the LSJ) in the mesh frame, against the MuJoCo model's own positions relative to the right hip centre, which sits on the mesh hip line."""
    import mujoco
    pel, thigh = field.Segment.load(CACHE / "pelvis.npz"), field.Segment.load(CACHE / "thigh_R.npz")
    m = mujoco.MjModel.from_xml_path(str(REPO / "sim" / "models" / "freyja.xml"))
    d = mujoco.MjData(m)
    mujoco.mj_forward(m, d)
    xp = {n: d.xpos[mujoco.mj_name2id(m, mujoco.mjtObj.mjOBJ_BODY, n)] * 1000.0 for n in ("pelvis", "thigh_right", "abdomen", "thorax", "head_and_neck")}
    hjc_mesh = np.array(thigh.meta["origin_xyz"])
    lsj = frames.model_to_mesh(pel.meta, "pelvis", [0.0, 0.0, 0.0])
    want = hjc_mesh + (xp["pelvis"] - xp["thigh_right"])
    assert lsj[0] == pytest.approx(want[0], abs=1e-6) and lsj[2] == pytest.approx(want[2], abs=1e-6)         # x and z against the model; y is the mesh midline (the mesh hips are not the sheet's width)
    assert lsj[0] == pytest.approx(pel.meta["mesh_hip_line_x_mm"] - HJC_X, abs=1e-9) and lsj[1] == pytest.approx(pel.meta["origin_xyz"][1])
    for body, name in (("abdomen", "abdomen"), ("thorax", "thorax"), ("head_and_neck", "head_neck")):
        seg = field.Segment.load(CACHE / f"{name}.npz")
        p = frames.model_to_mesh(seg.meta, name, [0.0, 0.0, 0.0])
        w = hjc_mesh + (xp[body] - xp["thigh_right"])
        assert p[0] == pytest.approx(w[0], abs=1e-6) and p[2] == pytest.approx(w[2], abs=1e-3), name          # the sheet's body origins: TJC, CJC, CJC


@built
def test_the_trunk_example_poses_are_in_the_model_frame_and_their_margins_are_unchanged():
    """Memo 36's margins (pelvis box +37.128 / -11.588, thorax box +17.497 / -34.405, union +39.405 / overrun 37.318): the poses moved by the constant, the answers did not."""
    for name in ("pelvis_box", "thorax_box"):
        for kind in ("feasible", "infeasible"):
            rows = oracle.read_poses(EX / f"{name}_{kind}_poses.csv")
            assert rows[0, 0] == pytest.approx(10.0 + HJC_X, abs=1e-6), (name, kind)
    def binding(out):
        return float(out.split("binds at pose")[1].split("margin ")[1].split(" mm")[0])
    want = {("pelvis", "pelvis_box"): (37.128, -11.588), ("thorax", "thorax_box"): (17.497, -34.405)}
    for (body, name), (ok, bad) in want.items():
        for kind, margin in (("feasible", ok), ("infeasible", bad)):
            r = cli("check", "--segment", body, "--shapes", str(EX / f"{name}_shapes.yaml"), "--poses", str(EX / f"{name}_{kind}_poses.csv"))
            assert abs(binding(r.stdout) - margin) <= 0.01, (name, kind, r.stdout)
    u = ("check", "--segment", "pelvis,abdomen", "--shapes", str(EX / "trunk_union_shapes.yaml"))
    ok, bad = cli(*u, "--poses", str(EX / "trunk_union_feasible_poses.csv")), cli(*u, "--poses", str(EX / "trunk_union_infeasible_poses.csv"))
    assert ok.returncode == 0 and bad.returncode == 1
    assert abs(binding(ok.stdout) - 39.405) <= 0.01 and abs(float(bad.stdout.split("slab overrun ")[-1].split(" mm")[0]) - 37.318) <= 0.01
    assert "frame:" in ok.stdout and "frame:" in bad.stdout
