"""Volume-extractor brief 6, item 10: MakeHuman's base.obj carries helper geometry after the body's 13,380 vertices. Reading it gives the body only unless a caller opts in, and every result
computed from base.obj is the same with and without the helper vertices."""
import json
import sys
from pathlib import Path

import numpy as np
import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "tools"))

import analysis.makehuman_attribution as A  # noqa: E402
import analysis.makehuman_v2 as M  # noqa: E402
from envelope import meshio  # noqa: E402

BASE = REPO / "data" / "makehuman" / "base.obj"
RULER = REPO / "data" / "makehuman" / "ruler_measures.json"


def test_read_obj_vertices_returns_the_body_only_unless_the_caller_opts_in():
    body = A.read_obj_vertices(BASE)
    full = A.read_obj_vertices(BASE, include_helpers=True)
    assert body.shape == (meshio.BODY_VERTICES, 3) and full.shape[0] > meshio.BODY_VERTICES
    assert np.array_equal(full[: meshio.BODY_VERTICES], body)


def test_the_committed_exports_have_no_helper_vertices_so_reading_them_is_unchanged():
    for name in ("freyja-body-v1.obj", "freyja-body-v2.obj"):
        assert A.read_obj_vertices(REPO / "data" / "makehuman" / name).shape[0] == meshio.BODY_VERTICES


def test_base_obj_results_are_identical_with_and_without_the_helper_vertices():
    body = A.read_obj_vertices(BASE)
    full = A.read_obj_vertices(BASE, include_helpers=True)
    measures = json.loads(RULER.read_text())["measures"]
    assert max(max(ids) for ids in measures.values()) < meshio.BODY_VERTICES              # every Ruler chain and loop is made of body vertices
    chords = {"upper": measures["measure/measure-upperleg-height-decr|incr"], "lower": measures["measure/measure-lowerleg-height-decr|incr"]}
    assert A.knee_metrics(body, chords) == A.knee_metrics(full, chords)
    assert M.readouts(body, measures) == M.readouts(full, measures)
    assert M.loop_heights_mm(body, measures) == M.loop_heights_mm(full, measures)
    assert M.height_cm(body) == M.height_cm(full)
    assert body.tobytes() == full[: meshio.BODY_VERTICES].tobytes()


def test_the_topology_check_compares_the_body_faces_only():
    assert meshio.topology_difference(BASE.parent / "freyja-body-v2.obj", BASE) is None


def test_the_callers_that_read_base_obj_ask_for_the_helpers_explicitly():
    import re
    seen = 0
    for path in ("analysis/makehuman_attribution.py", "analysis/makehuman_v2.py", "analysis/makehuman_v2_check.py"):
        for args in re.findall(r"read_obj_vertices\(([^)]*)\)", (REPO / path).read_text(encoding="utf-8")):
            if "base" in args and not args.startswith("path"):
                seen += 1
                assert "include_helpers=True" in args, f"{path}: read_obj_vertices({args})"
    assert seen == 3
