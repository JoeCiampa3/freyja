"""Volume-extractor brief 8, item 6: the corridor sweep on synthetic bodies with an analytic answer, the sim-axis read from `trunk_offsets.json`, and the committed result."""
import json
import sys
from pathlib import Path

import numpy as np
import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "tools"))

from envelope import corridor, field  # noqa: E402
from envelope.synthetic import frustum  # noqa: E402


def body(cx, radius, length, cy=0.0):
    v, f = frustum(radius, radius, 60.0, -length - 60.0)
    v = v + np.array([cx, cy, 0.0])
    return field.build_segment(v, f, length=length, voxel=2.0, z_top=0.0, margin=40.0)


@pytest.fixture(scope="module")
def two_bodies():
    # the abdomen's column of radius 60 is centred at x = +20, the thorax's at x = -10: a vertical axis at d keeps a radius min(55 - |d - 20|, 55 - |d + 10|) at skin margin 5
    return {"abdomen": body(20.0, 60.0, 80.0), "thorax": body(-10.0, 60.0, 120.0)}


def test_the_best_axis_balances_the_two_bodies_and_the_minimum_diameter_is_analytic(two_bodies):
    prof = corridor.profile(two_bodies, 5.0)
    b = corridor.best(prof)
    assert b["best_d_mm"] == pytest.approx(5.0, abs=0.01)                       # the 5 mm sweep lands on the midpoint of the two centres
    assert b["best_min_diameter_mm"] == pytest.approx(2 * (55.0 - 15.0), abs=3.0)
    tab = {r["d_mm"]: r["min_diameter_mm"] for r in b["table"]}
    assert tab[20.0] == pytest.approx(2 * (55.0 - 30.0), abs=5.0) and tab[-10.0] == pytest.approx(2 * (55.0 - 30.0), abs=5.0)      # a voxel of 2 mm each way on the radius
    assert tab[60.0] == 0.0 or tab[60.0] < 2 * (55.0 - 40.0) + 3.0                                                       # off the edge of the thorax's column
    assert len(b["table"]) == 25 and b["table"][0]["d_mm"] == -60.0 and b["table"][-1]["d_mm"] == 60.0


def test_a_sweep_point_outside_a_body_gives_a_zero_diameter_and_names_that_body(two_bodies):
    prof = corridor.profile(two_bodies, 5.0, ds=[200.0])
    b = corridor.best(prof)
    assert b["best_min_diameter_mm"] == 0.0 and b["best_station"]["body"] in ("abdomen", "thorax")


def test_the_profile_starts_at_the_lsj_and_runs_up_through_the_abdomen_then_the_thorax(two_bodies):
    prof = corridor.profile(two_bodies, 5.0)
    rows = prof["rows"]
    assert rows[0]["body"] == "abdomen" and rows[-1]["body"] == "thorax"
    h = [r["height_above_lsj_mm"] for r in rows]
    assert h == sorted(h) and h[0] < 3.0 and h[-1] == pytest.approx(200.0, abs=3.0)
    at = corridor.profile_at(prof, 5.0)
    assert at[0]["height_above_lsj_mm"] < 3.0 and all(abs(a["diameter_mm"] - 80.0) < 4.0 for a in at[1:-1])


def test_the_forward_shift_is_the_best_d_less_the_sims_axis():
    axes = {"zero": {"LJC": -56.7, "TJC": -56.7, "CJC": -56.7}, "stance_lean": {"LJC": -31.8, "TJC": -27.8, "CJC": -17.4}}
    s = corridor.forward_shift(-5.0, axes)
    assert s["zero"]["CJC"] == pytest.approx(51.7) and s["stance_lean"]["CJC"] == pytest.approx(12.4) and s["stance_lean"]["LJC"] == pytest.approx(26.8)


def test_the_sim_axes_are_read_from_the_offsets_file():
    axes = corridor.sim_axes(json.loads((REPO / "data/envelope/trunk_offsets.json").read_text()))
    assert set(axes) == {"zero", "stance", "stance_lean"}
    assert axes["zero"]["TJC"] == pytest.approx(-56.719, abs=1e-3) and axes["stance"]["LJC"] == pytest.approx(-35.17, abs=1e-2)
    assert axes["stance_lean"]["CJC"] == pytest.approx(-17.369, abs=1e-3)


def test_the_committed_result_has_the_sweep_the_axes_and_a_ledger_per_body():
    res = json.loads((REPO / "data/envelope/corridor_result.json").read_text())
    assert res["required_skin_margin_mm"] == 5.0 and len(res["sweep"]) == 25
    assert res["best_min_diameter_mm"] == max(r["min_diameter_mm"] for r in res["sweep"])
    assert res["corridor_diameter_mm"] == pytest.approx(0.8 * res["best_min_diameter_mm"], rel=1e-9)        # the reservations file's diameter is null
    for pose in ("zero", "stance", "stance_lean"):
        for plane, x in res["sim_stack_axis_x_mm"][pose].items():
            assert res["forward_shift_of_best_d_mm"][pose][plane] == pytest.approx(res["best_d_mm"] - x, abs=1e-9)
    for n in ("abdomen", "thorax"):
        b = res["bodies"][n]
        assert b["free_volume_l"] < b["without_corridor"]["free_volume_l"] and b["occupied_volume_l"] > 0
        assert (REPO / b["ledger"]).exists() and (REPO / b["registry"]).exists()
