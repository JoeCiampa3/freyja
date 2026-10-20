"""check.mjcf.top_of_head (advisory, Stage 2g T4): the top of the head above the floor in the upright design stance against the target stature, with its mutation tests.
The models are the fixtures of tests/foot_help.py: the committed snapshot (whose lengths close the stack on chord lengths, not vertical heights) plus the design range."""
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tests"))

import checklib as cl  # noqa: E402
import foot_help as fh  # noqa: E402
import mjcf_checks as mc  # noqa: E402


@pytest.fixture(scope="module")
def ctx():
    return cl.Context.from_xml_text(Path(fh.fixture_model_path()).read_text(encoding="utf-8"), fh.scaled_snapshot_values())


def run(c):
    return cl.call(cl.REGISTRY["check.mjcf.top_of_head"], c)[0]


def with_values(c, **v):
    return cl.Context.from_xml_text(c.xml_text, {**c.snapshot, **v})


@pytest.mark.check("check.mjcf.top_of_head", tier="advisory")
def test_it_is_advisory_and_skips_without_the_tilt_or_the_stature(ctx):
    assert cl.REGISTRY["check.mjcf.top_of_head"].tier == "advisory"
    assert run(cl.Context.from_xml_text(ctx.xml_text, {k: v for k, v in ctx.snapshot.items() if k != "stand_pelvis_tilt_deg"})).status == cl.SKIP
    assert run(cl.Context.from_xml_text(ctx.xml_text, {k: v for k, v in ctx.snapshot.items() if k != "target_stature"})).status == cl.SKIP


@pytest.mark.check("check.mjcf.top_of_head", tier="advisory")
def test_a_fixture_that_fails_the_committed_lengths_do_not_close_the_stack_on_vertical_heights(ctx):
    """The committed snapshot's lengths were closed on chord lengths for a stature of 1700 mm: with the pelvis tilted 12 degrees the head is short of the stature."""
    r = run(ctx)
    assert r.status == cl.FAIL and r.measured["offset_mm"] < -3.0, r.message


@pytest.mark.check("check.mjcf.top_of_head", tier="advisory")
def test_it_passes_when_the_stature_is_the_height_and_fails_when_the_head_moves_by_more_than_the_limit(ctx):
    height = run(ctx).measured["top_of_head_m"]
    ok = with_values(ctx, target_stature=height + 0.0029)
    assert run(ok).status == cl.PASS
    for off in (0.0031, -0.0031, 0.02):
        assert run(with_values(ctx, target_stature=height + off)).status == cl.FAIL, off
    root = ET.fromstring(ctx.xml_text)
    site = next(e for e in root.iter("site") if e.get("name") == "site_vertex")
    x, y, z = (float(t) for t in site.get("pos").split())
    site.set("pos", f"{x} {y} {z + 0.005}")  # the head 5 mm taller: a broken copy of the model
    broken = cl.Context.from_xml_text(ET.tostring(root, encoding="unicode"), {**ctx.snapshot, "target_stature": height})
    assert run(broken).status == cl.FAIL


@pytest.mark.check("check.mjcf.top_of_head", tier="advisory")
def test_at_zero_tilt_it_is_the_neutral_pose_vertex_height_of_check_stature_chain(ctx):
    """The upright stance with no tilt is the model at neutral, so the two checks must read the same vertex height."""
    flat = with_values(ctx, stand_pelvis_tilt_deg=0.0)
    chain = cl.call(cl.REGISTRY["check.mjcf.stature_chain"], flat)[0]
    assert run(flat).measured["top_of_head_m"] == pytest.approx(chain.measured["vertex_height_m"], abs=1e-9)
