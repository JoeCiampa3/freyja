"""analysis/makehuman_v3.py (brief 10): the v3 writers and the export comparison on synthetic inputs, and the committed v3 against them. The pinned targets stay out of the suite (gitignored)."""
import sys
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "analysis"))
sys.path.insert(0, str(ROOT / "tools"))
import makehuman_v3 as v3  # noqa: E402


OBJ = ("# MakeHuman exported OBJ\r\n\r\nmtllib freyja-body-v2.mtl\r\nv 1.0000 2.0000 3.0000\r\nv -0.3393 15.8075 1.3169\r\nv 0.0000 0.0000 0.0000\r\n"
       "vt 0.1 0.2\r\ng base.obj\r\nf 1/1 2/1 3/1\r\n").encode("ascii")


def test_obj_changes_only_the_moved_v_lines_and_the_material_file():
    d = np.zeros((3, 3))
    d[1] = [0.01, 0.0, -0.002]
    out = v3.v3_obj_bytes(OBJ, d, n_body=3)
    a, b = OBJ.split(b"\r\n"), out.split(b"\r\n")
    assert len(a) == len(b) and [i for i, (p, q) in enumerate(zip(a, b)) if p != q] == [2, 4]
    assert b[4] == b"v -0.3293 15.8075 1.3149" and b[2] == b"mtllib freyja-body-v3.mtl"


def test_obj_refuses_a_vertex_count_mismatch():
    with pytest.raises(ValueError):
        v3.v3_obj_bytes(OBJ, np.zeros((4, 3)), n_body=4)


def test_mhm_adds_two_lines_after_the_lower_leg_measure():
    text = "version v\nmodifier measure/measure-lowerleg-height-decr|incr -0.515000\nskeleton x\n"
    out = v3.v3_mhm_text(text, 0.4, 0.43)
    assert out.split("\n") == ["version v", "modifier measure/measure-lowerleg-height-decr|incr -0.515000",
                               "modifier measure/measure-upperarm-length-decr|incr 0.400000", "modifier measure/measure-lowerarm-length-decr|incr 0.430000",
                               "skeleton x", ""]
    assert v3.v3_mhm_text(text, 0.4, None).count("modifier") == 2
    with pytest.raises(ValueError):
        v3.v3_mhm_text("modifier other 1\n", 0.4, 0.43)


def test_verified_target_refuses_a_changed_file(tmp_path):
    p = tmp_path / "measure" / "t.target"
    p.parent.mkdir()
    p.write_text("# c\n0 0.1 0.2 0.3\n2 1 2 3\n")
    man = {"files": {"measure/t.target": {"sha256": v3.fetch.sha256(p.read_bytes()), "size": p.stat().st_size}}}
    D = v3.read_verified_target(man, tmp_path, "measure/t.target", 3)
    assert D.tolist() == [[0.1, 0.2, 0.3], [0, 0, 0], [1, 2, 3]]
    p.write_text("# c\n0 0.1 0.2 0.9\n")
    with pytest.raises(ValueError):
        v3.read_verified_target(man, tmp_path, "measure/t.target", 3)


def test_verified_target_ignores_helper_vertices(tmp_path):
    p = tmp_path / "t.target"
    p.write_text("0 1 1 1\n5 9 9 9\n")
    man = {"files": {"t.target": {"sha256": v3.fetch.sha256(p.read_bytes())}}}
    assert v3.read_verified_target(man, tmp_path, "t.target", 2).tolist() == [[1, 1, 1], [0, 0, 0]]


def test_solver_closes_a_coupled_linear_system():
    A = np.array([[60.0, 1.0], [-2.0, 55.0]])
    b = np.array([200.0, 210.0])
    w = v3.solve_weights(lambda x: b + A @ x, np.array([228.0, 232.0]), start=(0.3, 0.3))
    assert np.abs(b + A @ w - [228.0, 232.0]).max() < 1e-6


def _obj(path, scale=1.0, shift=0.0, jitter=0.0):
    pts = [(0.0, 0.0, 0.0), (10.0, 0.0, 0.0), (0.0, 10.0, 0.0), (0.0, 0.0, 10.0)]
    lines = [f"v {x * scale + shift + jitter * (i == 1):.4f} {y * scale:.4f} {z * scale:.4f}" for i, (x, y, z) in enumerate(pts)]
    path.write_text("\n".join(lines + ["f 1 2 3", "f 1 3 4", "f 1 4 2", "f 2 4 3"]) + "\n")
    return path


def test_the_export_comparison_passes_a_rounding_step_and_names_a_scale_or_offset(tmp_path):
    a = _obj(tmp_path / "a.obj")
    assert v3.compare_export(a, _obj(tmp_path / "b.obj", jitter=0.0001))["pass"]                        # 0.01 mm
    off = v3.compare_export(a, _obj(tmp_path / "c.obj", shift=0.01))
    assert not off["pass"] and off["offset_per_axis_mm"][0] == pytest.approx(1.0)
    sc = v3.compare_export(a, _obj(tmp_path / "d.obj", scale=1.001))
    assert not sc["pass"] and sc["scale_per_axis"][0] == pytest.approx(1.001)


def test_the_export_comparison_refuses_another_topology(tmp_path):
    a, b = _obj(tmp_path / "a.obj"), tmp_path / "b.obj"
    b.write_text(a.read_text().replace("f 2 4 3", "f 2 3 4"))
    assert not v3.compare_export(a, b)["pass"]


def test_the_committed_v3_is_the_scripted_one():
    mh = ROOT / "data/makehuman"
    w = v3.V3_WEIGHTS
    assert (w["upper"], w["lower"]) == (0.381365, 0.512871)
    assert (mh / "freyja-body-v3.mhm").read_text() == v3.v3_mhm_text((mh / "freyja-body-v2.mhm").read_text(), w["upper"], w["lower"])
    assert (mh / "freyja-body-v3.mtl").read_bytes() == (mh / "freyja-body-v2.mtl").read_bytes()
    assert b"mtllib freyja-body-v3.mtl" in (mh / "freyja-body-v3.obj").read_bytes()
    assert v3.meshio.topology_difference(mh / "freyja-body-v3.obj", mh / "base.obj") is None
    if (v3.TARGETS / v3.UPPER_REL).exists():
        import json
        man = json.loads(v3.MANIFEST.read_text(encoding="utf-8"))
        d = sum(w[k] * v3.read_verified_target(man, v3.TARGETS, r, v3.meshio.BODY_VERTICES) for k, r in (("upper", v3.UPPER_REL), ("lower", v3.LOWER_REL)))
        assert (mh / "freyja-body-v3.obj").read_bytes() == v3.v3_obj_bytes((mh / "freyja-body-v2.obj").read_bytes(), d)
