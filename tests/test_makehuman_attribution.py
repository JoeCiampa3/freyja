"""analysis/makehuman_attribution.py: the weights follow MakeHuman's own rules (human.py, humanmodifier.py), checked on hand-computable cases and on a tiny
synthetic target folder. The real run needs MakeHuman's base.obj and targets, which stay outside the repo."""
import sys
from pathlib import Path

import numpy as np
import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "analysis"))

import makehuman_attribution as A  # noqa: E402


def state(**over):
    s = dict(A.MACRO_DEFAULTS)
    s.update(over)
    return s


def test_default_macro_values_are_the_defaults_of_the_human_object():
    v = A.macro_values(state())
    assert v["male"] == v["female"] == 0.5 and v["young"] == 1.0 and v["child"] == v["baby"] == v["old"] == 0.0
    assert v["averagemuscle"] == v["averageweight"] == v["averageheight"] == v["regularproportions"] == 1.0
    assert abs(v["african"] - 1 / 3) < 1e-12 and abs(sum(v[k] for k in ("african", "asian", "caucasian")) - 1) < 1e-12


def test_the_sculpts_macro_values_by_hand():
    s = state(**{"macrodetails/Gender": 0.0, "macrodetails/Age": 0.44, "macrodetails/African": 0.0, "macrodetails/Asian": 0.0, "macrodetails/Caucasian": 1.0,
                 "macrodetails-universal/Muscle": 0.396, "macrodetails-universal/Weight": 0.232, "macrodetails-height/Height": 0.623,
                 "macrodetails-proportions/BodyProportions": 0.546})
    v = A.macro_values(s)
    assert v["female"] == 1.0 and v["male"] == 0.0 and v["caucasian"] == 1.0
    assert v["young"] == pytest.approx((0.44 - 0.1875) * 3.2) and v["child"] == pytest.approx(1 - v["young"], abs=2e-3) and v["baby"] == 0.0
    assert v["minweight"] == pytest.approx(1 - 0.464) and v["averageweight"] == pytest.approx(0.464)
    assert v["maxheight"] == pytest.approx(0.246) and v["averageheight"] == pytest.approx(0.754)
    assert v["idealproportions"] == pytest.approx(0.092) and v["regularproportions"] == pytest.approx(0.908)
    assert v["minmuscle"] == pytest.approx(1 - 0.792) and v["averagemuscle"] == pytest.approx(0.792)


def test_target_names_split_into_variables_and_group():
    var, key = A.parse_target("macrodetails/height/female-young-averagemuscle-averageweight-maxheight.target")
    assert var == ["female", "young", "averagemuscle", "averageweight", "maxheight"] and key == ["macrodetails", "height"]
    var, key = A.parse_target("pelvis/bulge-decr.target")
    assert var == [] and key == ["pelvis", "bulge", "decr"]


def test_macro_target_weight_is_the_product_of_its_variables_and_universal_modifiers_use_the_sign():
    files = ["macrodetails/caucasian-female-young.target", "macrodetails/caucasian-male-young.target", "pelvis/bulge-decr.target", "pelvis/bulge-incr.target",
             "bodyshapes/bodyshapes-elvs-fem-neat-hourglass.target"]
    s = state(**{"macrodetails/Gender": 0.25, "macrodetails/African": 0.0, "macrodetails/Asian": 0.0, "macrodetails/Caucasian": 1.0,
                 "pelvis/bulge-decr|incr": -0.5, "bodyshapes/bodyshapes-elvs-fem-neat-hourglass": 0.3})
    w = A.target_weights(files, s, A.macro_values(s))
    assert w["macrodetails/caucasian-female-young.target"] == pytest.approx(0.75) and w["macrodetails/caucasian-male-young.target"] == pytest.approx(0.25)
    assert w["pelvis/bulge-decr.target"] == pytest.approx(0.5) and "pelvis/bulge-incr.target" not in w
    assert w["bodyshapes/bodyshapes-elvs-fem-neat-hourglass.target"] == pytest.approx(0.3)


def test_a_modifier_with_no_target_file_is_an_error():
    with pytest.raises(KeyError):
        A.target_weights([], state(**{"pelvis/bulge-decr|incr": 0.5}), A.macro_values(state()))


def test_mesh_is_base_plus_weighted_deltas(tmp_path):
    (tmp_path / "pelvis").mkdir()
    (tmp_path / "pelvis" / "bulge-incr.target").write_text("# c\n1 0.0 1.0 0.0\n2 1.0 0.0 0.0\n")
    base = np.zeros((4, 3))
    (tmp_path / "pelvis" / "bulge-decr.target").write_text("")           # an empty target file is legal
    T = A.Targets(tmp_path)
    V = T.mesh(base, {"pelvis/bulge-decr|incr": 0.5})
    assert np.allclose(V[1], [0, 0.5, 0]) and np.allclose(V[2], [0.5, 0, 0]) and np.allclose(V[0], 0)


def test_solve_finds_the_smallest_root_and_reports_no_root():
    root, span = A.solve(lambda x: x - 0.3, -1.0, 1.0)
    assert root == pytest.approx(0.3, abs=1e-9)
    root, span = A.solve(lambda x: x * x + 1, -1.0, 1.0)
    assert root is None and span[0] >= 1.0


def test_knee_metrics_use_the_lower_chord_end_and_the_upper_chord_end():
    V = np.zeros((13380 + 4, 3))
    V[:13380, 1] = np.linspace(0, 10, 13380)             # 0 to 10 dm: the sole and the top of the head
    chords = {"upper": [13380, 13381], "lower": [13382, 13383]}
    V[13380, 1], V[13381, 1] = 5.0, 3.0                  # upper-leg chord: hip end 5, knee end 3
    V[13382, 1], V[13383, 1] = 3.2, 0.5                  # lower-leg chord: knee end 3.2, ankle end 0.5
    m = A.knee_metrics(V, chords)
    assert m["knee_fraction"] == pytest.approx((3.0 + 3.2) / 2 / 10) and m["stature_mm"] == pytest.approx(1000.0)
    assert m["hip_fraction"] == pytest.approx(0.5)
