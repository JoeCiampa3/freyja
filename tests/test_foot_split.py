"""
Stage 2g T2: the foot and toe in the preprocessor and the template (decisions/0001 amendment, 0038). The foot box and the toe come from the sheet's `design`
range; the toe is split off the sheet's whole-foot row by conservation. These tests build a fixture model from the committed snapshot plus the design
values of the sheet spec (tests/foot_help.py), never the tracked model.

Run from the repo root:
    python -m pytest tests/test_foot_split.py
"""
import json
import sys
from pathlib import Path

import mujoco
import numpy as np
import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "tests"))

import foot_help as fh  # noqa: E402
import pre_processor as pp  # noqa: E402

CONSERVATION_TOL = 1e-9  # the brief: the toe and the rest reproduce the whole foot's mass, centre of mass and inertia to this (relative for the mass, SI for the others)
ANKLE_M = 0.0627  # the ankle height of the committed snapshot's chain (pelvis + thigh + shank + foot positions)


def design_si(**override):
    d = {**fh.SPEC_DESIGN, **override}
    return {pp.DESIGN_KEYS[k][0]: v * pp.DESIGN_KEYS[k][1] for k, v in d.items()}


def whole_foot(side="right", k=fh.K_ADR0038):
    m, c, I = pp.foot_whole(fh.snapshot_values(), side)
    return m, c * k, I * k * k


def split(side="right", **override):
    d = design_si(**override)
    return pp.foot_split(*whole_foot(side), ankle=ANKLE_M, **{k: d[k] for k in pp.DESIGN_SNAPSHOT_KEYS})


# ---------------------------------------------------------------- conservation

@pytest.mark.parametrize("side", ["right", "left"])
def test_the_toe_and_the_rest_reproduce_the_whole_foot_to_1e_9(side):
    err = pp.foot_conservation_error(whole_foot(side), split(side))
    assert err["mass_rel"] < CONSERVATION_TOL and err["com_m"] < CONSERVATION_TOL and err["inertia"] < CONSERVATION_TOL, err


def test_mutation_a_dropped_parallel_axis_term_or_a_shifted_centre_breaks_conservation():
    """The conservation check must be able to fail: each deliberate error below is far above the 1e-9 limit."""
    whole, good = whole_foot(), split()
    for name, tamper in (
            ("rest inertia without the toe's parallel-axis term", lambda s: s["rest"].update(inertia=s["rest"]["inertia"] + pp.parallel_axis(s["toe"]["mass"], s["toe"]["com"] - whole[1]))),
            ("rest centre of mass moved 1 mm", lambda s: s["rest"].update(com=s["rest"]["com"] + [0.001, 0, 0])),
            ("toe mass off by 1 g", lambda s: s["toe"].update(mass=s["toe"]["mass"] + 0.001)),
            ("toe tensor without its box-to-centre-of-mass shift", lambda s: s["toe"].update(inertia=s["toe"]["inertia"] - pp.parallel_axis(s["toe"]["mass"], [0.0043, 0, 0])))):
        bad = {k: dict(v) for k, v in good.items()}
        tamper(bad)
        err = pp.foot_conservation_error(whole, bad)
        assert max(err["mass_rel"], err["com_m"], err["inertia"]) > 1e-7, name


def test_the_mirror_image_foot_splits_into_the_mirror_image_parts():
    r, l = split("right"), split("left")
    assert r["toe"]["mass"] == l["toe"]["mass"] and np.allclose(r["rest"]["com"] * [1, -1, 1], l["rest"]["com"], atol=1e-15)
    flip = np.diag([1, -1, 1])
    assert np.allclose(flip @ r["rest"]["inertia"] @ flip, l["rest"]["inertia"], atol=1e-15)


def test_the_toe_is_what_the_design_range_says():
    s = split()
    t = s["toe"]
    assert t["mass"] == pytest.approx(0.144 * 0.65, rel=1e-12)  # 14.4% of the sheet's whole-foot mass
    assert t["length"] == pytest.approx(0.19514 - 0.12812, abs=1e-12)  # hinge to tip
    assert t["com"][0] - t["hinge"][0] == pytest.approx(0.436 * t["length"], abs=1e-12)  # 43.6% of the toe length from the hinge
    assert t["hinge"][2] == pytest.approx(-ANKLE_M + 0.0125, abs=1e-12)  # the axis at the mid-height of a toe box 25 mm tall whose sole is the foot's sole
    assert t["half"].tolist() == pytest.approx([t["length"] / 2, 0.050, 0.0125])
    box = np.diag([(0.1 ** 2 + 0.025 ** 2), (t["length"] ** 2 + 0.025 ** 2), (t["length"] ** 2 + 0.1 ** 2)]) * t["mass"] / 12  # its box about its own centre
    assert np.allclose(np.diag(t["inertia"])[1], box[1, 1] + t["mass"] * (0.436 * t["length"] - t["length"] / 2) ** 2, atol=1e-12)  # carried to the centre of mass about y


def test_the_foot_box_runs_from_the_heel_to_the_toe_hinge():
    r = split()["rest"]
    assert r["box_pos_x"] - r["box_half_x"] == pytest.approx(-0.06197, abs=1e-12)  # the rear face, behind the ankle
    assert r["box_pos_x"] + r["box_half_x"] == pytest.approx(0.12812, abs=1e-12)  # the front face is the hinge
    assert r["box_half_y"] == pytest.approx(0.050)


def test_a_remainder_that_breaks_the_triangle_inequality_is_refused_not_clipped():
    """Finding: on the committed (unscaled) foot row the remainder is not a physical body. The check must refuse the build and say so."""
    with pytest.raises(pp.BuildError) as e:
        fh.build_model_file(fh.tempfile.mkdtemp(), scaled=False)
    assert "triangle inequality" in e.value.format() and "foot_right" in e.value.format()


# ---------------------------------------------------------------- the design range

def read(rows):
    r = pp.Report()
    return pp.read_design(pp.RawTable("design", "BSIP Reference", 10, 1, rows), r), r


def test_the_design_range_is_read_in_si_with_the_cell_that_gave_each_value():
    out, r = read([[k, v] for k, v in fh.SPEC_DESIGN.items()])
    assert r.errors == [] and r.warnings == []
    assert out["foot_heel_behind_ankle"].value == pytest.approx(0.06197) and out["foot_heel_behind_ankle"].source == "'BSIP Reference'!B11"
    assert out["toe_stiffness_nm_per_rad"].value == pytest.approx(0.25 * 180 / np.pi) and out["toe_damping_nm_s_per_rad"].value == 0.05
    assert out["stand_pelvis_tilt_deg"].value == 12.0 and out["toe_mass_fraction"].value == 0.144


def test_an_absent_range_gives_nothing_and_a_missing_or_bad_key_is_an_error_naming_the_cell():
    assert pp.read_design(None, pp.Report()) == {}
    rows = [[k, v] for k, v in fh.SPEC_DESIGN.items()]
    out, r = read(rows[:-1])
    assert any("toe_damping_nm_s_per_rad" in e and "missing" in e for e in r.errors)
    for bad, text in (("abc", "not a number"), ("", "empty"), (-5.0, "outside"), (0.0, "outside"), (1e6, "outside"), (float("nan"), "not a number")):
        rows2 = [[k, v] for k, v in fh.SPEC_DESIGN.items()]
        i = [k for k, _ in rows2].index("toe_hinge_ahead_ankle_mm")
        rows2[i][1] = bad
        out, r = read(rows2)
        assert any(text in e and f"B{10 + i}" in e and "toe_hinge_ahead_ankle_mm" in e for e in r.errors), (bad, r.errors)
    out, r = read(rows + [["toe_height_mm", 25.0]])
    assert any("appears twice" in e for e in r.errors)
    out, r = read([["Key", "Value"]] + rows + [["mystery_mm", 3.0]])
    assert r.errors == [] and len(r.warnings) == 1 and "mystery_mm" in r.warnings[0]  # a header row is skipped, an unknown key is ignored with a warning


def test_zero_tilt_and_zero_stiffness_are_allowed_zero_length_is_not():
    out, r = read([[k, (0.0 if k in ("stand_pelvis_tilt_deg", "toe_stiffness_nm_per_deg", "toe_damping_nm_s_per_rad") else v)] for k, v in fh.SPEC_DESIGN.items()])
    assert r.errors == []
    out, r = read([[k, (0.0 if k == "foot_half_width_mm" else v)] for k, v in fh.SPEC_DESIGN.items()])
    assert any("foot_half_width_mm" in e for e in r.errors)


def test_a_hinge_that_disagrees_with_the_foot_lengths_is_a_warning_and_a_hinge_behind_the_ankle_is_an_error():
    r = pp.Report()
    pp.check_design(pp.read_design(fh.design_table(toe_hinge_ahead_ankle_mm=130.0), r), r)
    assert r.errors == [] and any("toe_hinge_ahead_ankle" in w for w in r.warnings)
    r = pp.Report()
    pp.check_design(pp.read_design(fh.design_table(toe_tip_ahead_ankle_mm=100.0), r), r)
    assert any("must be ahead of the ankle and behind the toe tip" in e for e in r.errors)
    r = pp.Report()
    pp.check_design(pp.read_design(fh.design_table(), r), r)
    assert r.errors == [] and r.warnings == []  # the spec's own numbers are consistent to 0.01 mm


def test_without_a_design_range_the_build_says_where_the_foot_comes_from():
    t = fh.tables()
    del t["design"]
    with pytest.raises(pp.BuildError) as e:
        pp.build_model(t, template=fh.TEMPLATE, output=Path(fh.tempfile.mkdtemp()) / "m.xml", archive=False, dry_run=True)
    assert "'design' named range" in e.value.format()


# ---------------------------------------------------------------- the compiled model

@pytest.fixture(scope="module")
def model():
    return mujoco.MjModel.from_xml_path(str(fh.fixture_model_path()))


def test_two_bodies_and_two_hinges_more(model):
    assert model.nbody - 1 == 18 and model.njnt - 1 == 33  # 16 bodies and 31 hinges before, the free root aside
    for side in ("right", "left"):
        assert model.body(f"toe_{side}").parentid[0] == model.body(f"foot_{side}").id


def test_the_toe_hinge_is_passive_extension_positive_stopped_flat_and_at_80_degrees(model):
    for side in ("right", "left"):
        j = model.joint(f"toe_{side}")
        assert np.allclose(j.axis, [0, -1, 0])  # the ankle's axis: a positive angle lifts the toe tip
        assert j.limited[0] and np.allclose(np.degrees(j.range), [0.0, 80.0], atol=1e-9)
        assert j.stiffness[0] == pytest.approx(0.25 * 180 / np.pi, rel=1e-9) and model.dof_damping[j.dofadr[0]] == 0.05


def test_the_spring_torque_is_the_stiffness_in_n_m_per_rad_whatever_the_compiler_angle_unit(model):
    """Guard against MuJoCo reading the stiffness in degrees: at 0.5 rad the spring pulls back with k * 0.5."""
    d = mujoco.MjData(model)
    j = model.joint("toe_right")
    d.qpos[j.qposadr[0]] = 0.5
    mujoco.mj_forward(model, d)
    assert d.qfrc_passive[j.dofadr[0]] == pytest.approx(-0.5 * 0.25 * 180 / np.pi, rel=1e-9)


def test_positive_toe_angle_lifts_the_tip(model):
    d = mujoco.MjData(model)
    g = next(g for g in range(model.ngeom) if model.geom_bodyid[g] == model.body("toe_right").id)
    mujoco.mj_forward(model, d)
    z0 = d.geom_xpos[g][2] + d.geom_xmat[g].reshape(3, 3)[2, 0] * model.geom_size[g][0]
    d.qpos[model.joint("toe_right").qposadr[0]] = 0.3
    mujoco.mj_forward(model, d)
    z1 = d.geom_xpos[g][2] + d.geom_xmat[g].reshape(3, 3)[2, 0] * model.geom_size[g][0]
    assert z1 > z0 + 0.01


def body_tensor_in_foot_frame(model, name):
    b = model.body(name)
    r = np.zeros(9)
    mujoco.mju_quat2Mat(r, b.iquat)
    r = r.reshape(3, 3)
    return b.mass[0], b.ipos.copy(), r @ np.diag(b.inertia) @ r.T


@pytest.mark.parametrize("side", ["right", "left"])
def test_the_compiled_foot_and_toe_together_are_the_sheets_whole_foot(model, side):
    """From MuJoCo's own body data, not from the preprocessor's arithmetic: the toe body (frame parallel to the foot's, origin at its hinge) and the foot
    body recomposed about their common centre of mass are the whole-foot row of the sheet, to 1e-9."""
    t = fh.tables()
    names = [pp.column_key(h) for h in t["bsip"].rows[0]]
    row = next(r for r in t["bsip"].rows[1:] if pp.ident(r[0]) == "foot")
    get = lambda col: float(row[names.index(col)])  # noqa: E731
    sign = np.array([1, 1 if side == "right" else -1, 1])
    want_m, want_c = get("mass"), np.array([get("com_x"), get("com_y"), get("com_z")]) * sign
    want_I = pp._tensor([get(k) for k in pp.INERTIA_KEYS]) * np.outer(sign, sign)  # the left foot negates the products with y
    mf, cf, If = body_tensor_in_foot_frame(model, f"foot_{side}")
    mt, ct, It = body_tensor_in_foot_frame(model, f"toe_{side}")
    ct = ct + model.body(f"toe_{side}").pos  # into the foot frame
    m = mf + mt
    c = (mf * cf + mt * ct) / m
    I = If + pp.parallel_axis(mf, cf - c) + It + pp.parallel_axis(mt, ct - c)
    assert m == pytest.approx(want_m, rel=CONSERVATION_TOL) and np.abs(c - want_c).max() < CONSERVATION_TOL and np.abs(I - want_I).max() < CONSERVATION_TOL


def test_the_model_mass_is_the_sheets_mass_with_the_toe_counted_under_the_foot(model):
    v = fh.snapshot_values()
    total = sum(x for k, x in v.items() if k.endswith("_mass") and k != "target_mass")
    assert sum(model.body_mass[1:]) == pytest.approx(total, rel=1e-9)


# ---------------------------------------------------------------- regression: the old box with a negligible welded toe reproduces the tracked reference

def test_with_the_old_box_a_negligible_toe_and_the_toe_welded_the_tracked_a_filtered_reference_is_reproduced(tmp_path):
    """The toe's footprint, hinge and split must change nothing else: a foot box from 41.25 mm behind to 165 mm ahead (the old box, as heel behind and toe tip
    ahead), a toe of mass fraction 1e-6, the toe held flat (method A never moves it), and the walking-reference subset (AB06, 1.4 m/s, three strides) of A_filtered
    comes out as the tracked sim/benchmarks/walk_reference.json says, to its own reproduction tolerance. Only A_filtered is compared: it is the one method
    the tracked reference holds, and B and H see the footprint."""
    import gait
    old_box = fh.design_table(foot_heel_behind_ankle_mm=41.25, toe_hinge_ahead_ankle_mm=128.0, toe_tip_ahead_ankle_mm=165.0, foot_ball_length_mm=169.25,
                              foot_length_total_mm=206.25, toe_mass_fraction=1e-6)
    path = fh.build_model_file(tmp_path, design=old_box, scaled=False)
    base = json.loads((REPO / "sim" / "benchmarks" / "walk_reference.json").read_text(encoding="utf-8"))["reproduction"]
    now = gait.reference_metrics(methods=["A_filtered"], model_path=path)
    assert gait.compare_reference(base["metrics"], now, base["tolerance_rel"]) == []
