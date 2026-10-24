"""Volume-extractor brief 1, Phase A: landmarks.json schema, OBJ reading, topology check, frame map."""
import json
import sys
from pathlib import Path

import numpy as np
import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "tools"))

from envelope import landmarks, meshio  # noqa: E402

OBJ = REPO / "data" / "makehuman" / "freyja-body-v1.obj"
REF = REPO / "data" / "mesh" / "freyja-body-v1.obj"


def good():
    return {"schema": "landmarks/1", "topology": 13380,
            "landmarks": {n: {"vertex": i} for i, n in enumerate(landmarks.REQUIRED)}}


def test_required_names_are_the_trial_checklist():
    assert landmarks.REQUIRED == ("ASIS_R", "ASIS_L", "SACRAL_MID", "EPI_MED_R", "EPI_LAT_R")


def test_good_file_validates():
    assert landmarks.validate(good()) == []


@pytest.mark.parametrize("mutate,word", [
    (lambda d: d.update(topology=13381), "topology"),
    (lambda d: d.update(schema="x"), "schema"),
    (lambda d: d["landmarks"].pop("ASIS_L"), "ASIS_L"),
    (lambda d: d["landmarks"]["ASIS_L"].update(vertex=13380), "ASIS_L"),
    (lambda d: d["landmarks"]["ASIS_L"].update(vertex=-1), "ASIS_L"),
    (lambda d: d["landmarks"]["ASIS_L"].update(vertex=1.5), "ASIS_L"),
    (lambda d: d["landmarks"]["ASIS_L"].update(vertex=True), "ASIS_L"),
    (lambda d: d.pop("landmarks"), "landmarks"),
])
def test_bad_files_are_rejected(mutate, word):
    d = good()
    mutate(d)
    problems = landmarks.validate(d)
    assert problems and any(word in p for p in problems)


def test_committed_landmarks_file_validates_when_present():
    p = REPO / "data" / "mesh" / "landmarks.json"
    if not p.exists():
        pytest.skip("no picks committed yet")
    assert landmarks.validate(json.loads(p.read_text())) == []


def test_obj_has_13380_body_vertices_and_the_reference_topology():
    v, polys = meshio.read_obj(OBJ)
    assert v.shape == (13380, 3)
    assert max(max(p) for p in polys) < 13380
    assert meshio.topology_difference(OBJ, REF) is None


def test_topology_difference_names_the_first_difference(tmp_path):
    lines = OBJ.read_text().splitlines()
    k = next(i for i, l in enumerate(lines) if l.startswith("f "))
    parts = lines[k].split()
    parts[1], parts[2] = parts[2], parts[1]
    lines[k] = " ".join(parts)
    bad = tmp_path / "bad.obj"
    bad.write_text("\n".join(lines) + "\n")
    d = meshio.topology_difference(bad, REF)
    assert d is not None and "face 0" in d


def test_vertex_count_mismatch_is_reported(tmp_path):
    bad = tmp_path / "short.obj"
    bad.write_text("v 0 0 0\nv 1 0 0\nv 0 1 0\nf 1 2 3\n")
    assert "vertices" in meshio.topology_difference(bad, REF)


def test_frame_map_is_a_proper_rotation_and_sends_mh_axes_to_the_sheet_frame():
    R = meshio.MH_TO_SHEET
    assert np.isclose(np.linalg.det(R), 1.0)
    assert np.allclose(R @ R.T, np.eye(3))
    # MakeHuman (x left, y up, z anterior) -> sheet (x anterior, y left, z up)
    assert np.allclose(R @ [0, 0, 1], [1, 0, 0])
    assert np.allclose(R @ [1, 0, 0], [0, 1, 0])
    assert np.allclose(R @ [0, 1, 0], [0, 0, 1])


def test_to_sheet_mm_converts_decimeters():
    out = meshio.to_sheet_mm(np.array([[0.1, 0.2, 0.3]]))   # dm, MH axes
    assert np.allclose(out, [[30.0, 10.0, 20.0]])
