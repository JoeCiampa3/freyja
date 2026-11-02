"""analysis/fall_room.py (fall inputs brief, T1): the room at each zone's contact and the lowest fitting first cap."""
import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("fall_room", ROOT / "analysis" / "fall_room.py")
fr = importlib.util.module_from_spec(SPEC)
sys.modules["fall_room"] = fr
SPEC.loader.exec_module(fr)

STROKES = {10: 113, 20: 57, 40: 29}


def test_lowest_cap_takes_the_lowest_force_whose_stroke_fits():
    assert fr.lowest_cap(113.0, STROKES) == 10
    assert fr.lowest_cap(112.9, STROKES) == 20
    assert fr.lowest_cap(57.0, STROKES) == 20
    assert fr.lowest_cap(29.0, STROKES) == 40
    assert fr.lowest_cap(28.9, STROKES) is None


def test_ray_hits_a_vertical_cylinder_at_its_near_face():
    cyl = {"cx": 0.0, "cy": -80.0, "r": 45.0, "s_top": 0.0, "s_bottom": 100.0, "clearance": 5.0}
    # along +y from the skin at y = -160, through the axis: the near face is at y = -125
    assert fr.ray_to_cylinder((0.0, -160.0), (0.0, 1.0), 50.0, cyl) == pytest.approx(35.0)
    # offset 27 of 45: half chord 36
    assert fr.ray_to_cylinder((27.0, -160.0), (0.0, 1.0), 50.0, cyl) == pytest.approx(160.0 - 80.0 - 36.0)


def test_ray_misses_a_cylinder_it_passes_beside_or_below():
    cyl = {"cx": 0.0, "cy": -80.0, "r": 45.0, "s_top": 0.0, "s_bottom": 100.0, "clearance": 5.0}
    assert fr.ray_to_cylinder((46.0, -160.0), (0.0, 1.0), 50.0, cyl) is None
    assert fr.ray_to_cylinder((0.0, -160.0), (0.0, 1.0), 106.0, cyl) is None


def test_the_clearance_extends_a_cylinder_axially():
    cyl = {"cx": 0.0, "cy": -80.0, "r": 45.0, "s_top": 0.0, "s_bottom": 100.0, "clearance": 5.0}
    assert fr.ray_to_cylinder((0.0, -160.0), (0.0, 1.0), 104.0, cyl) == pytest.approx(35.0)


def test_gap_is_the_room_beside_a_ray_that_misses():
    cyl = {"id": "m", "cx": 0.0, "cy": -80.0, "r": 45.0, "s_top": 0.0, "s_bottom": 100.0, "clearance": 5.0}
    assert fr.side_gap((60.0, -160.0), (0.0, 1.0), 50.0, [cyl]) == {"occupant": "m", "gap_mm": 10.0}
    assert fr.side_gap((0.0, -160.0), (0.0, 1.0), 50.0, [cyl]) is None
    assert fr.side_gap((60.0, -160.0), (0.0, 1.0), 200.0, [cyl]) is None


def test_a_file_from_another_mesh_is_reported_and_not_used():
    assert fr.usable({"mesh_file": fr.BASELINE_MESH}) is True
    assert fr.usable({"mesh_file": "data/makehuman/freyja-body-v2.obj"}) is False
    assert fr.usable({}) is False


def test_a_ledger_built_from_another_mesh_stops_the_room(tmp_path):
    (tmp_path / "pelvis.yaml").write_text("mesh_file: data/makehuman/freyja-body-v2.obj\ninputs_sha256_12: abc\n", encoding="utf-8")
    (tmp_path / "pelvis_sections.csv").write_text("# banner\ns_mm,hw_right_mm\n0.0,100.0\n", encoding="utf-8")
    with pytest.raises(fr.NotBaseline):
        fr.Ledger(tmp_path, "pelvis")


def test_strokes_are_read_from_the_decision_records():
    s = fr.read_strokes(ROOT)
    assert s["hip"] == {10: 113, 20: 57, 40: 29}
    assert s["knee"] == {10: 55, 20: 28, 40: 14}
    assert s["hand_arm"] == {10: 90, 20: 45, 40: 23}


def test_claims_are_read_from_the_decision_record():
    c = fr.read_claims(ROOT)
    assert c["hip"]["kg_per_unit_now"] == 0.40 and c["hip"]["units"] == 2
    assert c["shoulder"]["element_kg"][20] == 0.117
    assert fr.released_kg(c["hip"], 20) == pytest.approx(0.30)
    assert fr.released_kg(c["shoulder"], 40) == pytest.approx(0.0)
    assert fr.released_kg(c["buttock"], None) is None


@pytest.fixture(scope="module")
def outputs():
    return fr.render(fr.build(ROOT)), fr.render(fr.build(ROOT))


def test_g3_two_runs_are_byte_identical(outputs):
    assert outputs[0] == outputs[1]


def test_g3_the_committed_output_is_a_fresh_build(outputs):
    assert (ROOT / fr.OUT).read_text(encoding="utf-8") == outputs[0]


def test_g3_the_script_refuses_any_argument():
    r = subprocess.run([sys.executable, str(ROOT / "analysis" / "fall_room.py"), "--out", "x"], capture_output=True, cwd=ROOT)
    assert r.returncode == 2


def test_g3_the_output_records_its_arguments_and_no_path_of_this_machine(outputs):
    assert json.loads(outputs[0])["arguments"] == {}
    assert str(ROOT).replace("\\", "/") not in outputs[0].replace("\\\\", "/")


def test_g1_every_room_number_names_its_file_mesh_hash_and_shell(outputs):
    d = json.loads(outputs[0])
    for name, z in d["zones"].items():
        for src in z.get("sources", []):
            assert src["mesh_file"] == fr.BASELINE_MESH, name
            assert len(src["inputs_sha256_12"]) == 12, name
            assert src["file"] and src["column"] and src["shell_mm"] == 5.0, name


def test_g4_every_zone_has_an_outcome(outputs):
    d = json.loads(outputs[0])
    assert set(d["zones"]) == {"hip", "shoulder", "buttock", "back", "knee", "hand_arm"}
    for name, z in d["zones"].items():
        assert z["outcome"] in ("answered", "cannot be answered"), name
        if z["outcome"] == "answered":
            assert "reading_a" in z and "reading_b" in z, name
            assert set(z["station"]) >= {"vertex", "segment", "section_station_mm", "frame", "point_mm"}, name
        else:
            assert z["reason"], name


def test_the_spine_registries_belong_to_the_ledgers_they_are_read_with(outputs):
    d = json.loads(outputs[0])
    assert all(v["ties"] for v in d["registry_ties"].values())
