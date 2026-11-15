"""
The characterization geometry (docs/briefs/ariadne/upper-arm-characterization-brief.md, T6; gates G-G1 to G-G7) on the real repository: tools/characterization
reads every value through tools/thread's address resolution and computes the frames, bars, tilt bound, interface sections with ray labels, the room at
the elbow node, the ROM and the volume.

    python -m pytest tests/test_characterization_geometry.py
"""
import csv
import math
import sys
from pathlib import Path

import numpy as np
import pytest
import yaml

REPO = Path(__file__).resolve().parents[1]
for _p in (str(REPO / "tools"),):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from characterization import cli, geometry  # noqa: E402
from characterization.reader import CharacterizationError, Reader  # noqa: E402
from envelope import registry  # noqa: E402

LEDGER = REPO / "data" / "envelope" / "upper_arm_R.yaml"
CSV = REPO / "data" / "envelope" / "upper_arm_R_sections.csv"
SNAP = {r["placeholder"]: r["value"] for r in csv.DictReader(open(REPO / "params" / "snapshot.csv", encoding="utf-8"))}
L_MM = 1000 * float(SNAP["upper_arm_right_length"])


@pytest.fixture(scope="module")
def run():
    rd = Reader(REPO)
    g = geometry.geometry(rd, "upper_arm")
    g["consumes"] = rd.consumes
    return g


def csv_rows():
    return {r["s_mm"]: r for r in csv.DictReader(l for l in open(CSV, encoding="utf-8") if not l.startswith("#"))}


# ---- the label and bracket rules ---------------------------------------------------------------------------------------------------------

@pytest.mark.parametrize("text, label", [("34.3", "skin"), ("45.68", "skin"), ("3.0", "cut_plane"), ("0.0", "cut_plane"), ("45.75", "cut_plane"),
                                         ("4.75", "cut_plane"), ("30.01", "skin"), ("0.01", "skin")])
def test_a_ray_is_skin_only_when_its_value_cannot_be_a_step_multiple(text, label):
    assert geometry.ray_label(text) == label


def test_to_cad_is_the_transpose_of_isb_to_segment():
    P = np.array([[1.0, 2.0, 3.0], [-4.0, 5.0, -6.0]])
    assert np.allclose(registry.isb_to_segment(geometry.to_cad(P)), P) and np.allclose(geometry.to_cad(registry.isb_to_segment(P)), P)
    assert np.allclose(geometry.to_cad([[0, 1, 0]]), [[0, 0, -1]])  # the ledger's left is the CAD frame's -z (medial for the right arm)
    assert np.allclose(geometry.to_cad([[0, 0, 1]]), [[0, 1, 0]])   # up is proximal


# ---- G-G1 provenance ---------------------------------------------------------------------------------------------------------------------

def test_gg1_both_ledgers_name_the_v3_mesh(run):
    prov = run["report"]["provenance"]
    assert set(prov) == {"upper_arm_R", "forearm_R"}
    assert all(v["mesh_file"] == "data/makehuman/freyja-body-v3.obj" for v in prov.values())
    assert all(len(v["inputs_sha256_12"]) == 12 for v in prov.values())


# ---- G-G2 frames -------------------------------------------------------------------------------------------------------------------------

def test_gg2_frames(run):
    fc = run["report"]["frame_checks"]
    assert fc["orthonormal_error"] <= 1e-9 and abs(fc["determinant"] - 1.0) <= 1e-9 and fc["axes_shared"]
    assert abs(fc["distal_distance_mm"] - L_MM) <= 0.1
    assert fc["distal_direction"] == [0.0, -1.0, 0.0]
    assert abs(fc["ledger_length_less_joint_station_mm"] - L_MM) <= 0.1 and abs(fc["ledger_mesh_length_mm"] - L_MM) <= 0.1
    ifs = run["part"]["interfaces"]
    assert ifs["shoulder"]["frame"]["axes"] == ifs["elbow"]["frame"]["axes"] == [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]]
    assert run["part"]["frame"]["origin"] == "shoulder" and ifs["shoulder"]["frame"]["origin"]["mm"] == [0.0, 0.0, 0.0]


# ---- G-G3 bars -------------------------------------------------------------------------------------------------------------------------

def test_gg3_bars_and_the_tilt_bound(run):
    a = run["part"]["anchors"]
    assert a["elbow"]["position"]["bar"]["value_mm"] == 7 and a["elbow"]["position"]["bar"]["direction"] == "anteroposterior"
    assert a["wrist"]["position"]["bar"]["value_mm"] == 5
    assert a["shoulder"]["position"]["bar"]["value_mm"] == "unstated"
    t = run["part"]["axis_tilt_bound"]["value_deg"]
    assert abs(t - math.degrees(math.atan(7 / L_MM))) < 1e-6 and abs(t - 1.6) <= 0.05


def test_the_wrist_is_the_two_sheet_lengths_below_the_shoulder_at_the_zero_pose(run):
    w = run["part"]["anchors"]["wrist"]["position"]["mm"]
    assert np.allclose(w, [0, -(L_MM + 1000 * float(SNAP["forearm_right_length"])), 0], atol=1e-6)


# ---- G-G4 interface sections -----------------------------------------------------------------------------------------------------------

def test_gg4_each_interface_carries_its_two_bracketing_rows_uninterpolated(run):
    ifs, rows = run["part"]["interfaces"], csv_rows()
    sh, el = ifs["shoulder"], ifs["elbow"]
    assert sh["joint_station_mm"] == yaml.safe_load(LEDGER.read_text(encoding="utf-8"))["stations"]["joint_station_mm"] == 36.0
    assert [x["station_mm"] for x in sh["sections"]] == [30.0, 40.0]
    assert [x["offset_from_joint_mm"] for x in sh["sections"]] == [6.0, -4.0]
    assert [x["station_mm"] for x in el["sections"]] == [290.0, 291.2]
    assert abs(el["joint_station_mm"] - (36.0 + L_MM)) < 1e-6
    for i in (sh, el):
        for x in i["sections"]:
            r = rows[f"{x['station_mm']:.1f}"]
            assert {**x["values"], **{k: v["mm"] for k, v in x["rays"].items()}} == {k: float(v) for k, v in r.items() if k != "s_mm"}  # unchanged in value


def test_gg4_every_ray_is_labelled_and_the_shoulder_s_first_lateral_skin_ray_is_station_40(run):
    sh = run["part"]["interfaces"]["shoulder"]["sections"]
    for i in run["part"]["interfaces"].values():
        for x in i["sections"]:
            assert len(x["rays"]) == 12 and all(v["label"] in ("skin", "cut_plane") for v in x["rays"].values())
    first = next(r for r in run["part"]["volume"]["stations"] if r["rays"]["hw_lat_mm"]["label"] == "skin")
    assert first["station_mm"] == 40.0 and sh[1]["rays"]["hw_lat_mm"] == {"mm": 34.3, "label": "skin"}
    assert abs(first["rays"]["hw_lat_mm"]["mm"] - 34.30) <= 0.01


def test_no_ray_labelled_skin_is_a_step_multiple(run):
    """The rule's one-sidedness: a cut-plane ray (field.py:271-272 returns a step multiple) is never labelled skin."""
    for r in run["part"]["volume"]["stations"]:
        for v in r["rays"].values():
            if v["label"] == "skin":
                assert abs(v["mm"] * 4 - round(v["mm"] * 4)) > 1e-9


# ---- G-G5 elbow room ---------------------------------------------------------------------------------------------------------------------

def test_gg5_the_room_around_the_elbow_node(run):
    d = run["report"]["distal_room"]
    assert d["station_mm"] == 270.0
    assert len(d["r_mm"]) == 8 and all(v > 0 for v in d["r_mm"].values())
    assert len(d["hw_mm"]) == 4 and all(v > 0 for v in d["hw_mm"].values())
    rows = csv_rows()
    assert all(not all(geometry.ray_label(rows[s][k]) == "skin" for k in rows[s] if k.startswith(("hw_", "r_"))) for s in ("280.0", "290.0", "291.2"))


# ---- G-G6 ROM ----------------------------------------------------------------------------------------------------------------------------

def test_gg6_rom(run):
    rom = run["part"]["rom"]
    assert rom["anatomical"]["min_deg"] == -float(SNAP["elbow_extension"]) and rom["anatomical"]["max_deg"] == float(SNAP["elbow_flexion"])
    assert rom["mechanism"]["min_deg"] == -float(SNAP["elbow_extension"]) and rom["mechanism"]["max_deg"] == 157.0
    assert rom["sign"].startswith("flexion positive, extension negative")
    assert rom["loaded_arc"] == {"min_deg": None, "max_deg": None, "basis": rom["loaded_arc"]["basis"], "source_needed": True}


# ---- G-G7 volume -------------------------------------------------------------------------------------------------------------------------

def test_gg7_volume_is_read_not_recomputed(run):
    v = run["part"]["volume"]
    led = yaml.safe_load(LEDGER.read_text(encoding="utf-8"))
    assert v["shell_mm"] == 5.0 and v["inner_volume_l"] == led["inner_volume_l"]["t5"]
    rows = csv_rows()
    assert [r["station_mm"] for r in v["stations"]] == [float(s) for s in rows]
    for r in v["stations"]:
        assert r["y_mm"] == pytest.approx(36.0 - r["station_mm"], abs=1e-9)


# ---- addresses, the schema fragment, the CLI ----------------------------------------------------------------------------------------------

def test_everything_is_read_by_address_and_nothing_under_catalog(run):
    c = run["consumes"]
    assert "data/envelope/upper_arm_R_sections.csv#" in c and "snapshot#/upper_arm_right_length" in c
    assert "data/envelope/upper_arm_R.yaml#/inner_volume_l/t5" in c and any(a.startswith("data/characterization/inputs/upper_arm.yaml#") for a in c)
    assert not any(a.startswith("catalog/") for a in c)


def test_the_parts_validate_against_the_schema(run):
    import json
    import jsonschema
    schema = json.loads((REPO / "docs" / "schemas" / "segment-characterization-1.schema.json").read_text(encoding="utf-8"))
    defs = schema["$defs"]
    for key in ("frame", "anchors", "axis_tilt_bound", "interfaces", "volume"):
        sub = {**schema["properties"][key], "$defs": defs}
        assert list(jsonschema.Draft202012Validator(sub).iter_errors(json.loads(json.dumps(run["part"][key])))) == [], key
    rom = {k: v for k, v in schema["properties"]["rom"]["properties"].items() if k != "flexion_clearance"}
    for k, s in rom.items():
        assert list(jsonschema.Draft202012Validator({**s, "$defs": defs}).iter_errors(run["part"]["rom"][k])) == [], k


def test_a_missing_input_fails_naming_the_address(tmp_path):
    import shutil
    from thread import build
    root = tmp_path / "r"
    for d in ("thread", "params", "sim/models", "decisions", "checks", "data/envelope", "data/characterization", "docs/schemas", "requirements", "cad/sidecars", "roadmap"):
        if (REPO / d).is_dir():
            shutil.copytree(REPO / d, root / d, ignore=shutil.ignore_patterns("cache", "*.png", "*.npz"))
    p = root / "data" / "characterization" / "inputs" / "upper_arm.yaml"
    doc = yaml.safe_load(p.read_text(encoding="utf-8"))
    del doc["shell"]
    p.write_text(yaml.safe_dump(doc), encoding="utf-8")
    with pytest.raises(CharacterizationError, match=r"inputs/upper_arm\.yaml#/shell"):
        geometry.geometry(Reader(root, build.build_root(root)), "upper_arm")


def test_the_dry_run_prints_a_summary_and_writes_nothing(capsys):
    lines = []
    assert cli.main(["upper_arm", "--dry-run"], default_root=REPO, say=lines.append) == 0
    text = "\n".join(lines)
    assert "seg.upper_arm" in text and "unstated" in text and "0.8346" in text and "station 36.0" in text
    assert len(lines) < 30 and all(len(ln) < 300 for ln in lines)
    assert cli.main(["upper_arm"], default_root=REPO, say=lines.append) == 2
