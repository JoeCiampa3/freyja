"""Volume-extractor brief 5, items 2 to 8: the committed result of `fy envelope gates` for the trunk bodies (`data/envelope/trunk_bodies.json`, the gates in `leg_R_trial.json`),
the section ledgers, and the worked examples through `fy envelope check`. The result is read, not rebuilt (the build takes minutes); the code that makes it is tested on synthetic bodies
in test_envelope_bodies.py."""
import csv
import json
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "tools"))

from envelope import bodies, ledger, trunk  # noqa: E402

ENV = REPO / "data" / "envelope"
CACHE = ENV / "cache"
NAMES = ("pelvis", "abdomen", "thorax", "head_neck")


@pytest.fixture(scope="module")
def res():
    return json.loads((ENV / "trunk_bodies.json").read_text())


@pytest.fixture(scope="module")
def trial_json():
    return json.loads((ENV / "leg_R_trial.json").read_text())


def test_every_gate_of_the_trial_passes_including_the_trunk_ones(trial_json):
    gates = trial_json["gates"]
    assert all(g["pass"] for g in gates)
    names = " | ".join(g["gate"] for g in gates)
    for body in NAMES:
        assert f"1 {body}: topology matches base; surface watertight" in names and f"3 {body}: matched-station areas within 1%" in names
    for want in ("2 trunk: |stretch-1| < 8%", "7 closure", "5 oracle example pelvis_box", "5 oracle example thorax_box", "5 oracle union query trunk_union", "4 oracle reproduces", "6 mesh volume matches"):
        assert want in names


def test_the_registration_is_the_decided_one(res):
    assert res["cjc_anchor"] == "ansur_cervicale" and res["map"] == "slope1"
    reg = json.loads((ENV / "trunk_registration.json").read_text())
    assert reg["primary_candidate"] == res["cjc_anchor"]
    st = reg["candidates"]["ansur_cervicale"]["modes"]["slope1"]["stretch"]
    assert all(abs(v - 1.0) < 0.08 for v in st.values())
    assert st["head_neck"] == pytest.approx(265.738185 / (1698.95 - res["mesh_nodes_mm"]["cjc"]), rel=1e-4)       # the head and neck keeps the sheet's length
    assert res["sheet_nodes_mm"]["vertex"] - res["sheet_nodes_mm"]["cjc"] == pytest.approx(265.738185, abs=1e-3)


def test_design_numbers_are_the_sheet_mass_over_the_volumes_and_the_inner_volumes_shrink(res):
    snap = {r["placeholder"]: float(r["value"]) for r in csv.DictReader(open(REPO / "params/snapshot.csv"))}
    for n in NAMES:
        d = res["design"][n]
        assert d["sheet_mass_kg"] == pytest.approx(snap[f"{n}_mass"])
        assert d["required_density_skin_kg_per_l"] == pytest.approx(d["sheet_mass_kg"] / d["skin_volume_l"], rel=1e-9)
        v = [d["skin_volume_l"]] + [d["inner_volume_l"][t] for t in ("t3", "t5", "t8", "t10")]
        assert v == sorted(v, reverse=True)
        for t in ("t3", "t5", "t8", "t10"):
            assert d["required_density_inner_kg_per_l"][t] == pytest.approx(d["sheet_mass_kg"] / d["inner_volume_l"][t], rel=1e-9)
        assert d["min_inscribed_radius"]["r_mm"] > 0 and 0.0 <= d["min_inscribed_radius"]["station_mm"] <= d["length_mm"] + 0.05           # stations are rounded to 0.1 mm in the ledger
        assert d["length_mm"] == pytest.approx(res["sheet_nodes_mm"][bodies.PLANES[n][0]] - res["sheet_nodes_mm"][bodies.PLANES[n][1]], abs=1e-3)
    assert res["design"]["head_neck"]["pinch_stations"][0]["station_mm"] == pytest.approx(170.0)          # the neck
    assert res["design"]["head_neck"]["min_inscribed_radius"]["from_station_mm"] == bodies.FREE_END_MM


def test_the_pair_is_the_sums_and_one_budget(res):
    p, a, b = res["pair_abdomen_pelvis"], res["design"]["abdomen"], res["design"]["pelvis"]
    assert p["skin_volume_l"] == pytest.approx(a["skin_volume_l"] + b["skin_volume_l"]) and p["sheet_mass_kg"] == pytest.approx(a["sheet_mass_kg"] + b["sheet_mass_kg"])
    assert p["required_density_skin_kg_per_l"] == pytest.approx(p["sheet_mass_kg"] / p["skin_volume_l"])
    assert p["sheet_mass_kg"] == pytest.approx(12.155)


def test_closure_is_within_half_a_percent_and_the_shares_sum_to_one(res):
    c = res["closure"]
    assert c["within_tolerance"] and abs(c["relative_difference"]) <= 0.005
    assert c["sum_l"] == pytest.approx(sum(c["built_l"].values()) + sum(c["remainder_l"].values()))
    assert sum(c["shares"].values()) == pytest.approx(1.0, abs=1e-12) and c["share_denominator_l"] == c["sum_l"]
    assert set(c["remainder_l"]) == {"arms", "shoulder_R", "shoulder_L"}
    assert abs(c["raster_minus_mesh_l"]) < 0.005                   # the cell accounting itself closes to 0.01%: the rest of the difference is the conform


def test_the_field_and_the_raster_accounting_agree_per_body(res):
    for n, v in res["field_vs_raster_l"].items():
        assert abs(v["field"] - v["raster"]) / v["raster"] < bodies.FIELD_VS_RASTER_TOL
    for n in NAMES:
        assert res["matched_areas"][n]["worst"] < bodies.AREA_TOL


def test_joint_zones_report_each_body_with_and_without_the_slabs(res):
    z = res["zones"]
    assert z["zone_h_mm"] == bodies.ZONE_H_MM == 25.0
    for n in NAMES:
        assert z[n]["without_all_l"] < z[n]["with_zones_l"] and all(v > 0 for v in z[n]["slab_l"].values())
    assert set(z["pelvis"]["slab_l"]) == {"ljc", "hjc"} and set(z["thorax"]["slab_l"]) == {"tjc", "cjc"} and set(z["head_neck"]["slab_l"]) == {"cjc"}
    assert z["thighs"]["slab_l"]["hjc"] > 0
    # the slab either side of a plane is the same thickness of the same section: abdomen below the TJC against thorax above it differ by the stretch only
    raw = res["zone_planes_raw_l"]["tjc"]
    assert raw["above"]["thorax"] / raw["below"]["abdomen"] == pytest.approx(1.0, abs=0.35)


def test_the_shoulder_cut_is_the_vertical_plane_through_the_sjc_with_a_sphere_zone_owned_jointly(res):
    s = res["shoulder"]
    assert s["plane"]["lateral_mm"] == pytest.approx(178.0 * 328.759098448 / 313.0) and s["plane"]["below_cjc_mm"] == pytest.approx(84.0 * 328.759098448 / 313.0)
    assert s["sphere_radius_mm"] == bodies.ZONE_H_MM
    assert s["thorax_with_zone_l"] > s["thorax_without_zone_l"] > 0 and s["thorax_in_spheres_l"] == pytest.approx(s["thorax_with_zone_l"] - s["thorax_without_zone_l"])
    g = s["shoulder_girdle_assigned_to_the_arm_side_l"]
    assert g["right"] > 0 and g["left"] > 0 and abs(g["right"] - g["left"]) / (g["right"] + g["left"]) < 0.1
    for side in ("R", "L"):                                        # a sphere holds thorax-side cells and arm-side (shoulder) cells: jointly owned
        assert s["spheres"][side]["thorax"] > 0 and s["spheres"][side][f"shoulder_{side}"] > 0
    ax = s["axilla"]
    assert ax["merged_below_axilla"] is False and abs(ax["right_minus_left_mm"]) <= 4.0 and ax["level_mm"] == pytest.approx(1296.0)
    assert res["arm_rule_cross_check"]["relative"] == pytest.approx(0.0, abs=0.01)


def test_ledgers_are_the_thigh_schema_every_10_mm_with_trunk_directions():
    thigh_cols = [c for c in next(csv.reader(open(ENV / "thigh_R_sections.csv").readlines()[1:])) if c]
    for n in NAMES:
        text = (ENV / f"{n}_sections.csv").read_text().splitlines()
        assert text[0].startswith("# GENERATED by fy envelope build")
        rows = list(csv.DictReader(text[1:]))
        h = yaml.safe_load((ENV / f"{n}.yaml").read_text())
        s = [float(r["s_mm"]) for r in rows]
        assert s[0] == 0.0 and s[-1] == pytest.approx(h["length_mm"], abs=0.06) and all(abs(b - a - 10.0) < 1e-6 for a, b in zip(s[:-2], s[1:-1]))
        assert {"s_mm", "area_mm2", "perimeter_mm", "cheb_r_mm", "hw_ant_mm", "hw_left_mm", "area_t5_mm2", "cheb_r_t10_mm"} <= set(rows[0])
        assert set(thigh_cols) - {"hw_med_mm", "hw_lat_mm", "r_med_mm", "r_post_med_mm", "r_post_lat_mm", "r_lat_mm", "r_ant_lat_mm", "r_ant_med_mm"} <= set(rows[0])
        assert h["segment"] == n and h["cjc_anchor"] == "ansur_cervicale" and h["checks"]["boundary_edges_near_segment"] == 0 and h["inputs_sha256_12"]
        for view in ("sagittal", "coronal"):
            assert (ENV / f"{n}_{view}.png").exists()
        for f in (ENV / f"{n}.yaml", ENV / f"{n}_sections.csv"):
            t = f.read_text()
            assert "\r" not in t and "C:\\" not in t and "/Users/" not in t


def run_cli(*args):
    return subprocess.run([sys.executable, str(REPO / "tools" / "fy"), "envelope", *args], capture_output=True, text=True, cwd=REPO)


@pytest.mark.skipif(not (CACHE / "thorax.npz").exists(), reason="the built segments are a gitignored cache (fy envelope build)")
def test_the_box_examples_and_the_union_query_through_the_cli():
    ex = ENV / "examples"
    for body, name in (("pelvis", "pelvis_box"), ("thorax", "thorax_box")):
        ok = run_cli("check", "--segment", body, "--shapes", str(ex / f"{name}_shapes.yaml"), "--poses", str(ex / f"{name}_feasible_poses.csv"))
        bad = run_cli("check", "--segment", body, "--shapes", str(ex / f"{name}_shapes.yaml"), "--poses", str(ex / f"{name}_infeasible_poses.csv"))
        assert ok.returncode == 0 and "FEASIBLE" in ok.stdout and bad.returncode == 1 and "INFEASIBLE" in bad.stdout
    u = ("check", "--segment", "pelvis,abdomen", "--shapes", str(ex / "trunk_union_shapes.yaml"))
    assert run_cli(*u, "--poses", str(ex / "trunk_union_feasible_poses.csv")).returncode == 0
    assert run_cli(*u, "--poses", str(ex / "trunk_union_infeasible_poses.csv")).returncode == 1
    alone = run_cli("check", "--segment", "pelvis", "--shapes", str(ex / "trunk_union_shapes.yaml"), "--poses", str(ex / "trunk_union_feasible_poses.csv"))
    assert alone.returncode == 1                                    # the rod across the plane does not fit the pelvis alone: that is what the union is for


def test_the_union_needs_built_bodies_and_says_so(tmp_path):
    ex = ENV / "examples"
    r = run_cli("check", "--segment", "pelvis,abdomen", "--shapes", str(ex / "trunk_union_shapes.yaml"), "--poses", str(ex / "trunk_union_feasible_poses.csv"), "--cache-dir", str(tmp_path))
    assert r.returncode == 2 and "fy envelope build" in r.stderr
