"""
Stage 2 T1: Camargo et al. 2021 ingestion. Synthetic cases pin the segmentation arithmetic; cases marked data_needed read
real trials from the raw folder (skipped when it is absent, so the suite stays runnable without the 20 GB download).

Run from the repo root:
    python -m pytest tests/test_camargo_ingest.py
"""
import sys
from pathlib import Path

import numpy as np
import pytest
import yaml

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "analysis"))
sys.path.insert(0, str(REPO / "sim" / "scripts"))

import gaitfeatures  # noqa: E402
import ingest_camargo as ic  # noqa: E402

SPEC = yaml.safe_load((REPO / "data" / "camargo2021" / "ingest_spec.yaml").read_text())
MAPPING = yaml.safe_load((REPO / "sim" / "scenarios" / "gait" / "camargo_mapping.yaml").read_text())
RAW = ic.raw_dir()
data_needed = pytest.mark.skipif(not (RAW / "AB06.zip").exists(), reason="Camargo raw archives not present")


# ---------- synthetic: contacts, phase normalisation, steady plateaus ----------

def force_trace(onsets, offsets, fs=1000.0, t_end=6.0, peak=700.0):
    t = np.arange(0, t_end, 1 / fs)
    f = np.zeros_like(t)
    for a, b in zip(onsets, offsets):
        m = (t >= a) & (t < b)
        f[m] = peak * np.sin(np.pi * (t[m] - a) / (b - a))
    return t, f


def test_contacts_find_known_events():
    t, f = force_trace([0.5, 1.6, 2.7], [1.2, 2.3, 3.4])
    ev = ic.contacts(t, f, threshold_n=20.0, min_duration_s=0.25)
    assert len(ev) == 3
    for (on, off), (a, b) in zip(ev, [(0.5, 1.2), (1.6, 2.3), (2.7, 3.4)]):
        assert abs(t[on] - a) < 0.03 and abs(t[off] - b) < 0.03  # sine ramps cross 20 N a little inside the edges


def test_contacts_reject_short_crossover_blips():
    t, f = force_trace([0.5, 1.6, 2.7], [1.2, 1.7, 3.4])  # the middle one lasts 0.1 s
    assert len(ic.contacts(t, f, 20.0, 0.25)) == 2


def test_phase_normalise_exact_on_a_ramp():
    t = np.linspace(0, 10, 2001)
    x = 3.0 * t + 1.0
    out = ic.phase_normalise(t, x, 2.0, 4.0, 101)
    assert out.shape == (101,)
    assert np.allclose(out, 3.0 * np.linspace(2.0, 4.0, 101) + 1.0, atol=1e-12)


def test_wrap_gap_is_zero_for_a_periodic_signal_and_flags_a_jump():
    ph = np.linspace(0, 1, 101)
    assert ic.wrap_gap(np.sin(2 * np.pi * ph)[:, None])[0] < 1e-12
    x = (np.sin(2 * np.pi * ph) + 0.5 * ph)[:, None]
    assert abs(ic.wrap_gap(x)[0] - 0.5) < 1e-12


def test_steady_plateaus_split_on_speed_change():
    t = np.arange(0, 30, 0.01)
    sp = np.where(t < 10, 1.4, np.where(t < 12, 1.4 + 0.1 * (t - 10), 1.6))
    segs = ic.steady_segments(t, sp, target=1.4, tol=0.01, ptp=0.001)
    assert len(segs) == 1 and abs(segs[0][0] - 0.0) < 0.02 and abs(segs[0][1] - 10.0) < 0.02
    assert ic.steady_segments(t, sp, target=1.6, tol=0.01, ptp=0.001)[0][0] > 11.9


# ---------- raw folder resolution ----------

def test_raw_dir_order_env_then_config_key_then_default(tmp_path, monkeypatch):
    cfg = tmp_path / "local_config.json"
    cfg.write_text('{"camargo_raw_dir": "/from/config"}')
    monkeypatch.delenv("CAMARGO_RAW_DIR", raising=False)
    assert ic.raw_dir(cfg) == Path("/from/config")
    monkeypatch.setenv("CAMARGO_RAW_DIR", "/from/env")
    assert ic.raw_dir(cfg) == Path("/from/env")
    monkeypatch.delenv("CAMARGO_RAW_DIR")
    cfg.write_text('{"sheet_key": "x"}')
    assert ic.raw_dir(cfg) == REPO / "data" / "camargo2021" / "raw"
    assert ic.raw_dir(tmp_path / "missing.json") == REPO / "data" / "camargo2021" / "raw"


# ---------- gait features on the sign mapping, with a mutation ----------

def synthetic_stride_model_angles():
    """One idealised stride in the MODEL convention (flexion positive), 101 phase points, stance to 60%."""
    ph = np.linspace(0, 1, 101)
    knee = 8 + 12 * np.exp(-((ph - 0.12) / 0.06) ** 2) + 55 * np.exp(-((ph - 0.72) / 0.07) ** 2)
    hip = 6.5 + 18.5 * np.cos(2 * np.pi * ph)
    ankle = -4 * np.exp(-((ph - 0.07) / 0.03) ** 2) + 12 * np.exp(-((ph - 0.40) / 0.12) ** 2) - 14 * np.exp(-((ph - 0.62) / 0.04) ** 2)
    add = 5 * np.exp(-((ph - 0.2) / 0.15) ** 2) - 6 * np.exp(-((ph - 0.75) / 0.1) ** 2)
    return {"hip_fe": hip[None], "knee": knee[None], "ankle": ankle[None], "hip_aa": add[None], "toe_off_phase": np.array([0.6])}


def test_features_pass_on_an_idealised_stride():
    assert gaitfeatures.check_all(synthetic_stride_model_angles()) == []


@pytest.mark.parametrize("joint", ["hip_fe", "knee", "ankle", "hip_aa"])
def test_flipping_one_sign_fails_its_feature(joint):
    a = synthetic_stride_model_angles()
    a[joint] = -a[joint]
    failed = gaitfeatures.check_all(a)
    assert failed, f"flipping {joint} was not detected"


# ---------- real data ----------

@pytest.fixture(scope="module")
def ab06():
    return ic.ingest_subject(RAW, "AB06", SPEC)


@data_needed
def test_read_table_decodes_a_matlab_table():
    import zipfile
    z = zipfile.ZipFile(RAW / "AB06.zip")
    name = next(n for n in z.namelist() if n.endswith("/treadmill/gcRight/treadmill_01_01.mat"))
    t = ic.read_table(z.read(name))
    assert list(t) == ["Header", "HeelStrike", "ToeOff"]
    assert t["Header"].size > 1000 and abs(np.diff(t["Header"]).mean() - 0.005) < 1e-6


@data_needed
def test_stride_counts_and_durations_are_plausible(ab06):
    for speed in SPEC["speeds_mps"]:
        s = ab06["strides"][speed]
        assert 15 <= s["n"] <= 60, (speed, s["n"])
        lo, hi = SPEC["stride_s"]
        assert lo <= s["duration_s"].min() and s["duration_s"].max() <= hi
        assert 0.9 < s["duration_s"].mean() < 1.25  # 1.4-1.6 m/s adult walking
    assert ab06["strides"][1.6]["duration_s"].mean() < ab06["strides"][1.4]["duration_s"].mean()


@data_needed
def test_phase_arrays_have_the_documented_shape_and_wrap(ab06):
    s = ab06["strides"][1.4]
    n = s["n"]
    assert s["ik"].shape == (n, 101, len(ic.IK_CHANNELS))
    assert s["id"].shape == (n, 101, len(ic.ID_CHANNELS))
    assert s["fp"].shape == (n, 2, 101, 7)  # foot (R, L); Fx Fy Fz CoPx CoPy CoPz mask
    ik = ic.IK_CHANNELS.index
    gap = ic.wrap_gap(s["ik"][:, :, ik("knee_angle_r")].T)
    assert np.median(gap) < 3.0  # deg: heel strike to heel strike of the same limb, not a loop but close
    assert not np.isnan(s["ik"]).any() and not np.isnan(s["id"]).any()


@data_needed
def test_units_are_degrees_newtons_and_metres(ab06):
    s = ab06["strides"][1.4]
    knee = s["ik"][:, :, ic.IK_CHANNELS.index("knee_angle_r")]
    assert -90 < knee.min() < -50 and knee.max() < 5  # degrees, knee_angle is negative flexion
    mz = s["id"][:, :, ic.ID_CHANNELS.index("ankle_angle_r_moment")]
    assert -250 < mz.min() < -60  # N m, not N m / kg
    fy = s["fp"][:, 0, :, 1]
    assert 1.0 < fy.max() / (ab06["mass_kg"] * 9.81) < 1.6  # N: peak vertical force 1.0 to 1.6 body weights
    cop = s["fp"][:, 0, :, 3:6]
    stance = s["fp"][:, 0, :, 6] > 0.5
    assert np.nanmax(np.abs(cop[stance][:, 1])) < 1e-6  # CoP is on the belt surface (y = 0)
    ty = s["ik"][:, :, ic.IK_CHANNELS.index("pelvis_ty")]
    assert 0.8 < ty.mean() < 1.2  # m


@data_needed
def test_stance_mask_follows_vertical_force(ab06):
    s = ab06["strides"][1.4]
    fy, mask = s["fp"][:, 0, :, 1], s["fp"][:, 0, :, 6] > 0.5
    assert (fy[mask] > SPEC["contact_force_n"] * 0.99).all() and (fy[~mask] <= SPEC["contact_force_n"] * 1.01).all()
    frac = mask.mean(axis=1)
    assert 0.5 < frac.mean() < 0.7  # stance is about 60% of the stride


@data_needed
def test_sign_mapping_passes_the_gait_feature_checks_and_one_flip_fails(ab06):
    ang = ic.model_angles(ab06["strides"][1.4], MAPPING)
    assert gaitfeatures.check_all(ang) == []
    for joint in ("knee", "ankle", "hip_fe"):
        bad = dict(ang)
        bad[joint] = -ang[joint]
        assert gaitfeatures.check_all(bad), f"flipped {joint} not detected"


@data_needed
def test_static_standing_pelvis_tilt_is_read(ab06):
    tilt = ab06["static_pelvis_tilt_deg"]
    assert tilt is not None and -15 < tilt < 15  # degrees; the T-pose tilt of a standing subject
    walking = ab06["strides"][1.4]["ik"][:, :, ic.IK_CHANNELS.index("pelvis_tilt")].mean()
    assert abs(walking - tilt) < 10


@data_needed
def test_hip_centre_in_the_dataset_pelvis_frame_is_read(ab06):
    h = ab06["hip_in_pelvis_os_m"]
    # AB06's scaled gait2392 pelvis: hips 73.7 mm behind and 68.9 mm below the pelvis origin, 87.1 mm to each side
    assert h == pytest.approx([-0.0737266, -0.0689296, 0.0870745], abs=1e-6)
