"""
Stage 2g T1: the gait spec option `pelvis_frame_offset: none | measured` (decisions/0004-hip-stop-pelvis-pose.md, point 2) and the per-subject static
Dumas tilt the ingestion stores for it.

Run from the repo root:
    python -m pytest tests/test_gait_frame_offset.py
"""
import json
import sys
from pathlib import Path

import numpy as np
import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "sim" / "scripts"))
sys.path.insert(0, str(REPO / "analysis"))

import gait  # noqa: E402
import ingest_camargo as ic  # noqa: E402

MANIFEST = REPO / "data" / "camargo2021" / "manifest.json"
PROCESSED = REPO / "data" / "camargo2021" / "processed" / "AB06.npz"
data_needed = pytest.mark.skipif(not (PROCESSED.exists() and MANIFEST.exists()), reason="processed Camargo arrays not present")


def test_none_gives_no_offset_and_measured_gives_the_dumas_tilt_minus_the_ik_pitch():
    info = {"static_dumas_tilt_deg": 12.5, "static_pelvis_pitch_deg": -1.0}
    assert gait.frame_offset_deg("none", info) == 0.0
    assert gait.frame_offset_deg("measured", info) == pytest.approx(13.5, abs=1e-12)
    assert gait.frame_offset_deg("measured", {"static_dumas_tilt_deg": 3.0, "static_pelvis_pitch_deg": 5.0}) == pytest.approx(-2.0, abs=1e-12)


def test_an_unknown_mode_or_a_manifest_without_the_tilt_is_an_error_not_a_silent_zero():
    with pytest.raises(gait.GaitError, match="pelvis_frame_offset"):
        gait.frame_offset_deg("dumas", {"static_dumas_tilt_deg": 1.0, "static_pelvis_pitch_deg": 0.0})
    with pytest.raises(gait.GaitError, match="static_dumas_tilt_deg"):
        gait.frame_offset_deg("measured", {"static_pelvis_pitch_deg": 0.0})  # a manifest from before Stage 2g
    with pytest.raises(gait.GaitError, match="static_dumas_tilt_deg"):
        gait.frame_offset_deg("measured", {"static_dumas_tilt_deg": None, "static_pelvis_pitch_deg": 0.0})  # a subject without static markers
    assert gait.frame_offset_deg("none", {}) == 0.0  # the old manifest is fine when no offset is asked for


def test_the_spec_option_reaches_every_task_and_defaults_to_none():
    manifest = {"subjects": {"S": {"strides": {"1.4": 2}, "static_dumas_tilt_deg": 12.0, "static_pelvis_pitch_deg": 0.0}}}
    spec = {"speeds_mps": [1.4], "root_rule": "pelvis_dataset", "cop_scale": 1.0, "trunk": "rigid"}
    t = gait._tasks(spec, manifest, "m.xml", "p", ["A_filtered"], 6.0, 0.0, None, False, False, False)
    assert {x["pelvis_frame_offset"] for x in t} == {"none"}
    t = gait._tasks({**spec, "pelvis_frame_offset": "measured"}, manifest, "m.xml", "p", ["A_filtered"], 6.0, 0.0, None, False, False, False)
    assert {x["pelvis_frame_offset"] for x in t} == {"measured"}


@data_needed
def test_the_ingestion_stored_the_static_dumas_tilt_beside_the_ik_pitch_for_every_subject():
    man = json.loads(MANIFEST.read_text())["subjects"]
    assert len(man) == 17
    tilt = np.array([m["static_dumas_tilt_deg"] for m in man.values()])
    pitch = np.array([m["static_pelvis_pitch_deg"] for m in man.values()])
    assert np.isfinite(tilt).all()
    # memo 23, D2: Dumas tilt 12.43 (SD 3.90), IK pitch -1.14, difference +13.57 (SD 2.62)
    assert tilt.mean() == pytest.approx(12.43, abs=0.01) and tilt.std(ddof=1) == pytest.approx(3.90, abs=0.01)
    assert (tilt - pitch).mean() == pytest.approx(13.57, abs=0.01) and (tilt - pitch).std(ddof=1) == pytest.approx(2.62, abs=0.01)
    z = np.load(PROCESSED)
    assert float(z["static_dumas_tilt_deg"]) == man["AB06"]["static_dumas_tilt_deg"]


def test_the_tilt_function_the_ingestion_uses_is_the_diagnostics_function():
    import snapshot_diag
    assert snapshot_diag.dumas_pelvic_tilt_deg is ic.dumas_pelvic_tilt_deg
    # a pelvis whose ASIS sit 0.1 m below and 0.2 m ahead of the PSIS midpoint: tilt = atan(0.1 / 0.2)
    ar, al = np.array([[0.1, 0.0, -0.2]]), np.array([[-0.1, 0.0, -0.2]])  # x lateral, y up, z forward(-): ASIS are ahead of the PSIS
    pr, pl = np.array([[0.05, 0.1, 0.0]]), np.array([[-0.05, 0.1, 0.0]])
    assert ic.dumas_pelvic_tilt_deg(ar, al, pr, pl)[0] == pytest.approx(np.degrees(np.arctan2(0.1, 0.2)), abs=1e-9)


def test_the_extract_passes_the_option_to_its_lumbosacral_tasks():
    import gait_extract
    manifest = {"subjects": {"S": {"strides": {"1.4": 1}, "static_dumas_tilt_deg": 12.0, "static_pelvis_pitch_deg": 0.0}}}
    assert {t["pelvis_frame_offset"] for t in gait_extract.lsj_tasks(["1.4"], 0, manifest)} == {"none"}
    assert {t["pelvis_frame_offset"] for t in gait_extract.lsj_tasks(["1.4"], 0, manifest, frame_offset="measured")} == {"measured"}
