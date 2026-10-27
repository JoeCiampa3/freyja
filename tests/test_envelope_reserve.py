"""Volume-extractor brief 8, item 5: the spine reservations. The module volume check, the placement search on synthetic bodies with an analytic answer, the registry of reserved modules and the free
numbers. The committed result (`data/envelope/reservations_result.json`) is tested at the end."""
import json
import sys
from pathlib import Path

import numpy as np
import pytest
import yaml

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "tools"))

from envelope import field, registry, reserve  # noqa: E402
from envelope.synthetic import frustum  # noqa: E402

MODULE = {"count": 3, "diameter_mm": 90, "length_mm": 81.5, "mass_kg": 1.4}


def cylinder_body(radius, length=200.0):
    v, f = frustum(radius, radius, 60.0, -length - 60.0)
    return field.build_segment(v, f, length=length, voxel=2.0, z_top=0.0, margin=40.0)


def test_the_module_volume_matches_the_briefs_figure():
    chk = reserve.module_check(reserve.load(REPO))
    assert chk["volume_mm3"] == pytest.approx(3 * np.pi / 4 * 90 ** 2 * 81.5)
    assert chk["within_2_percent"] and abs(chk["relative_difference"]) < 0.02
    assert chk["candidates"] == ["abdomen", "pelvis", "thorax"] and chk["clearance_mm"] == 5


def test_three_modules_fit_in_a_cylinder_up_to_the_analytic_margin_and_sit_on_its_axis():
    # three discs of radius 45 with centres 95 apart: the centres lie on a circle of radius 95 / sqrt(3) = 54.85 mm; the body of radius R holds them to a skin margin of R - 45 - 54.85
    R = 110.0
    r = reserve.search(cylinder_body(R), MODULE, 5.0, (0.0, 0.0))
    assert not r["none"]
    # the centres are taken on a 6 mm lattice (GRID_STRIDE), so the margin found is a lower bound, short by up to about one lattice step, and never above the analytic value
    assert R - 45 - 95 / np.sqrt(3) - 6.0 <= r["max_skin_margin_mm"] <= R - 45 - 95 / np.sqrt(3) + 1.0
    c = np.array(r["centres_mm"])
    d = [np.linalg.norm(c[i, :2] - c[j, :2]) for i in range(3) for j in range(i + 1, 3)]
    assert min(d) >= 95.0 - 1e-9
    assert np.linalg.norm(c[:, :2].mean(axis=0)) < 10.0 and r["centroid_offset_from_trunk_axis_mm"] < 10.0
    assert -200.0 + 81.5 / 2 - 1 <= r["module_centre_height_mm"] <= -81.5 / 2 + 1


def test_a_body_too_narrow_for_three_modules_says_none():
    r = reserve.search(cylinder_body(80.0), MODULE, 5.0, (0.0, 0.0))
    assert r == {"none": True, "reason": "no three modules fit even with a skin margin of 0"}


def test_a_body_shorter_than_the_module_says_none():
    r = reserve.search(cylinder_body(150.0, length=70.0), MODULE, 5.0, (0.0, 0.0))
    assert r["none"] is True


def test_the_registry_of_reserved_modules_is_valid_and_in_the_model_frame():
    body = cylinder_body(110.0)
    r = reserve.search(body, MODULE, 5.0, (-56.7, 0.0))
    off = (-56.7, 0.0, 0.0)
    doc = reserve.registry_doc("pelvis", r, MODULE, 5.0, off)
    reg = registry.parse(doc, REPO, "test")
    assert [c.status for c in reg.components] == ["reserved"] * 3 and all(c.occupies for c in reg.components)
    assert all(c.clearance_mm == 5.0 and c.mass_kg == 1.4 and c.primitive == {"type": "cylinder", "diameter": 90, "length": 81.5} for c in reg.components)
    for c, centre in zip(reg.components, r["centres_mm"]):
        assert c.pose[0] == pytest.approx(centre[0] - off[0], abs=1e-3)           # the pose is in the model frame; the segment frame is the model's plus the offset
    assert reserve.registry_doc("abdomen", {"none": True}, MODULE, 5.0, off) is None


def test_the_free_numbers_take_the_modules_and_their_clearance_out_of_the_inner_volume():
    body = cylinder_body(110.0)
    r = reserve.search(body, MODULE, 5.0, (0.0, 0.0))
    reg = registry.parse(reserve.registry_doc("pelvis", r, MODULE, 5.0, (0.0, 0.0, 0.0)), REPO, "test")
    n = reserve.free_numbers(body, [(reg, np.zeros(3))], 5.0, 9.49, 4.2)
    inner = np.pi * (110 - 5) ** 2 * 200 / 1e6
    assert n["inner_volume_l"] == pytest.approx(inner, rel=0.01)
    modules = 3 * np.pi / 4 * 90 ** 2 * 81.5 / 1e6
    assert n["occupied_volume_l"] >= modules * 0.99 and n["free_volume_l"] == pytest.approx(n["inner_volume_l"] - n["occupied_volume_l"], rel=1e-6)
    assert n["module_mass_fraction_of_sheet_mass"] == pytest.approx(4.2 / 9.49)
    assert n["density_remaining_inside_budget_kg_per_l"] == pytest.approx((9.49 - 4.2) / n["free_volume_l"])
    assert n["density_remaining_modules_additional_kg_per_l"] == pytest.approx(9.49 / n["free_volume_l"])


def test_the_committed_result_is_for_the_file_and_has_an_answer_per_candidate():
    res = json.loads((REPO / "data/envelope/reservations_result.json").read_text())
    assert res["module_check"]["within_2_percent"] and set(res["bodies"]) == {"abdomen", "pelvis", "thorax"}
    assert res["orientation_assumed"].startswith("vertical")
    for b, e in res["bodies"].items():
        assert "without_modules" in e
        if e["search"]["none"]:
            assert "with_modules" not in e and not (REPO / f"data/envelope/reserved/{b}.yaml").exists()
        else:
            doc = yaml.safe_load((REPO / f"data/envelope/reserved/{b}.yaml").read_text())
            assert len(doc["components"]) == 3 and registry.parse(doc, REPO, b).segment == b
            w = e["with_modules"]["at_required_margin"]
            assert w["free_volume_l"] < w["inner_volume_l"] and w["module_mass_kg"] == pytest.approx(4.2)
