"""analysis/makehuman_v3.py (brief 10, 2.2 and 2.3): the v3 writers and the adr-0042 helpers, on synthetic inputs; the pinned targets stay out of the suite (gitignored)."""
import sys
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "analysis"))
sys.path.insert(0, str(ROOT / "tools"))
import makehuman_v3 as v3  # noqa: E402


OBJ = ("# MakeHuman exported OBJ\r\n\r\nmtllib x.mtl\r\nv 1.0000 2.0000 3.0000\r\nv -0.3393 15.8075 1.3169\r\nv 0.0000 0.0000 0.0000\r\n"
       "vt 0.1 0.2\r\ng base.obj\r\nf 1/1 2/1 3/1\r\n").encode("ascii")


def test_obj_changes_only_the_moved_v_lines():
    d = np.zeros((3, 3))
    d[1] = [0.01, 0.0, -0.002]
    out = v3.v3_obj_bytes(OBJ, d, n_body=3)
    a, b = OBJ.split(b"\r\n"), out.split(b"\r\n")
    assert len(a) == len(b) and [i for i, (p, q) in enumerate(zip(a, b)) if p != q] == [4]
    assert b[4] == b"v -0.3293 15.8075 1.3149"


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


@pytest.mark.parametrize("axis", [(0.6, -0.3, -0.74), (0.0, -0.17, -0.98), (-0.2, 0.5, -0.84)])
def test_d4_roll_keeps_the_axis_and_makes_the_projected_anterior_the_frame_x(axis):
    u = np.array(axis) / np.linalg.norm(axis)
    R = v3.rotation_to_down_d4(u)
    assert np.allclose(R @ R.T, np.eye(3)) and np.isclose(np.linalg.det(R), 1.0)
    assert np.allclose(R @ u, [0, 0, -1])
    x = np.array([1.0, 0, 0]) - u[0] * u
    r = R @ (x / np.linalg.norm(x))
    assert np.allclose(r, [1, 0, 0])


def test_solver_closes_a_coupled_linear_system():
    A = np.array([[60.0, 1.0], [-2.0, 55.0]])
    b = np.array([200.0, 210.0])
    w = v3.solve_weights(lambda x: b + A @ x, np.array([228.0, 232.0]), start=(0.3, 0.3))
    assert np.abs(b + A @ w - [228.0, 232.0]).max() < 1e-6
