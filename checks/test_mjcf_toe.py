"""The MJCF checks on a model with the toe (Stage 2g T2), each with its mutation. The model is the fixture of tests/foot_help.py: the committed snapshot plus the
design range of the sheet spec, built into a temporary directory. The tracked model has no toe until the sheet carries the design range and `fy build` has run."""
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

import mujoco
import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tests"))

import checklib as cl  # noqa: E402
import foot_help as fh  # noqa: E402
import mjcf_checks as mc  # noqa: E402


@pytest.fixture(scope="module")
def ctx():
    return cl.Context.from_xml_text(Path(fh.fixture_model_path()).read_text(encoding="utf-8"), fh.scaled_snapshot_values())


def run(c, check_id):
    return cl.call(cl.REGISTRY[check_id], c)[0]


def mutated(c, edit, **snapshot):
    root = ET.fromstring(c.xml_text)
    edit(root)
    return cl.Context.from_xml_text(ET.tostring(root, encoding="unicode"), {**c.snapshot, **snapshot})


def named(root, tag, name):
    return next(e for e in root.iter(tag) if e.get("name") == name)


def test_the_model_with_the_toe_has_eighteen_bodies_and_thirty_three_hinges(ctx):
    assert ctx.model.nbody - 1 == 18 and ctx.model.njnt - 1 == 33


@pytest.mark.check("check.mjcf.joint_signs", tier="gate")
def test_joint_signs_checks_the_toe_hinges_and_fails_when_one_is_flipped(ctx):
    r = run(ctx, "check.mjcf.joint_signs")
    assert r.status == cl.PASS and r.measured["checked"] == 33, r.message
    bad = mutated(ctx, lambda root: named(root, "joint", "toe_left").set("axis", "0 1 0"))
    r = run(bad, "check.mjcf.joint_signs")
    assert r.status == cl.FAIL and "toe_left" in r.message


@pytest.mark.check("check.mjcf.joint_signs", tier="gate")
def test_no_row_is_pending_now_that_the_model_has_the_toe_and_a_row_without_a_hinge_fails(ctx, tmp_path):
    import yaml
    tracked = mc.load_polarity()
    assert not tracked.get("pending")  # the toe rows were written ahead of the model; the model has the hinges, so the list is gone
    spec = {**tracked, "joints": {**tracked["joints"], "ghost_right": tracked["joints"]["toe_right"]}}
    path = tmp_path / "p.yaml"
    path.write_text(yaml.safe_dump(spec), encoding="utf-8")
    r = mc.joint_signs(ctx, polarity=path)
    assert r.status == cl.FAIL and "ghost_right: row names a joint that is not a hinge" in r.message
    spec = {**tracked, "pending": ["ghost_right"]}  # the mechanism stays for the next joint added ahead of its model
    path.write_text(yaml.safe_dump(spec), encoding="utf-8")
    assert "ghost_right: listed as pending" in mc.joint_signs(ctx, polarity=path).message


@pytest.mark.check("check.mjcf.joint_signs", tier="gate")
def test_every_ankle_probe_point_is_inside_the_foot_box_of_the_model(ctx):
    """The ankle probes are hand-written points in the foot frame; they must stay on the foot whatever the foot box is, so the sign they show is the foot's."""
    m, d = ctx.model, ctx.data
    rows = mc.load_polarity()["joints"]
    for name in ("ankle_pdflex_right", "ankle_pdflex_left", "ankle_ie_right", "ankle_ie_left"):
        jid = m.joint(name).id
        body = int(m.jnt_bodyid[jid])
        p = np.array(rows[name]["probe"], float)
        inside = False
        for g in range(m.ngeom):
            if m.geom_bodyid[g] == body and m.geom_type[g] == mujoco.mjtGeom.mjGEOM_BOX:
                local = m.geom_quat[g]  # boxes here are axis aligned in the foot frame
                assert np.allclose(local, [1, 0, 0, 0])
                inside |= bool(np.all(np.abs(p - m.geom_pos[g]) <= m.geom_size[g] + 1e-12))
        assert inside, (name, p.tolist())


@pytest.mark.check("check.mjcf.mirror", tier="gate")
def test_mirror_needs_nothing_for_the_toe_and_fails_when_one_toe_differs(ctx):
    r = run(ctx, "check.mjcf.mirror")
    assert r.status == cl.PASS and r.measured["pairs"] == 7 and r.measured["joint_pairs"] == 12, r.message  # toe_right/toe_left are one more pair of each
    for edit in (lambda root: named(root, "body", "toe_left").find("inertial").set("mass", "0.1"),
                 lambda root: named(root, "joint", "toe_left").set("range", "0 1.0")):
        assert run(mutated(ctx, edit), "check.mjcf.mirror").status == cl.FAIL


@pytest.mark.check("check.mjcf.mass_closure", tier="gate")
def test_mass_closure_counts_the_toe_under_the_foot(ctx):
    r = run(ctx, "check.mjcf.mass_closure")
    assert r.status == cl.PASS, r.message
    bad = mutated(ctx, lambda root: named(root, "body", "toe_right").find("inertial").set("mass", "0.0946"))  # 1 g more than the toe's share
    assert run(bad, "check.mjcf.mass_closure").status == cl.FAIL
    bad = mutated(ctx, lambda root: None, foot_right_mass=0.651)
    assert run(bad, "check.mjcf.mass_closure").status == cl.FAIL  # the snapshot's whole-foot mass is the sum of the foot body and the toe


@pytest.mark.check("check.mjcf.floor_contact", tier="advisory")
def test_the_lowest_collision_point_including_the_toe_is_on_the_floor(ctx):
    r = run(ctx, "check.mjcf.floor_contact")
    assert r.status == cl.PASS, r.message
