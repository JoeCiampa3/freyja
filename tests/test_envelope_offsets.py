"""Volume-extractor brief 7, item 2: where the sim's trunk stack stands against the mesh trunk centre line at the LJC, TJC, CJC and SJC planes, in the zero pose and in the design stance
(12 degrees of pelvis tilt, lumbosacral extension 12 degrees, ADR 0004). A report: nothing in the sim changes."""
import json
import sys
from pathlib import Path

import numpy as np
import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "tools"))

from envelope import field, frames, offsets  # noqa: E402
from envelope.synthetic import frustum  # noqa: E402

ENV = REPO / "data" / "envelope"
CACHE = ENV / "cache"
SNAPSHOT = REPO / "params" / "snapshot.csv"
HJC_X = frames.hjc_x_in_pelvis_mm(SNAPSHOT)
HJC_Z = 97.6824158329                                                         # the model's pelvis-to-hip drop, mm (thigh_right_pos_z)
built = pytest.mark.skipif(not (CACHE / "head_neck.npz").exists() or "model_to_segment_mm" not in field.Segment.load(CACHE / "head_neck.npz").meta,
                           reason="the built segments are a gitignored cache (fy envelope build)")


def model():
    return offsets.load_model()


def test_zero_pose_stack_stands_hjc_x_behind_the_hip_on_one_vertical():
    s = offsets.sim_stack(model(), offsets.zero_qpos(model()))
    for k in ("ljc", "tjc", "cjc"):
        assert s[k]["x"] == pytest.approx(-HJC_X, abs=1e-6) and s[k]["y"] == pytest.approx(0.0, abs=1e-9)
    assert s["ljc"]["z"] == pytest.approx(HJC_Z, abs=1e-6)
    assert s["tjc"]["z"] - s["ljc"]["z"] == pytest.approx(127.092175438, abs=1e-6) and s["cjc"]["z"] - s["tjc"]["z"] == pytest.approx(328.759098448, abs=1e-6)
    assert s["sjc"]["point_x"] - s["cjc"]["x"] == pytest.approx(13.8136749663, abs=1e-6) and s["sjc"]["z"] - s["cjc"]["z"] == pytest.approx(-77.5690978875, abs=1e-6)


def test_design_stance_is_the_pelvis_rotated_about_the_hip_and_the_trunk_plumb():
    m = model()
    s = offsets.sim_stack(m, offsets.stance_qpos(m, 12.0))
    th = np.radians(12.0)
    x = -HJC_X * np.cos(th) + HJC_Z * np.sin(th)                             # the zero-pose LSJ (-56.7, 97.7) rotated forward by the tilt about the hip
    z = HJC_X * np.sin(th) + HJC_Z * np.cos(th)
    assert s["ljc"]["x"] == pytest.approx(x, abs=0.01) and s["ljc"]["z"] == pytest.approx(z, abs=0.01)
    assert z - HJC_Z == pytest.approx(9.67, abs=0.02)                         # memo 34's 9.66 mm
    for k in ("tjc", "cjc"):
        assert s[k]["x"] == pytest.approx(s["ljc"]["x"], abs=1e-6)            # the trunk stack is vertical
    assert s["tjc"]["z"] - s["ljc"]["z"] == pytest.approx(127.092175438, abs=1e-6)
    assert -35.5 < s["ljc"]["x"] < -34.5 and 107.0 < s["ljc"]["z"] < 108.0     # ADR 0004: about 34 forward and 107.5 below at 12.43 degrees


def test_the_centroid_of_a_section_is_the_centre_of_an_offset_cylinder():
    v, f = frustum(40, 40, 60, -360)
    seg = field.build_segment(v + np.array([7.0, -3.0, 0.0]), f, length=300.0, voxel=2.0, z_top=0.0, margin=40.0)
    c = offsets.section_centroid(seg, 100.0)
    assert c["x"] == pytest.approx(7.0, abs=0.5) and c["y"] == pytest.approx(-3.0, abs=0.5) and c["area_mm2"] == pytest.approx(np.pi * 40 ** 2, rel=0.01)


@built
def test_the_report_is_sim_less_mesh_and_matches_the_committed_file():
    rep = offsets.report(REPO, CACHE)
    zero = rep["poses"]["zero"]["planes"]
    for plane in ("ljc", "tjc", "cjc", "sjc"):
        for e in zero[plane]["mesh"]:
            assert e["offset_x_mm"] == pytest.approx(zero[plane]["sim"]["x"] - e["centroid_x_mm"], abs=1e-9)
            assert e["offset_y_mm"] == pytest.approx(zero[plane]["sim"]["y"] - e["centroid_y_mm"], abs=1e-9)
    e = zero["tjc"]["mesh"][1]                                                   # the skin margin at the stack point, against the body field read directly
    thorax = field.Segment.load(CACHE / "thorax.npz")
    assert e["body"] == "thorax" and e["skin_margin_at_stack_mm"] == pytest.approx(
        float(thorax.signed_distance([[zero["tjc"]["sim"]["x"], zero["tjc"]["sim"]["y"], -e["station_mm"]]])[0]), abs=1e-3)
    assert len(zero["ljc"]["mesh"]) == 2 and len(zero["cjc"]["mesh"]) == 2        # a plane is the boundary of two bodies: both are reported
    st, ln = rep["poses"]["stance"]["planes"], rep["poses"]["stance_lean"]["planes"]              # the lean about the ankle (a sensitivity) tips the stack forward with height
    assert ln["cjc"]["sim"]["x"] > ln["tjc"]["sim"]["x"] > ln["ljc"]["sim"]["x"] > st["ljc"]["sim"]["x"] - 5.0 and ln["cjc"]["sim"]["x"] > st["cjc"]["sim"]["x"]
    assert ln["tjc"]["sim"]["x"] < ln["sjc"]["sim"]["x"] < ln["cjc"]["sim"]["x"]                   # the thorax axis at the SJC's height lies between the TJC and CJC origins
    assert rep["poses"]["stance"]["rise_mm"] == pytest.approx(9.67, abs=0.02)
    assert rep["poses"]["stance"]["tilt_deg"] == 12.0 and rep["mesh_hip_line_x_mm"] == pytest.approx(field.Segment.load(CACHE / "pelvis.npz").meta["mesh_hip_line_x_mm"])
    committed = json.loads((ENV / "trunk_offsets.json").read_text())
    assert json.loads(json.dumps(rep, sort_keys=True)) == {k: v for k, v in committed.items() if k != "generated_by"}
