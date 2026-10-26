"""analysis/makehuman_v2_check.py: the committed result of the v2 checks (volume-extractor brief 4, items 1, 2, 9) says what the brief needs it to say, and the
helpers do what they claim. The rebuild itself needs the MakeHuman target cache (gitignored), so the tests read the committed `data/envelope/v2_check.json`."""
import json
import sys
from pathlib import Path

import numpy as np
import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "analysis"))
sys.path.insert(0, str(REPO / "tools"))

import makehuman_v2_check as C  # noqa: E402

RESULT = REPO / "data/envelope/v2_check.json"


@pytest.fixture(scope="module")
def res():
    return json.loads(RESULT.read_text())


def test_gate1_v2_matches_the_rebuild_in_every_region_and_the_topology_is_base(res):
    assert res["topology_v2_vs_base"] == "identical"
    g = res["gate1_v2_vs_rebuild"]
    assert g["whole_body"]["vertices"] == 13380 and g["whole_body"]["max_mm"] < g["flag_mm"] < g["stop_mm"]
    assert set(g["regions"]) == {"legs", "torso", "arms", "head"}
    assert sum(r["vertices"] for r in g["regions"].values()) == 13380
    assert all(r["max_mm"] < g["flag_mm"] and r["over_flag"] == 0 for r in g["regions"].values())


def test_v2_volume_matches_joes_blender_volume_within_the_gate(res):
    g = res["gate6_v2"]
    assert g["blender_l"] == pytest.approx(52.3331) and abs(g["relative_difference"]) < g["tolerance"]


def test_the_volume_change_is_split_into_pose_and_slider_effects_that_add_up(res):
    d = res["decomposition_l"]
    e = d["exact"]
    assert e["pose"] + e["slider"] == pytest.approx(e["total"], abs=1e-9)
    assert e["height_only"] + e["leg_measures_only"] == pytest.approx(e["slider"], abs=0.02)         # the two slider groups nearly add (their cross term is small)
    assert abs(d["unexplained_l"]) < d["unexplained_stop_l"]
    assert set(d["pose_effect (v1 posed -> v1 rest)"]) == {"feet", "shanks", "thighs", "abdomen_pelvis", "trunk_above_rib", "head", "arms"}
    # the legs are not moved by the pose, the lower leg is the only region the sliders shorten
    assert abs(d["pose_effect (v1 posed -> v1 rest)"]["shanks"]) < 0.01 and abs(d["pose_effect (v1 posed -> v1 rest)"]["feet"]) < 0.01
    assert d["slider_effect (v1 rest -> v2)"]["shanks"] < 0 < d["slider_effect (v1 rest -> v2)"]["thighs"]


def test_ruler_readouts_of_the_exported_v2_match_the_prediction_to_the_makehuman_display_precision(res):
    worst = max(abs(v["difference"]) for v in res["ruler_readouts_cm"].values())
    assert worst < 0.05                                                                    # MakeHuman shows 0.1 cm
    for k, v in res["girth_loops"].items():
        assert abs(v["v2_obj"]["z_mm"] - v["predicted"]["z_mm"]) < 0.05 and abs(v["v2_obj"]["tilt_deg"] - v["predicted"]["tilt_deg"]) < 0.05


def test_nothing_in_the_result_is_a_path_or_a_timestamp(res):
    text = RESULT.read_text()
    assert ":\\" not in text and "/Users/" not in text and "T00:" not in text


def test_write_obj_round_trips_through_the_loader(tmp_path):
    from envelope import meshio
    V = np.array([[0.0, 0.0, 0.0], [1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]])
    polys = [(0, 2, 1), (0, 1, 3), (1, 2, 3), (0, 3, 2)]
    C.write_obj(tmp_path / "t.obj", V, polys)
    v, p = meshio.read_obj(tmp_path / "t.obj")
    assert np.allclose(v, V) and [tuple(q) for q in p] == polys
