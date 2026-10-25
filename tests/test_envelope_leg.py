"""Volume-extractor brief 2: the Ruler anchors, the knee-anchor choice, the three-segment pipeline on the real mesh (slow) and the CLI."""
import json
import subprocess
import sys
from pathlib import Path

import numpy as np
import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "tools"))

from envelope import ruler, trial  # noqa: E402
from envelope.sheet import StopAndAsk  # noqa: E402

OBJ = REPO / "data" / "makehuman" / "freyja-body-v1.obj"


# ---- Ruler loops -------------------------------------------------------------------------------------------------------------------

def test_loop_stats_of_a_tilted_square_loop():
    # a unit-ish square loop of side 100 mm tilted 30 degrees about x, centred at height 200
    a = np.radians(30)
    P = np.array([[-50, -50, 0], [50, -50, 0], [50, 50, 0], [-50, 50, 0]], float)
    R = np.array([[1, 0, 0], [0, np.cos(a), -np.sin(a)], [0, np.sin(a), np.cos(a)]])
    V = P @ R.T + [10, 20, 200]
    s = ruler.loop_stats(V, [0, 1, 2, 3])
    assert abs(s["length_mm"] - 400) < 1e-9 and abs(s["tilt_deg"] - 30) < 1e-6
    assert abs(s["z_mm"] - 200) < 1e-9 and np.allclose(s["centroid_xy_mm"], [10, 20])


def test_chord_stats():
    V = np.array([[0, 0, 500.0], [30, 40, 100.0]])
    c = ruler.chord_stats(V, [0, 1])
    assert c["top_z_mm"] == 500 and c["bottom_z_mm"] == 100 and abs(c["length_mm"] - np.sqrt(30 ** 2 + 40 ** 2 + 400 ** 2)) < 1e-9


def test_the_tracked_ruler_file_names_the_loops_and_chords_the_trial_uses():
    d = ruler.load(REPO)
    for k in ruler.KEYS.values():
        assert k in d
    assert len(d[ruler.KEYS["knee"]]) > 2 and len(d[ruler.KEYS["upperleg_height"]]) == 2


def test_missing_ruler_file_stops(tmp_path):
    with pytest.raises(StopAndAsk, match="ruler_measures"):
        ruler.load(tmp_path)


# ---- the real mesh -----------------------------------------------------------------------------------------------------------------

@pytest.fixture(scope="module")
def inp_feats():
    inp = trial.load_inputs(REPO, OBJ)
    return inp, trial.find_features(inp)


def test_the_four_knee_estimates_are_all_reported_and_the_ruler_one_is_the_loop_plus_the_ansur_offset(inp_feats):
    inp, f = inp_feats
    e = f["kjc_estimates_mm"]
    off = inp.ansur["epicondyle_minus_midpatella"]["ratio"]["mean"] * inp.stature_mesh
    assert abs(e["ruler_loop_plus_ansur_offset"] - (inp.ruler["knee"]["z_mm"] + off)) < 1e-9
    assert abs(e["ansur_ratio"] - inp.ansur["landmarks"]["lateral_femoral_epicondyle"]["ratio"]["mean"] * inp.stature_mesh) < 1e-9
    assert e["breadth_peak"] is None            # this mesh has no knee-breadth feature (memo 28)


def test_ankle_anchor_is_the_ansur_ratio_because_ansur_has_no_loop_offset(inp_feats):
    inp, f = inp_feats
    reg = trial.make_registration(inp, f, "ruler")
    assert abs(reg.mesh_nodes["ajc"] - f["ajc_estimates_mm"]["ansur_ratio"]) < 1e-9


def test_each_knee_source_changes_only_the_knee_node(inp_feats):
    inp, f = inp_feats
    regs = {s: trial.make_registration(inp, f, s) for s in ("ruler", "ansur", "chords")}
    for n in ("ajc", "hjc"):
        assert len({round(r.mesh_nodes[n], 6) for r in regs.values()}) == 1
    assert len({round(r.mesh_nodes["kjc"], 3) for r in regs.values()}) == 3
    assert regs["ruler"].knee_source == "ruler"


def test_breadth_anchor_stops_when_the_mesh_has_no_such_feature(inp_feats):
    inp, f = inp_feats
    with pytest.raises(StopAndAsk, match="no knee-breadth feature"):
        trial.make_registration(inp, f, "breadth")


def test_unknown_knee_source_is_rejected(inp_feats):
    inp, f = inp_feats
    with pytest.raises(ValueError):
        trial.make_registration(inp, f, "guess")


def test_stretch_of_each_sub_segment_follows_from_the_anchor(inp_feats):
    inp, f = inp_feats
    for src in ("ruler", "ansur", "chords"):
        reg = trial.make_registration(inp, f, src)
        st = reg.axial.stretches()
        m, sh = reg.mesh_nodes, inp.sheet
        assert abs(st["thigh"] - sh.thigh_length / (m["hjc"] - m["kjc"])) < 1e-9
        assert abs(st["shank"] - sh.shank_length / (m["kjc"] - m["ajc"])) < 1e-9


def test_the_mesh_is_left_right_symmetric_enough_to_mirror_the_left_leg_ruler_loops(inp_feats):
    inp, f = inp_feats
    r = f["raster"]
    from scipy import ndimage
    for z in (200.0, 500.0, 750.0):
        a_r = r.right_section(z, 0.0)[0]
        L = r.layer(z)
        yc = r.o[1] + r.h * (np.arange(L.shape[1]) + 0.5)
        left = L & (yc[None, :] > 0)
        lab, n = ndimage.label(left)
        a_l = ndimage.sum(left, lab, range(1, n + 1)).max() * r.h ** 2
        assert abs(a_r - a_l) / a_l < 0.01, z


@pytest.mark.slow
def test_three_segments_build_with_the_sheet_lengths_and_the_masses_close(inp_feats):
    inp, f = inp_feats
    reg = trial.make_registration(inp, f, "ruler")
    for name, length in (("shank", inp.sheet.shank_length), ("foot", inp.sheet.ajc)):
        r = trial.build_segment(inp, f, reg, name, 4.0)          # 4 mm voxels: a quick structural check, not the trial's resolution
        assert abs(r.seg.length - length) < 1e-6
        assert r.checks["boundary_edges_near_segment"] == 0 and r.checks["seed_inside_region"]
        assert r.seg.volume() > 0


# ---- CLI ---------------------------------------------------------------------------------------------------------------------------

def run_cli(*args):
    return subprocess.run([sys.executable, str(REPO / "tools" / "fy"), "envelope", *args], capture_output=True, text=True, cwd=REPO)


@pytest.mark.skipif(not (REPO / "data" / "ansur2" / "raw" / "ANSUR_II_FEMALE_Public.csv").exists(), reason="the raw ANSUR II CSV stays outside git")
def test_cli_ratios_regenerates_the_tracked_summary_byte_for_byte():
    p = REPO / "data" / "ansur2" / "ratios.json"
    before = p.read_bytes()
    r = run_cli("ratios")
    assert r.returncode == 0 and p.read_bytes() == before
