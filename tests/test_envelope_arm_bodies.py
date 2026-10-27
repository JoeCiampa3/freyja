"""Volume-extractor brief 8, Phase A: the committed result of `fy envelope gates` for the arms (`data/envelope/arm_bodies.json`, the gates in `leg_R_trial.json`, the closure and the share table in
`trunk_bodies.json`), the arm ledgers, and the worked examples through `fy envelope check`. The result is read, not rebuilt; the code that makes it is tested in test_envelope_arms.py."""
import csv
import json
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "tools"))

from envelope import arms, field  # noqa: E402

ENV = REPO / "data" / "envelope"
CACHE = ENV / "cache"
EX = ENV / "examples"
NAMES = ("upper_arm", "forearm", "hand")
built = pytest.mark.skipif(not (CACHE / "upper_arm_R.npz").exists(), reason="the built segments are a gitignored cache (fy envelope build)")


@pytest.fixture(scope="module")
def res():
    return json.loads((ENV / "arm_bodies.json").read_text())


@pytest.fixture(scope="module")
def snap():
    return {r["placeholder"]: float(r["value"]) for r in csv.DictReader(open(REPO / "params/snapshot.csv"))}


def cli(*args):
    return subprocess.run([sys.executable, str(REPO / "tools" / "fy"), "envelope", *args], capture_output=True, text=True, cwd=REPO)


def test_every_gate_passes_and_the_arm_gates_are_in_the_table():
    gates = json.loads((ENV / "leg_R_trial.json").read_text())["gates"]
    assert all(g["pass"] for g in gates)
    names = " | ".join(g["gate"] for g in gates)
    for body in ("upper_arm_R", "forearm_R", "hand_R"):
        assert f"1 {body}: topology matches base; surface watertight" in names
    for want in ("2 arms: |stretch-1| within 2 x 17.3 mm / sheet length", "3b arms: field volume", "5 oracle example upper_arm_cylinder", "5 oracle example forearm_box", "5 oracle union query arm_union", "7 closure"):
        assert want in names


def test_the_stretches_are_each_against_their_own_gate_which_is_two_sigma_over_the_sheet_length(res, snap):
    r = res["registration"]
    assert r["sigma_mm"] == 17.3
    for n in ("upper_arm", "forearm"):
        L = snap[f"{n}_right_length"] * 1000.0
        assert r["lengths_sheet_mm"][n] == pytest.approx(L)
        assert r["gate"][n] == pytest.approx(2 * 17.3 / L)
        assert r["stretch"][n] == pytest.approx(L / r["lengths_mesh_mm"][n])
        assert abs(r["stretch"][n] - 1.0) < r["gate"][n]
    assert 1.12 < r["stretch"]["upper_arm"] < 1.13 and 1.11 < r["stretch"]["forearm"] < 1.13        # the sculpt's arms are about 11% shorter than the sheet's
    assert r["hand"]["stretch"] == 1.0
    ang = r["angle_from_vertical_deg"]
    assert 40 < ang["upper_arm"] < 46 and 53 < ang["forearm"] < 59                                       # the A-pose: far from vertical, hence a rotation and not a shear
    assert r["mirror_gap_mm"] == pytest.approx(0.0, abs=1e-6)


def test_the_ansur_arm_lengths_are_context_and_the_forearm_is_about_eight_percent_short(res):
    a = res["ansur_cross_check"]
    assert set(a) == {"shoulder_elbow", "radiale_stylion", "forearm_hand", "hand_length"}
    assert a["radiale_stylion"]["mesh_over_ansur"] == pytest.approx(0.92, abs=0.01)


def test_design_numbers_are_the_sheet_mass_over_the_volumes_and_the_conform_adds_volume(res, snap):
    for n in NAMES:
        d = res["design"][n]
        assert d["sheet_mass_kg"] == pytest.approx(snap[f"{n}_right_mass"])
        assert d["required_density_skin_kg_per_l"] == pytest.approx(d["sheet_mass_kg"] / d["skin_volume_l"], rel=1e-9)
        v = [d["skin_volume_l"]] + [d["inner_volume_l"][t] for t in ("t3", "t5", "t8", "t10")]
        assert v == sorted(v, reverse=True)
        assert d["conform_volume_change_l"] == pytest.approx(d["skin_volume_l"] - d["unconformed_skin_volume_l"], abs=1e-9)
        assert d["unconformed_skin_volume_l"] == pytest.approx(d["skin_volume_l"] / d["axial_stretch"], rel=1e-9)
    assert res["design"]["hand"]["conform_volume_change_l"] == 0.0
    assert sum(res["design"][n]["conform_volume_change_l"] for n in NAMES) * 2 == pytest.approx(res["closure"]["conform_effect_arms_l"], abs=1e-9)
    assert 0.3 < res["closure"]["conform_effect_arms_l"] < 0.5                                           # Joe's expectation, memo 38 decision 4: about +0.3 l


def test_the_hand_is_the_whole_hand_with_its_wrist_interface_section(res):
    h = res["hand"]
    assert h["volume_l"] == pytest.approx(res["design"]["hand"]["skin_volume_l"])
    bb = h["bounding_box_mm"]
    assert 150 < bb["z_axial"] < 200 and 60 < bb["x_anterior"] < 130 and 60 < bb["y_lateral"] < 130
    w = h["wrist_section"]
    assert 800 < w["area_mm2"] < 2000 and w["width_x_mm"] > w["width_y_mm"] > 0
    assert abs(res["interface_sections"]["wrist"]["relative"]) < 0.03                                    # the hand starts where the forearm ends (same rotation)


def test_the_joint_zones_are_reported_with_and_without_and_the_upper_arm_without_the_girdle(res):
    z = res["joint_zone_volumes_l"]
    u = z["upper_arm"]
    assert u["without_all_l"] < u["with_zones_l"] and u["without_girdle_l"] == pytest.approx(u["with_zones_l"] - u["girdle_l"], abs=1e-9)
    assert 0.2 < u["girdle_l"] < 0.35 and set(u["slab_l"]) == {"elbow", "sjc_sphere"}
    assert set(z["forearm"]["slab_l"]) == {"elbow", "wrist"} and set(z["hand"]["slab_l"]) == {"wrist"}


def test_nodes_sit_where_the_ruler_chords_put_them_near_the_skin(res):
    nd = res["registration"]["node_skin_distance"]
    assert nd["upper_arm"]["proximal_node_skin_distance_mm"] > 20                                          # the SJC is deep inside
    assert 0 < nd["upper_arm"]["distal_node_skin_distance_mm"] < 8                                         # the elbow: a chord end vertex, 4 mm inside the lateral skin
    assert abs(nd["forearm"]["distal_node_skin_distance_mm"]) < 2                                          # the wrist: on the skin


def test_the_closure_has_no_remainder_the_arms_included_and_the_shares_sum_to_one(res):
    c = res["closure"]
    assert c["remainder_l"] == {} and c["within_tolerance"] and abs(c["relative_difference"]) <= 0.005
    assert c["sum_l"] == pytest.approx(sum(c["built_l"].values()))
    assert sum(c["shares"].values()) == pytest.approx(1.0)
    for k in ("upper_arms", "forearms", "hands"):
        assert k in c["built_l"]
    assert abs(c["arms_built_minus_raster_l"]) / c["arms_and_girdles_raster_l"] < 0.01
    t = json.loads((ENV / "trunk_bodies.json").read_text())
    assert t["closure"]["sum_l"] == pytest.approx(c["sum_l"]) and t["share_table"] == res["share_table"]


def test_the_share_table_has_the_briefs_roles_and_the_sum_of_conformed_volumes_as_denominator(res):
    s = res["share_table"]
    rows = s["rows"]
    assert {k for k, v in rows.items() if v["role"] == "result"} == {"head_neck", "thorax", "forearms", "hands", "whole_arms", "lumped_abdomen_to_thigh", "shanks", "feet"}
    assert {k for k, v in rows.items() if v["role"] == "diagnostic"} == {"upper_arms", "abdomen", "pelvis", "thighs"}
    assert s["denominator_l"] == pytest.approx(res["closure"]["sum_l"])
    for k, v in rows.items():
        assert v["volume_share"] == pytest.approx(v["volume_l"] / s["denominator_l"]) and v["raw_ratio"] == pytest.approx(v["mass_share"] / v["volume_share"])
        assert v["required_density_kg_per_l"] == pytest.approx(v["sheet_mass_kg"] / v["volume_l"])
    assert rows["whole_arms"]["volume_l"] == pytest.approx(rows["upper_arms"]["volume_l"] + rows["forearms"]["volume_l"] + rows["hands"]["volume_l"])
    assert rows["lumped_abdomen_to_thigh"]["volume_l"] == pytest.approx(rows["abdomen"]["volume_l"] + rows["pelvis"]["volume_l"] + rows["thighs"]["volume_l"])


def test_the_left_arm_is_built_the_same_way_and_the_difference_is_reported(res):
    lr = res["left_right"]
    assert set(lr["bodies"]) == set(NAMES)
    assert all(abs(v["left_minus_right_percent"]) < 3 for v in lr["bodies"].values())
    assert set(lr["left_stretch"]) == {"upper_arm", "forearm"} and all(1.0 < v < 1.2 for v in lr["left_stretch"].values())         # the left's nodes come from the Ruler lists directly
    assert set(lr["raster_girdle_l"]) == {"right", "left", "left_minus_right_percent"}


@pytest.mark.parametrize("name", NAMES)
def test_the_ledger_matches_the_result_and_the_csv_has_a_row_every_10_mm(res, name):
    h = yaml.safe_load((ENV / f"{arms.SEG_KEY[name]}.yaml").read_text().split("\n", 1)[1])
    d = res["design"][name]
    assert h["skin_volume_l"] == pytest.approx(d["skin_volume_l"], abs=1e-4) and h["segment"] == arms.SEG_KEY[name]
    assert h["stretch"] == pytest.approx(d["axial_stretch"], abs=1e-4)
    rows = list(csv.DictReader(l for l in (ENV / f"{arms.SEG_KEY[name]}_sections.csv").read_text().splitlines() if not l.startswith("#")))
    s = [float(r["s_mm"]) for r in rows]
    assert s[0] == 0.0 and all(abs((b - a) - 10.0) < 1e-6 for a, b in zip(s[:-2], s[1:-1])) and s[-1] == pytest.approx(h["length_mm"], abs=0.05)         # the csv rounds stations to 0.1 mm
    for ext in ("sagittal", "coronal"):
        assert (ENV / f"{arms.SEG_KEY[name]}_{ext}.png").stat().st_size > 5000


@built
def test_the_upper_arm_reaches_above_the_sjc_by_the_girdle_and_the_arm_frames_need_no_offset():
    ua = field.Segment.load(CACHE / "upper_arm_R.npz")
    assert ua.z_top > 20.0 and ua.length == pytest.approx(ua.z_top + 255.2347, abs=0.01)
    assert ua.meta["joint_station_mm"] == pytest.approx(ua.z_top)
    assert ua.meta["origin_xyz"] == [0.0, 0.0, 0.0]
    fa = field.Segment.load(CACHE / "forearm_R.npz")
    assert fa.meta["origin_xyz"][2] == pytest.approx(-255.2347, abs=1e-3)
    from envelope import frames
    assert frames.segment_offset_mm("upper_arm_R", ua.meta) == (0.0, 0.0, 0.0)


@built
def test_the_cylinder_and_the_box_examples_through_the_cli():
    for ex, seg in (("upper_arm_cylinder", "upper_arm_R"), ("forearm_box", "forearm_R")):
        ok = cli("check", "--segment", seg, "--shapes", str(EX / f"{ex}_shapes.yaml"), "--poses", str(EX / f"{ex}_feasible_poses.csv"))
        no = cli("check", "--segment", seg, "--shapes", str(EX / f"{ex}_shapes.yaml"), "--poses", str(EX / f"{ex}_infeasible_poses.csv"))
        assert ok.returncode == 0 and "FEASIBLE" in ok.stdout and "INFEASIBLE" not in ok.stdout, ok.stdout + ok.stderr
        assert no.returncode == 1 and "INFEASIBLE" in no.stdout


@built
def test_the_union_across_the_elbow_holds_a_rod_neither_body_holds_alone():
    args = ("--shapes", str(EX / "arm_union_shapes.yaml"))
    alone = cli("check", "--segment", "upper_arm_R", *args, "--poses", str(EX / "arm_union_feasible_poses.csv"))
    both = cli("check", "--segment", "upper_arm_R,forearm_R", *args, "--poses", str(EX / "arm_union_feasible_poses.csv"))
    bad = cli("check", "--segment", "upper_arm_R,forearm_R", *args, "--poses", str(EX / "arm_union_infeasible_poses.csv"))
    assert alone.returncode == 1 and "slab overrun 80.00" in alone.stdout
    assert both.returncode == 0 and "FEASIBLE" in both.stdout and "slab overrun 0.00" in both.stdout, both.stdout
    assert bad.returncode == 1
