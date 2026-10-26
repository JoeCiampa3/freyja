"""Volume-extractor brief 1, step 12 and gates 4-5: the clearance oracle and `fy envelope check`."""
import subprocess
import sys
from pathlib import Path

import numpy as np
import pytest
import yaml

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "tools"))
sys.path.insert(0, str(REPO / "tests"))

from envelope import field, oracle  # noqa: E402
from envelope.synthetic import frustum  # noqa: E402

R_ENV, H = 45.0, 300.0


@pytest.fixture(scope="module")
def seg():
    v, f = frustum(R_ENV, R_ENV, 60, -H - 60)
    return field.build_segment(v, f, length=H, voxel=2.0, z_top=0.0, margin=40.0)


def rod(radius=20.0, length=150.0, name="rod"):
    return {"name": name, "type": "cylinder", "radius": radius, "length": length}


def pose(tx=0.0, ty=0.0, tz=-150.0, rx=0.0, ry=0.0, rz=0.0):
    return np.array([tx, ty, tz, rx, ry, rz], float)


def test_centred_cylinder_margin_is_the_radius_difference(seg):
    out = oracle.clearance(seg, [rod()], [pose()])
    assert abs(out["margin_mm"] - (R_ENV - 20.0)) < 1.0
    assert out["pose_index"] == 0 and out["feasible"]


def test_lateral_offset_sweep_margin_falls_one_for_one_and_goes_infeasible(seg):
    offs = [0.0, 10.0, 20.0, 30.0]
    out = oracle.clearance(seg, [rod()], [pose(ty=o) for o in offs])
    expect = [R_ENV - 20.0 - o for o in offs]
    assert np.allclose(out["margins_mm"], expect, atol=1.0)
    assert out["margin_mm"] == min(out["margins_mm"]) and out["pose_index"] == 3
    assert not out["feasible"]
    assert out["point_mm"][1] > 0                      # binds on the +y side, the way it was moved


def test_binding_station_is_at_an_end_of_a_tilted_rod(seg):
    # tilted about x, the rod's two ends swing out to +y and -y by 75 sin 12 deg = 15.6 mm: it binds at one of them (station 75 or 225)
    out = oracle.clearance(seg, [rod(radius=10.0)], [pose(rx=-12.0)])
    assert min(abs(out["station_mm"] - 75.0), abs(out["station_mm"] - 225.0)) < 6.0
    # the end rim's far point is 75 sin 12 + 10 cos 12 = 25.4 mm off the axis, so the margin is about 45 - 25.4
    assert abs(out["margin_mm"] - (R_ENV - 75 * np.sin(np.radians(12)) - 10 * np.cos(np.radians(12)))) < 1.5


def test_box_and_capsule_shapes(seg):
    out = oracle.clearance(seg, [{"name": "b", "type": "box", "half": [15, 10, 40]}], [pose()])
    assert abs(out["margin_mm"] - (R_ENV - np.hypot(15, 10))) < 1.0       # the corner binds
    out = oracle.clearance(seg, [{"name": "c", "type": "capsule", "radius": 12, "length": 100}], [pose()])
    assert abs(out["margin_mm"] - (R_ENV - 12.0)) < 1.0


def test_shape_outside_the_slab_is_reported_as_overrun(seg):
    out = oracle.clearance(seg, [rod(length=150.0)], [pose(tz=-250.0)])        # runs from -175 to -325, 25 mm past the knee plane
    assert abs(out["slab_overrun_mm"] - 25.0) < 1.0
    assert not out["feasible"]


def test_poses_csv_and_shapes_yaml_round_trip(tmp_path):
    (tmp_path / "p.csv").write_text("tx,ty,tz\n0,0,-150\n0,5,-150\n")
    (tmp_path / "s.yaml").write_text(yaml.safe_dump({"shapes": [rod()]}))
    P = oracle.read_poses(tmp_path / "p.csv")
    S = oracle.read_shapes(tmp_path / "s.yaml")
    assert P.shape == (2, 6) and P[1, 1] == 5 and S[0]["radius"] == 20


def test_unknown_shape_type_and_bad_columns_are_rejected(tmp_path):
    with pytest.raises(ValueError):
        oracle.sample_shape({"name": "x", "type": "torus"})
    (tmp_path / "p.csv").write_text("a,b\n1,2\n")
    with pytest.raises(ValueError):
        oracle.read_poses(tmp_path / "p.csv")


def test_segment_round_trips_through_its_cache_file(seg, tmp_path):
    seg.save(tmp_path / "s.npz")
    back = field.Segment.load(tmp_path / "s.npz")
    pts = np.array([[0, 0, -100.0], [30, 10, -200.0]])
    assert np.allclose(back.signed_distance(pts), seg.signed_distance(pts))


def test_cli_check_prints_margin_and_binding_station_for_a_feasible_and_an_infeasible_case(seg, tmp_path):
    cache = tmp_path / "cache"
    cache.mkdir()
    seg.save(cache / "thigh_R.npz")
    (tmp_path / "s.yaml").write_text(yaml.safe_dump({"shapes": [rod()]}))
    (tmp_path / "ok.csv").write_text("tx,ty,tz\n0,0,-150\n0,5,-150\n")
    (tmp_path / "bad.csv").write_text("tx,ty,tz\n0,0,-150\n0,30,-150\n")
    run = lambda poses: subprocess.run([sys.executable, str(REPO / "tools" / "fy"), "envelope", "check", "--segment", "thigh_R",
                                        "--shapes", str(tmp_path / "s.yaml"), "--poses", str(tmp_path / poses), "--cache-dir", str(cache)],
                                       capture_output=True, text=True, cwd=REPO)
    ok, bad = run("ok.csv"), run("bad.csv")
    assert ok.returncode == 0 and "FEASIBLE" in ok.stdout and "margin" in ok.stdout and "station" in ok.stdout, ok.stdout + ok.stderr
    assert bad.returncode == 1 and "INFEASIBLE" in bad.stdout and "pose 1" in bad.stdout, bad.stdout + bad.stderr


# ---- brief 5, item 3: containment in the union of adjacent bodies ------------------------------------------------------------------------

@pytest.fixture(scope="module")
def stacked():
    """A cylinder of radius 45 cut into two adjacent bodies at z = -100: the upper body spans z in [0, -100], the lower [-100, -300] (each in its own frame, origin at its top)."""
    v, f = frustum(R_ENV, R_ENV, 60, -H - 60)
    upper = field.build_segment(v, f, length=100.0, voxel=2.0, z_top=0.0, margin=40.0)
    lower_v = v + np.array([0.0, 0.0, 100.0])                       # the lower body's frame has its origin at z = -100 of the first
    lower = field.build_segment(lower_v, f, length=200.0, voxel=2.0, z_top=0.0, margin=40.0)
    return upper, lower


def test_a_rod_across_the_interface_is_contained_in_the_union_though_it_overruns_each_body(stacked):
    upper, lower = stacked
    parts = [(upper, (0, 0, 0)), (lower, (0, 0, -100))]
    shape = [rod(radius=20.0, length=150.0)]
    p = [pose(tz=-100.0)]                                           # centred on the interface: z from -25 to -175... no: 150 long, so -25 to -175
    assert oracle.clearance(upper, shape, p)["slab_overrun_mm"] > 0 and not oracle.clearance(upper, shape, p)["feasible"]
    out = oracle.clearance_union(parts, shape, p)
    assert out["slab_overrun_mm"] == 0.0 and out["feasible"]
    assert abs(out["margin_mm"] - (R_ENV - 20.0)) < 1.0


def test_the_union_overruns_beyond_its_outer_planes_and_binds_on_the_skin_like_one_body(stacked):
    upper, lower = stacked
    parts = [(upper, (0, 0, 0)), (lower, (0, 0, -100))]
    out = oracle.clearance_union(parts, [rod()], [pose(tz=-250.0)])        # reaches z = -325, 25 mm past the lower plane at -300
    assert out["slab_overrun_mm"] == pytest.approx(25.0, abs=1.0) and not out["feasible"]
    out = oracle.clearance_union(parts, [rod()], [pose(tz=-100.0, ty=30.0)])
    assert out["margin_mm"] == pytest.approx(R_ENV - 20.0 - 30.0, abs=1.0) and not out["feasible"]


def test_a_gap_between_two_bodies_is_an_overrun():
    v, f = frustum(R_ENV, R_ENV, 60, -H - 60)
    a = field.build_segment(v, f, length=60.0, voxel=2.0, z_top=0.0, margin=40.0)
    b = field.build_segment(v, f, length=60.0, voxel=2.0, z_top=-100.0, margin=40.0)
    out = oracle.clearance_union([(a, (0, 0, 0)), (b, (0, 0, 0))], [rod(radius=10.0, length=120.0)], [pose(tz=-80.0)])      # spans -20 to -140: the gap -60 to -100 is in no slab
    assert out["slab_overrun_mm"] == pytest.approx(20.0, abs=1.0)
