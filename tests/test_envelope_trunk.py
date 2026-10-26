"""Volume-extractor brief 5, step 0 and item 1: the hip diagnostic's Dumas offset, the sheet's trunk nodes, the trunk registration (CJC anchor candidates, stretch per
sub-segment, the Monte Carlo) and its committed result. Offline."""
import csv
import json
import sys
from pathlib import Path

import numpy as np
import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "tools"))

from envelope import anthro, masses, register, trunk  # noqa: E402

SNAP = REPO / "params" / "snapshot.csv"
RESULT = REPO / "data" / "envelope" / "trunk_registration.json"


@pytest.fixture(scope="module")
def sh():
    return register.sheet_nodes(SNAP)


# ---- step 0: the hip diagnostic expects the trochanterion 8 mm x k above the HJC ---------------------------------------------------

def _ansur(troch_mm):
    """A minimal ANSUR summary whose trochanterion, scaled to the sheet stature, sits at `troch_mm`."""
    return {"stature_mm": {"mean": 1700.0}, "landmarks": {"trochanterion": {"height_mm": {"mean": troch_mm}}, "lateral_femoral_epicondyle": {"height_mm": {"mean": 480.0}},
                                                          "lateral_malleolus": {"height_mm": {"mean": 65.0}}}}


def test_the_expected_trochanterion_offset_is_dumas_gt_8_mm_times_the_pelvis_scale(sh):
    d = register.diagnostics(sh, _ansur(sh.hjc + 8.0 * sh.k_pelvis))
    assert register.DUMAS_GT_ABOVE_HJC_MM == 8.0
    assert d["expected_trochanterion_above_hjc_mm"] == pytest.approx(8.0 * sh.k_pelvis)
    assert d["trochanterion_minus_expected_mm"] == pytest.approx(0.0, abs=1e-9)
    assert d["hjc_flag"] is False


def test_the_hip_flag_is_beyond_10_mm_of_the_expected_offset_in_either_direction(sh):
    e = 8.0 * sh.k_pelvis
    assert register.TROCH_OFFSET_FLAG_MM == 10.0
    assert register.diagnostics(sh, _ansur(sh.hjc + e + 9.9))["hjc_flag"] is False
    assert register.diagnostics(sh, _ansur(sh.hjc + e + 10.1))["hjc_flag"] is True
    assert register.diagnostics(sh, _ansur(sh.hjc + e - 10.1))["hjc_flag"] is True
    d = register.diagnostics(sh, _ansur(sh.hjc + e - 10.1))
    assert d["trochanterion_minus_expected_mm"] == pytest.approx(-10.1)


def test_the_old_zero_offset_figure_is_still_reported(sh):
    d = register.diagnostics(sh, _ansur(sh.hjc + 11.0))
    assert d["hjc_minus_scaled_trochanterion_mm"] == pytest.approx(-11.0)


# ---- the sheet's trunk nodes -------------------------------------------------------------------------------------------------------

def test_the_trunk_nodes_chain_up_from_the_lumbosacral_joint_by_the_sheets_lengths(sh):
    n = trunk.sheet_nodes(sh)
    assert n["hjc"] == sh.hjc and n["ljc"] == sh.ljc
    assert n["tjc"] - n["ljc"] == pytest.approx(127.092175438)
    assert n["cjc"] - n["tjc"] == pytest.approx(328.759098448)
    assert n["vertex"] - n["cjc"] == pytest.approx(265.738185008)


def test_the_zero_pose_top_is_below_the_stature_by_the_pelvis_non_verticality(sh):
    a = trunk.standing_head_top(sh, REPO)
    assert a["zero_pose_vertex_mm"] == pytest.approx(1690.342, abs=0.001)
    assert a["shortfall_mm"] == pytest.approx(9.658, abs=0.001)
    assert a["tilt_deg"] == 12.0
    # the shortfall is the vertical drop LJC to HJC at the design tilt (ADR 0038) minus the drop in the zero pose
    assert a["vertical_drop_at_tilt_mm"] == pytest.approx(sh.k_pelvis * (54.0 * np.sin(np.radians(12.0)) + 93.0 * np.cos(np.radians(12.0))))
    assert a["shortfall_mm"] == pytest.approx(a["vertical_drop_at_tilt_mm"] - a["zero_pose_drop_mm"], abs=0.01)


def test_the_dumas_c7_and_sternal_notch_offsets_scale_with_the_thorax(sh):
    t = masses.load_dumas_table1(REPO)
    s = 328.759098448 / 313.0
    assert trunk.c7_above_cjc_mm(t, sh) == pytest.approx(28.0 * s)
    assert trunk.sup_below_cjc_mm(t, sh) == pytest.approx(35.0 * s)


# ---- stretches ---------------------------------------------------------------------------------------------------------------------

SHEET = {"hjc": 871.0, "ljc": 968.0, "tjc": 1095.0, "cjc": 1424.0, "vertex": 1690.0}


def test_slope_one_mode_leaves_pelvis_and_abdomen_unstretched_and_puts_the_rest_on_the_thorax_and_head():
    m = trunk.mesh_nodes(SHEET, hjc_m=874.0, cjc_m=1400.0, top_m=1700.0, mode="slope1")
    assert m["ljc"] == pytest.approx(874.0 + 97.0) and m["tjc"] == pytest.approx(874.0 + 224.0)
    s = trunk.stretches(SHEET, m)
    assert s["pelvis"] == pytest.approx(1.0) and s["abdomen"] == pytest.approx(1.0)
    assert s["thorax"] == pytest.approx(329.0 / (1400.0 - 1098.0))
    assert s["head_neck"] == pytest.approx(266.0 / 300.0)


def test_uniform_mode_spreads_the_hjc_to_cjc_difference_over_pelvis_abdomen_and_thorax():
    m = trunk.mesh_nodes(SHEET, hjc_m=874.0, cjc_m=1400.0, top_m=1700.0, mode="uniform")
    s = trunk.stretches(SHEET, m)
    want = (1424.0 - 871.0) / (1400.0 - 874.0)
    assert s["pelvis"] == pytest.approx(want) and s["abdomen"] == pytest.approx(want) and s["thorax"] == pytest.approx(want)
    assert s["head_neck"] == pytest.approx(266.0 / 300.0)


def test_the_stretches_are_one_when_the_mesh_nodes_are_the_sheets():
    for mode in trunk.MODES:
        m = trunk.mesh_nodes(SHEET, hjc_m=871.0, cjc_m=1424.0, top_m=1690.0, mode=mode)
        assert all(v == pytest.approx(1.0) for v in trunk.stretches(SHEET, m).values())


def test_exceeds_flags_a_sub_segment_beyond_8_percent_and_names_it():
    assert trunk.exceeding({"pelvis": 1.0, "abdomen": 1.0, "thorax": 1.0799, "head_neck": 0.9201}) == []
    assert trunk.exceeding({"pelvis": 1.0, "abdomen": 1.0, "thorax": 1.0801, "head_neck": 0.9199}) == ["thorax", "head_neck"]


# ---- Monte Carlo -------------------------------------------------------------------------------------------------------------------

def test_monte_carlo_without_uncertainty_returns_the_nominal_stretches():
    out = trunk.monte_carlo(SHEET, hjc_m=874.0, cjc_m=1400.0, top_m=1700.0, sd_hjc=0.0, sd_cjc=0.0, mode="slope1", n=20, seed=0)
    nom = trunk.stretches(SHEET, trunk.mesh_nodes(SHEET, 874.0, 1400.0, 1700.0, "slope1"))
    for k, v in nom.items():
        assert out[k]["sd"] == pytest.approx(0.0, abs=1e-12) and out[k]["mean"] == pytest.approx(v)


def test_monte_carlo_is_reproducible_for_a_seed_and_the_cjc_spread_moves_thorax_and_head_in_opposite_directions():
    a = trunk.monte_carlo(SHEET, 874.0, 1400.0, 1700.0, sd_hjc=10.0, sd_cjc=10.0, mode="slope1", n=200, seed=0)
    b = trunk.monte_carlo(SHEET, 874.0, 1400.0, 1700.0, sd_hjc=10.0, sd_cjc=10.0, mode="slope1", n=200, seed=0)
    assert a == b
    assert a["thorax"]["sd"] > 0 and a["head_neck"]["sd"] > 0
    assert a["thorax"]["p2_5"] < a["thorax"]["mean"] < a["thorax"]["p97_5"]
    assert 0.0 <= a["thorax"]["fraction_beyond_8_percent"] <= 1.0


# ---- ANSUR landmarks added for the CJC cross-check ---------------------------------------------------------------------------------

def test_the_ansur_summary_carries_cervicale_and_suprasternale():
    assert anthro.COLUMNS["cervicale"] == "cervicaleheight" and anthro.COLUMNS["suprasternale"] == "suprasternaleheight"
    d = json.loads((REPO / "data/ansur2/ratios.json").read_text())
    c, s = d["landmarks"]["cervicale"], d["landmarks"]["suprasternale"]
    assert c["height_mm"]["mean"] == pytest.approx(1395.67, abs=0.01) and s["height_mm"]["mean"] == pytest.approx(1329.69, abs=0.01)
    assert c["ratio"]["mean"] == pytest.approx(0.85695, abs=1e-5)


# ---- the committed result ----------------------------------------------------------------------------------------------------------

@pytest.fixture(scope="module")
def res():
    return json.loads(RESULT.read_text())


def test_the_committed_result_names_every_anchor_candidate_and_both_modes(res):
    assert set(res["candidates"]) == {"nape_c7", "nape_as_cjc", "ansur_cervicale", "ansur_suprasternale"}
    for c in res["candidates"].values():
        assert set(c["modes"]) == {"slope1", "uniform"}
        for m in c["modes"].values():
            assert set(m["stretch"]) == {"pelvis", "abdomen", "thorax", "head_neck"}
            assert set(m["monte_carlo"]) >= {"thorax", "head_neck"}
    assert res["primary_candidate"] == "ansur_cervicale" and res["primary_mode"] == "slope1"      # Joe, memo 34 decisions 1 and 2
    assert res["primary_exceeding_8_percent"] == [] and res["stop_and_ask"] is False
    assert res["candidates"]["nape_c7"]["modes"]["slope1"]["exceeding_8_percent"] == ["thorax", "head_neck"]    # the brief's anchor, kept as a cross-check
    assert res["mesh"]["nape_vertex_id"] == 1491


def test_the_committed_result_is_what_a_fresh_run_produces(res):
    fresh = trunk.run(REPO, REPO / "data/makehuman/freyja-body-v2.obj")
    assert json.loads(json.dumps(fresh, sort_keys=True)) == res
