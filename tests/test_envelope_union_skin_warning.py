"""Volume-extractor brief 8, item 9 (the memo 37 defect): in `check --segment a,b` the warning that a component sticks out of the skin evaluated the second body's components in that body's own
frame against the union's skin, which lives in the first body's frame. The component's points must be shifted by the body's origin offset first."""
import sys
from pathlib import Path

import numpy as np
import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "tools"))

from envelope import field, occupancy, registry  # noqa: E402
from envelope.synthetic import frustum  # noqa: E402


def cylinder_body(radius, length=100.0):
    v, f = frustum(radius, radius, 40.0, -length - 40.0)
    return field.build_segment(v, f, length=length, voxel=2.0, z_top=0.0, margin=30.0)


def registry_on_second_body():
    doc = {"schema": registry.SCHEMA, "segment": "lower", "components": [
        {"id": "part.x", "name": "wide", "status": "designed", "owner": "lower", "primitive": {"type": "cylinder", "diameter": 100, "length": 60}, "pose": {"tx": 0, "ty": 0, "tz": -50}}]}
    return registry.parse(doc, REPO, "test")


def test_a_component_in_the_second_body_is_measured_against_the_skin_where_it_is():
    upper, lower = cylinder_body(30.0), cylinder_body(100.0)           # the union is narrow on top, wide below
    offset = np.array([0.0, 0.0, -100.0])                              # the lower body's origin in the upper body's frame
    skin = occupancy.skin_field([(upper, np.zeros(3)), (lower, offset)], 0.0)
    reg = registry_on_second_body()
    wrong = occupancy.component_skin_margins(skin.signed_distance, reg)["wide"]                       # the defect: no offset, the point lands in the narrow upper body
    right = occupancy.component_skin_margins(skin.signed_distance, reg, offset)["wide"]
    assert wrong < 0 < right
    assert right == pytest.approx(50.0, abs=2.0)                       # radius 100 body, radius 50 component: 50 mm to the skin


def test_without_an_offset_nothing_changes_for_the_first_body_or_a_single_segment():
    body = cylinder_body(100.0)
    reg = registry_on_second_body()
    a = occupancy.component_skin_margins(body.signed_distance, reg)
    b = occupancy.component_skin_margins(body.signed_distance, reg, (0.0, 0.0, 0.0))
    assert a == b
