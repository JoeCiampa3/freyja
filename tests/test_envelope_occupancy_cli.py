"""Volume-extractor brief 6, items 3, 4 and 7 through the command line: `fy envelope check` with and without a registry (the output without one is the old output, exactly), `fy envelope
free`, and the worked example on the right thigh (read against the built cache when it exists)."""
import re
import subprocess
import sys
from pathlib import Path

import numpy as np
import pytest
import yaml

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "tools"))

from envelope import field, frames, oracle, registry  # noqa: E402
from envelope.synthetic import box, frustum  # noqa: E402

ENV = REPO / "data" / "envelope"
CACHE = ENV / "cache"
R_ENV, H = 45.0, 300.0


def fy(*args):
    return subprocess.run([sys.executable, str(REPO / "tools" / "fy"), "envelope", *args], capture_output=True, text=True, cwd=REPO)


@pytest.fixture(scope="module")
def world(tmp_path_factory):
    """<tmp>/cache/thigh_R.npz (a cylinder of radius 45), <tmp>/components/thigh_R.yaml (a bar, with a mesh twin), <tmp>/shapes.yaml and pose files."""
    root = tmp_path_factory.mktemp("world")
    (root / "cache").mkdir()
    (root / "components").mkdir()
    v, f = frustum(R_ENV, R_ENV, 60, -H - 60)
    seg = field.build_segment(v, f, length=H, voxel=2.0, z_top=0.0, margin=40.0)
    seg.meta = {"inputs_sha256_12": "abc123abc123", "segment": "thigh_R"}
    seg.save(root / "cache" / "thigh_R.npz")
    bv, bf = box(8, 8, 30)
    registry.write_stl(root / "components" / "bar.stl", bv, bf)
    reg = {"schema": "components/1", "segment": "thigh_R", "components": [
        {"id": "p.bar", "name": "bar", "status": "designed", "owner": "thigh_R", "primitive": {"type": "box", "half": [8, 8, 30]}, "mesh": "bar.stl",
         "pose": {"tx": -22, "ty": 0, "tz": -150}, "clearance_mm": 2.0, "source": "test"},
        {"id": "p.pod", "name": "pod", "status": "candidate", "owner": "thigh_R", "primitive": {"type": "cylinder", "radius": 5, "length": 20}, "pose": {"tx": 0, "ty": 0, "tz": -150}}]}
    (root / "components" / "thigh_R.yaml").write_text(yaml.safe_dump(reg))
    (root / "shapes.yaml").write_text(yaml.safe_dump({"shapes": [{"name": "rod", "type": "cylinder", "radius": 10, "length": 100}]}))
    (root / "ok.csv").write_text("tx,ty,tz\n12,0,-150\n")                  # axes 34 apart: rod 10, bar face 8 -> 16 between, less the 2 mm clearance: 14
    (root / "hit.csv").write_text("tx,ty,tz\n12,0,-150\n-5,0,-150\n")
    return root


def run(world, poses, *extra):
    return fy("check", "--segment", "thigh_R", "--shapes", str(world / "shapes.yaml"), "--poses", str(world / poses), "--cache-dir", str(world / "cache"), *extra)


def old_output(world, poses_name, required=0.0):
    """What `fy envelope check` printed before the registry existed, rebuilt from the oracle."""
    seg = field.Segment.load(world / "cache" / "thigh_R.npz")
    shapes, poses = oracle.read_shapes(world / "shapes.yaml"), oracle.read_poses(world / poses_name)
    out = oracle.clearance(seg, shapes, poses, required)
    L = [f"segment thigh_R (inputs {seg.meta['inputs_sha256_12']}), {len(poses)} pose(s), {len(shapes)} shape(s)"]
    L += [f"  pose {i}: margin {m:8.2f} mm   slab overrun {o:6.2f} mm" for i, (m, o) in enumerate(zip(out["margins_mm"], out["slab_overruns_mm"]))]
    x, y, z = out["point_mm"]
    L.append(f"binds at pose {out['pose_index']} on {out['shape']}: margin {out['margin_mm']:.2f} mm at station {out['station_mm']:.1f} mm, point (x {x:.1f}, y {y:.1f}, z {z:.1f}) mm")
    L.append(f"slab overrun {out['slab_overrun_mm']:.2f} mm; required margin {out['required_mm']:.2f} mm")
    L.append("FEASIBLE" if out["feasible"] else "INFEASIBLE")
    return "\n".join(L) + "\n", out["feasible"]


def test_without_a_registry_and_with_no_occupied_the_output_and_exit_code_are_the_old_ones(world, tmp_path):
    expect, feasible = old_output(world, "ok.csv")
    bare = fy("check", "--segment", "thigh_R", "--shapes", str(world / "shapes.yaml"), "--poses", str(world / "ok.csv"), "--cache-dir", str(world / "cache"), "--components-dir", str(tmp_path))
    assert bare.stdout == expect and bare.returncode == (0 if feasible else 1)
    ignored = run(world, "ok.csv", "--no-occupied")
    assert ignored.stdout == expect and ignored.returncode == bare.returncode
    expect2, feasible2 = old_output(world, "hit.csv")
    assert run(world, "hit.csv", "--no-occupied").stdout == expect2 and feasible2                      # the skin alone does not see the bar: that is what the registry adds
    assert run(world, "hit.csv", "--no-occupied").returncode == 0


def test_with_a_registry_the_margin_to_each_placed_component_enters_the_verdict(world):
    ok = run(world, "ok.csv")
    assert ok.returncode == 0, ok.stdout + ok.stderr
    head, _ = old_output(world, "ok.csv")
    assert ok.stdout.startswith(head[: head.rindex("FEASIBLE")])                                  # the skin lines come first, unchanged
    assert "components (" in ok.stdout and "bar [designed]: margin" in ok.stdout and "pod" not in ok.stdout.split("components (")[1]       # a candidate takes no space
    assert re.search(r"\(distance 1[56]\.\d\d - clearance 2\.00\)", ok.stdout)
    assert "binding constraint: component bar" in ok.stdout and "voxel 2 mm; confidence: clear" in ok.stdout and ok.stdout.rstrip().endswith("FEASIBLE")
    assert "exact mesh-to-mesh distance of the binding pair: 16.000 mm" in ok.stdout
    bad = run(world, "hit.csv")
    assert bad.returncode == 1 and bad.stdout.rstrip().endswith("INFEASIBLE") and "the meshes overlap" in bad.stdout
    bound = [l for l in bad.stdout.splitlines() if l.startswith("binding constraint")][0]
    assert "component bar" in bound and "pose 1" in bound


def test_a_marginal_result_is_labelled_marginal(world, tmp_path):
    (tmp_path / "edge.csv").write_text("tx,ty,tz\n9,0,-150\n")                                 # 31 between the axes: 15 between the surfaces... less 2: 13? no: -> use the skin instead
    (tmp_path / "edge.csv").write_text("tx,ty,tz\n0,32,-150\n")                                # the rod's rim sits 3 mm from the skin
    r = run(world, str(tmp_path / "edge.csv"), "--required", "2")
    assert "confidence: marginal" in r.stdout and "binding constraint: skin" in r.stdout and r.returncode == 0


def test_occupied_without_a_registry_says_so_and_the_two_flags_exclude_each_other(world, tmp_path):
    r = fy("check", "--segment", "thigh_R", "--shapes", str(world / "shapes.yaml"), "--poses", str(world / "ok.csv"), "--cache-dir", str(world / "cache"), "--components-dir", str(tmp_path), "--occupied")
    assert r.returncode == 2 and "no component registry" in r.stderr
    assert run(world, "ok.csv", "--occupied", "--no-occupied").returncode == 2


def test_a_component_sticking_out_of_the_skin_is_a_warning(world, tmp_path):
    comps = tmp_path / "components"
    comps.mkdir()
    reg = yaml.safe_load((world / "components" / "thigh_R.yaml").read_text())
    reg["components"][0].pop("mesh")
    reg["components"][0]["pose"]["tx"] = 40
    (comps / "thigh_R.yaml").write_text(yaml.safe_dump(reg))
    r = fy("check", "--segment", "thigh_R", "--shapes", str(world / "shapes.yaml"), "--poses", str(world / "ok.csv"), "--cache-dir", str(world / "cache"), "--components-dir", str(comps))
    assert "WARNING: bar sticks out of the skin" in r.stdout


def test_free_writes_the_ledger_and_reports_volumes_and_the_largest_sphere(world, tmp_path):
    r = fy("free", "--segment", "thigh_R", "--cache-dir", str(world / "cache"), "--components-dir", str(world / "components"), "--out", str(tmp_path))
    assert r.returncode == 0, r.stderr
    d = yaml.safe_load((tmp_path / "free" / "thigh_R.yaml").read_text())
    assert d["segment"] == "thigh_R" and [c["name"] for c in d["components"]] == ["bar"] and d["inputs_sha256_12"]
    assert d["skin_volume_l"] == pytest.approx(np.pi * R_ENV ** 2 * H / 1e6, rel=0.01)
    assert d["free_volume_l"] + d["occupied_volume_l"] == pytest.approx(d["skin_volume_l"], abs=2e-4)
    assert d["occupied_volume_l"] == pytest.approx(20 * 20 * 64 / 1e6 * 1.0, rel=0.35)           # a 16 x 16 x 60 bar dilated by 2 mm
    rows = d["rows"]
    assert [r_["s_mm"] for r_ in rows[:3]] == [0.0, 10.0, 20.0] and rows[-1]["s_mm"] == pytest.approx(H) and {"area_mm2", "cheb_r_mm", "hw_ant_mm", "area_t5_mm2"} <= set(rows[0])
    mid = next(r_ for r_ in rows if r_["s_mm"] == 150.0)
    assert mid["area_mm2"] < next(r_ for r_ in rows if r_["s_mm"] == 50.0)["area_mm2"]                  # the bar takes room at the middle station only
    text = (tmp_path / "free" / "thigh_R.yaml").read_text()
    assert text.startswith("# GENERATED by fy envelope free") and "\r" not in text and str(tmp_path) not in text
    again = fy("free", "--segment", "thigh_R", "--cache-dir", str(world / "cache"), "--components-dir", str(world / "components"), "--out", str(tmp_path))
    assert (tmp_path / "free" / "thigh_R.yaml").read_text() == text and again.stdout == r.stdout        # deterministic
    big = fy("free", "--segment", "thigh_R", "--required", "10", "--cache-dir", str(world / "cache"), "--components-dir", str(world / "components"), "--out", str(tmp_path / "t10"))
    assert yaml.safe_load((tmp_path / "t10" / "free" / "thigh_R.yaml").read_text())["skin_volume_l"] < d["skin_volume_l"] * 0.7


def test_a_union_check_reads_the_registry_of_the_second_body_in_the_frame_of_the_first(tmp_path):
    """Two stacked bodies cut from one cylinder at z = -100; a bar registered in the lower body's own frame is found where it really is, in the first body's frame."""
    cache, comps = tmp_path / "cache", tmp_path / "components"
    cache.mkdir()
    comps.mkdir()
    v, f = frustum(R_ENV, R_ENV, 60, -300 - 60)
    upper = field.build_segment(v, f, length=100.0, voxel=2.0, z_top=0.0, margin=40.0)
    lower = field.build_segment(v + np.array([0.0, 0.0, 100.0]), f, length=200.0, voxel=2.0, z_top=0.0, margin=40.0)
    upper.meta = {"inputs_sha256_12": "u", "origin_xyz": [0.0, 0.0, 1000.0], **frames.meta("pelvis", 0.0, 0.0, 100.0)}        # a test body whose model frame is its own (brief 7: no shift)
    lower.meta = {"inputs_sha256_12": "l", "origin_xyz": [0.0, 0.0, 900.0], **frames.meta("abdomen", 0.0, 0.0, 200.0)}      # the lower body's origin is 100 mm below the upper's
    upper.save(cache / "pelvis.npz")
    lower.save(cache / "abdomen.npz")
    reg = {"schema": "components/1", "segment": "abdomen", "components": [
        {"id": "b", "name": "bar", "status": "designed", "owner": "abdomen", "primitive": {"type": "cylinder", "radius": 6, "length": 40}, "pose": {"tx": -20, "tz": -50}}]}
    (comps / "abdomen.yaml").write_text(yaml.safe_dump(reg))                                  # z = -50 in the lower frame is z = -150 in the upper's
    (tmp_path / "s.yaml").write_text(yaml.safe_dump({"shapes": [{"name": "rod", "type": "cylinder", "radius": 6, "length": 40}]}))
    (tmp_path / "p.csv").write_text("tx,ty,tz\n10,0,-150\n")                                  # axes 30 apart: 18 between the surfaces
    r = fy("check", "--segment", "pelvis,abdomen", "--shapes", str(tmp_path / "s.yaml"), "--poses", str(tmp_path / "p.csv"), "--cache-dir", str(cache))
    assert r.returncode == 0, r.stdout + r.stderr
    line = next(l for l in r.stdout.splitlines() if l.strip().startswith("bar [designed]"))
    assert re.search(r"margin 1[78]\.\d\d mm", line) and "z -1" in line, line
    moved = fy("check", "--segment", "pelvis,abdomen", "--shapes", str(tmp_path / "s.yaml"), "--poses", str(tmp_path / "p.csv"), "--cache-dir", str(cache), "--no-occupied")
    assert "bar" not in moved.stdout


def test_free_needs_a_built_segment(tmp_path):
    r = fy("free", "--segment", "thigh_R", "--cache-dir", str(tmp_path))
    assert r.returncode == 2 and "fy envelope build" in r.stderr


# ---- the worked example on the right thigh (item 7) ------------------------------------------------------------------------------------------

EX = ENV / "examples"
cache_missing = pytest.mark.skipif(not (CACHE / "thigh_R.npz").exists(), reason="the built segments are a gitignored cache (fy envelope build)")


def thigh(poses):
    return fy("check", "--segment", "thigh_R", "--shapes", str(EX / "thigh_components_shapes.yaml"), "--poses", str(EX / f"thigh_components_{poses}_poses.csv"))


@cache_missing
def test_the_worked_example_has_a_feasible_a_colliding_and_an_outside_candidate():
    ok, hit, out = thigh("feasible"), thigh("colliding"), thigh("outside")
    assert ok.returncode == 0 and ok.stdout.rstrip().endswith("FEASIBLE") and "actuator [designed]: margin 27.00 mm" in ok.stdout
    assert hit.returncode == 1 and "binding constraint: component actuator" in hit.stdout and "actuator [designed]: margin -" in hit.stdout
    assert out.returncode == 1 and "binding constraint: skin" in out.stdout and "binds at pose 0 on pod: margin -" in out.stdout
    for r in (ok, hit, out):
        assert "driver [designed]" in r.stdout and "confidence: clear" in r.stdout


@cache_missing
def test_the_committed_outputs_of_the_worked_example_are_what_the_cli_prints():
    for name in ("feasible", "colliding", "outside"):
        committed = (EX / f"thigh_components_{name}.out").read_text()
        assert committed == thigh(name).stdout, name


@cache_missing
def test_the_thigh_rod_example_is_reproduced_exactly_with_the_registry_ignored():
    """Gate 5 of the trial: feasible margin 16.61 mm at station 275.0 mm, infeasible -8.18 mm at station 275.0 mm (pose 3); the output format is the old one."""
    for poses, margin, feasible in (("rod_feasible_poses.csv", 16.61, True), ("rod_infeasible_poses.csv", -8.18, False)):
        r = fy("check", "--segment", "thigh_R", "--shapes", str(EX / "rod_shapes.yaml"), "--poses", str(EX / poses), "--no-occupied")
        assert r.returncode == (0 if feasible else 1)
        assert f"margin {margin:.2f} mm at station 275.0 mm" in r.stdout.replace("binds at pose 0 on rod: ", "").replace("binds at pose 3 on rod: ", "")
        assert "components (" not in r.stdout and "confidence" not in r.stdout


@cache_missing
def test_the_committed_free_ledger_of_the_thigh_is_what_the_cli_writes(tmp_path):
    r = fy("free", "--segment", "thigh_R", "--out", str(tmp_path))
    assert r.returncode == 0, r.stderr
    assert (tmp_path / "free" / "thigh_R.yaml").read_text() == (ENV / "free" / "thigh_R.yaml").read_text()
    d = yaml.safe_load((ENV / "free" / "thigh_R.yaml").read_text())
    assert [c["name"] for c in d["components"]] == ["actuator", "driver"] and d["largest_free_sphere"]["diameter_mm"] > 80
