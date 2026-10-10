"""The MJCF checks, each against the committed model and against a deliberately broken copy
(its mutation test, CONVENTIONS section 7). A gate failure fails the test; an advisory failure
is an xfail that shows the measured number."""
import xml.etree.ElementTree as ET

import pytest

import checklib as cl
import mjcf_checks as mc


def run(ctx, check_id):
    return cl.call(cl.REGISTRY[check_id], ctx)


def only(results, check_id):
    return next(r for r in results if r.id == check_id)


def require(results):
    """gate failures fail the test, advisory failures are an xfail with the number"""
    for r in results:
        if r.status == cl.FAIL:
            if r.tier == "gate":
                pytest.fail(f"{r.id}: {r.message}")
            pytest.xfail(f"{r.id} (advisory): {r.message}")


def mutated(ctx, edit, snapshot=None):
    """A copy of the model (and optionally a changed snapshot) with edit(root) applied."""
    root = ET.fromstring(ctx.xml_text)
    edit(root)
    return cl.Context.from_xml_text(ET.tostring(root, encoding="unicode"), {**ctx.snapshot, **(snapshot or {})})


def without(ctx, key):
    return cl.Context.from_xml_text(ctx.xml_text, {k: v for k, v in ctx.snapshot.items() if k != key})


def with_snapshot(ctx, **values):
    return cl.Context.from_xml_text(ctx.xml_text, {**ctx.snapshot, **values})


def body(root, name):
    return next(b for b in root.iter("body") if b.get("name") == name)


def joint(root, name):
    return next(j for j in root.iter("joint") if j.get("name") == name)


def inertial(root, name):
    return body(root, name).find("inertial")


def tokens(element, attr):
    return element.get(attr).split()


def with_token(element, attr, index, fn):
    t = tokens(element, attr)
    t[index] = str(fn(float(t[index])))
    element.set(attr, " ".join(t))


# ---------------------------------------------------------------- mass_closure

@pytest.mark.check("check.mjcf.mass_closure", tier="gate")
def test_mass_closure_passes_on_the_model(ctx):
    rs = run(ctx, "check.mjcf.mass_closure")
    assert only(rs, "check.mjcf.mass_closure").status == cl.PASS
    require(rs)
    assert abs(only(rs, "check.mjcf.mass_closure").measured["model_mass_kg"] - 64.935) < 1e-3


@pytest.mark.check("check.mjcf.mass_closure", tier="gate")
def test_mass_closure_fails_when_a_segment_mass_is_wrong(ctx):
    bad = mutated(ctx, lambda r: inertial(r, "thigh_left").set("mass", "9.6"))
    assert only(run(bad, "check.mjcf.mass_closure"), "check.mjcf.mass_closure").status == cl.FAIL


@pytest.mark.check("check.mjcf.mass_closure", tier="gate")
def test_mass_closure_target_part_is_advisory_skips_without_target_and_fails_when_off(ctx):
    t = "check.mjcf.mass_closure.target"
    r = only(run(ctx, "check.mjcf.mass_closure"), t)
    assert r.tier == "advisory" and r.status == cl.PASS  # 64.935 vs 65 kg is 0.1%
    r = only(run(without(ctx, "target_mass"), "check.mjcf.mass_closure"), t)
    assert r.status == cl.SKIP and "target_mass" in r.message
    assert only(run(with_snapshot(ctx, target_mass=70.0), "check.mjcf.mass_closure"), t).status == cl.FAIL


# ---------------------------------------------------------------- mirror

@pytest.mark.check("check.mjcf.mirror", tier="gate")
def test_mirror_passes_on_the_model(ctx):
    rs = run(ctx, "check.mjcf.mirror")
    require(rs)
    assert rs[0].status == cl.PASS and rs[0].measured["pairs"] >= 6


MIRROR_MUTATIONS = {
    "mass": lambda r: inertial(r, "thigh_left").set("mass", "9.6"),
    "com_y_not_negated": lambda r: with_token(inertial(r, "shank_left"), "pos", 1, lambda x: -x),
    "ixz_negated": lambda r: with_token(inertial(r, "thigh_left"), "fullinertia", 4, lambda x: -x),
    "ixy_not_negated": lambda r: with_token(inertial(r, "thigh_left"), "fullinertia", 3, lambda x: -x),
    "axis_not_mirrored": lambda r: joint(r, "hip_aa_left").set("axis", "1 0 0"),
    "axis_y_flipped": lambda r: joint(r, "knee_left").set("axis", "0 -1 0"),
    "range": lambda r: joint(r, "elbow_left").set("range", "-0.1 2.0"),
    "body_pos_y": lambda r: body(r, "forearm_left").set("pos", "0 0.01 -0.243"),
}


@pytest.mark.check("check.mjcf.mirror", tier="gate")
@pytest.mark.parametrize("name", sorted(MIRROR_MUTATIONS))
def test_mirror_fails_on_a_broken_copy(ctx, name):
    bad = mutated(ctx, MIRROR_MUTATIONS[name])
    assert run(bad, "check.mjcf.mirror")[0].status == cl.FAIL, name


# ---------------------------------------------------------------- joint_signs

@pytest.mark.check("check.mjcf.joint_signs", tier="gate")
def test_joint_signs_on_the_model(ctx):
    rs = run(ctx, "check.mjcf.joint_signs")
    assert rs[0].tier == "gate"  # Joe approved the polarity file
    assert rs[0].status == cl.PASS, rs[0].message
    assert rs[0].measured["checked"] == 31


@pytest.mark.check("check.mjcf.joint_signs", tier="gate")
def test_joint_signs_is_advisory_while_the_polarity_file_is_a_draft(ctx, tmp_path):
    draft = tmp_path / "p.yaml"
    draft.write_text(mc.POLARITY_FILE.read_text(encoding="utf-8").replace("status: approved", "status: DRAFT"), encoding="utf-8")
    bad = mutated(ctx, lambda r: joint(r, "knee_right").set("axis", "0 -1 0"))
    r = mc.joint_signs(bad, polarity=draft)
    assert r.status == cl.FAIL and r.tier == "advisory"


@pytest.mark.check("check.mjcf.joint_signs", tier="gate")
def test_joint_signs_fails_when_a_spine_axis_is_negated(ctx):
    bad = mutated(ctx, lambda r: joint(r, "tj_fe").set("axis", "0 -1 0"))
    r = run(bad, "check.mjcf.joint_signs")[0]
    assert r.status == cl.FAIL and "tj_fe" in r.message


@pytest.mark.check("check.mjcf.joint_signs", tier="gate")
def test_joint_signs_fails_when_one_axis_is_negated(ctx):
    bad = mutated(ctx, lambda r: joint(r, "knee_right").set("axis", "0 -1 0"))
    r = run(bad, "check.mjcf.joint_signs")[0]
    assert r.status == cl.FAIL and "knee_right" in r.message


@pytest.mark.check("check.mjcf.joint_signs", tier="gate")
def test_joint_signs_is_a_gate_once_the_polarity_file_is_approved(ctx):
    assert "status: approved" in mc.POLARITY_FILE.read_text(encoding="utf-8")
    bad = mutated(ctx, lambda r: joint(r, "knee_right").set("axis", "0 -1 0"))
    r = mc.joint_signs(bad)
    assert r.status == cl.FAIL and r.tier == "gate"


@pytest.mark.check("check.mjcf.joint_signs", tier="gate")
def test_every_hinge_in_the_model_has_a_polarity_row(ctx):
    rows = mc.load_polarity()["joints"]
    assert {j.get("name") for j in ET.fromstring(ctx.xml_text).iter("joint") if j.get("type") == "hinge"} <= set(rows)
    root = ET.fromstring(ctx.xml_text)
    body(root, "shank_right").append(ET.Element("joint", name="knee_extra", type="hinge", axis="0 1 0"))
    extra = cl.Context.from_xml_text(ET.tostring(root, encoding="unicode"), ctx.snapshot)
    r = run(extra, "check.mjcf.joint_signs")[0]
    assert r.status == cl.FAIL and "knee_extra" in r.message


# ---------------------------------------------------------------- floor_contact

@pytest.mark.check("check.mjcf.floor_contact", tier="advisory")
def test_floor_contact_on_the_model(ctx):
    rs = run(ctx, "check.mjcf.floor_contact")
    require(rs)
    assert abs(rs[0].measured["lowest_point_m"]) < 1e-6


@pytest.mark.check("check.mjcf.floor_contact", tier="advisory")
def test_floor_contact_fails_when_the_feet_float_or_sink(ctx):
    for z in ("0.98", "0.94"):  # pelvis up or down by about 2 cm
        bad = mutated(ctx, lambda r, z=z: body(r, "pelvis").set("pos", f"0 0 {z}"))
        assert run(bad, "check.mjcf.floor_contact")[0].status == cl.FAIL, z


# ---------------------------------------------------------------- stature_chain

@pytest.mark.check("check.mjcf.stature_chain", tier="advisory")
def test_stature_chain_on_the_model(ctx):
    rs = run(ctx, "check.mjcf.stature_chain")
    require(rs)
    assert abs(rs[0].measured["offset_mm"] - (-14.684)) < 0.5  # the sheet's own definitional offset


@pytest.mark.check("check.mjcf.stature_chain", tier="advisory")
def test_stature_chain_skips_without_a_target_and_fails_when_off(ctx):
    r = run(without(ctx, "target_stature"), "check.mjcf.stature_chain")[0]
    assert r.status == cl.SKIP and "target_stature" in r.message
    assert run(with_snapshot(ctx, target_stature=1.75), "check.mjcf.stature_chain")[0].status == cl.FAIL
    bad = mutated(ctx, lambda r: next(s for s in r.iter("site") if s.get("name") == "site_vertex").set("pos", "0 0 0.35"))
    assert run(bad, "check.mjcf.stature_chain")[0].status == cl.FAIL


# ---------------------------------------------------------------- com

@pytest.mark.check("check.mjcf.com_pct_stature", tier="advisory")
def test_com_pct_stature_reports_the_known_value(ctx):
    rs = run(ctx, "check.mjcf.com")
    assert abs(only(rs, "check.mjcf.com_pct_stature").measured["pct_stature"] - 55.26) < 0.02
    require([only(rs, "check.mjcf.com_lateral")])


@pytest.mark.check("check.mjcf.com_pct_stature", tier="advisory")
def test_com_pct_stature_passes_inside_the_band_and_fails_outside(ctx):
    z = only(run(ctx, "check.mjcf.com"), "check.mjcf.com_pct_stature").measured["com_height_m"]
    pct = "check.mjcf.com_pct_stature"
    assert only(run(with_snapshot(ctx, target_stature=z / 0.5588), "check.mjcf.com"), pct).status == cl.PASS
    assert only(run(with_snapshot(ctx, target_stature=z / 0.60), "check.mjcf.com"), pct).status == cl.FAIL
    assert only(run(without(ctx, "target_stature"), "check.mjcf.com"), pct).status == cl.SKIP


@pytest.mark.check("check.mjcf.com_lateral", tier="advisory")
def test_com_lateral_fails_when_the_body_leans_to_one_side(ctx):
    bad = mutated(ctx, lambda r: inertial(r, "pelvis").set("pos", "0.0 0.1 -0.05"))
    assert only(run(bad, "check.mjcf.com"), "check.mjcf.com_lateral").status == cl.FAIL


# ---------------------------------------------------------------- the committed waivers file

@pytest.mark.check("check.infra.waivers", tier="gate")
def test_committed_waivers_name_registered_checks_and_have_every_field():
    for w in cl.load_waivers():
        assert w.check in cl.all_ids(), w.check
