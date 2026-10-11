"""
Stage 2 T3c.5: where B's single-support CoP comes from, by segment group (stance leg, swing leg, pelvis and trunk), and the in-memory
model copies that swap in the dataset's segment masses. The partition is additive, so its pieces must add to the CoP.

Run from the repo root:
    python -m pytest tests/test_partition.py
"""
import sys
from pathlib import Path

import mujoco
import numpy as np
import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "sim" / "scripts"))
sys.path.insert(0, str(REPO / "analysis"))

import dynamics  # noqa: E402
import partition  # noqa: E402


@pytest.fixture(scope="module")
def model():
    return mujoco.MjModel.from_xml_path(str(REPO / "sim" / "models" / "freyja.xml"))


def moving_pose(model, seed=0):
    rng = np.random.default_rng(seed)
    q = np.zeros(model.nq)
    q[3] = 1.0
    q[2] = 0.97
    for j in range(model.njnt):
        if model.jnt_type[j] == mujoco.mjtJoint.mjJNT_HINGE:
            q[model.jnt_qposadr[j]] = rng.uniform(-0.2, 0.2)
    qd = rng.uniform(-0.8, 0.8, model.nv)
    qdd = rng.uniform(-2.0, 2.0, model.nv)
    return q, qd, qdd


def test_group_contributions_add_up_to_the_whole_body_cop(model):
    for seed in (0, 1, 2):
        q, qd, qdd = moving_pose(model, seed)
        qfrc = dynamics.inverse_frame(model, q, qd, qdd)
        full, pm, am = dynamics.cop_decomposition(model, q, qfrc)
        ankle = np.array([0.1, -0.09])
        parts = partition.cop_partition(model, q, qd, qdd, "foot_right", ankle_xy=ankle)
        assert sum(g["mass_fraction"] for g in parts.values()) == pytest.approx(1.0, abs=1e-12)
        total_com = sum(g["com_minus_ankle_xy"] for g in parts.values())
        total_dyn = sum(g["dynamic_xy"] for g in parts.values())
        assert ankle + total_com + total_dyn == pytest.approx(full[:2], abs=1e-6)
        # the CoM term alone is the whole-body CoM minus the ankle
        d = mujoco.MjData(model)
        d.qpos[:] = q
        mujoco.mj_kinematics(model, d)
        mujoco.mj_comPos(model, d)
        assert ankle + total_com == pytest.approx(d.subtree_com[0][:2], abs=1e-9)


def test_groups_are_stance_leg_swing_leg_and_pelvis_trunk_and_follow_the_stance_side(model):
    q, qd, qdd = moving_pose(model)
    right = partition.cop_partition(model, q, qd, qdd, "foot_right", ankle_xy=np.zeros(2))
    left = partition.cop_partition(model, q, qd, qdd, "foot_left", ankle_xy=np.zeros(2))
    assert set(right) == {"stance_leg", "swing_leg", "pelvis_trunk"}
    assert right["stance_leg"]["mass_fraction"] == pytest.approx(left["stance_leg"]["mass_fraction"], rel=1e-12)  # symmetric masses
    # swapping the stance side swaps which leg is which, so the two legs' contributions swap
    assert np.allclose(right["stance_leg"]["dynamic_xy"], left["swing_leg"]["dynamic_xy"])  # the same bodies, labelled the other way
    assert np.allclose(right["swing_leg"]["dynamic_xy"], left["stance_leg"]["dynamic_xy"])
    assert not np.allclose(right["stance_leg"]["dynamic_xy"], right["swing_leg"]["dynamic_xy"])


def test_a_static_pose_has_no_dynamic_term(model):
    q = np.zeros(model.nq); q[3] = 1.0; q[2] = 0.965
    parts = partition.cop_partition(model, q, np.zeros(model.nv), np.zeros(model.nv), "foot_right", ankle_xy=np.zeros(2))
    for g in parts.values():
        assert np.abs(g["dynamic_xy"]).max() < 1e-9


# ---- in-memory copies of the model with the dataset's segment masses

import datasetmass  # noqa: E402
import ingest_camargo as ic  # noqa: E402

RAW = ic.raw_dir()
data_needed = pytest.mark.skipif(not (RAW / "AB06.zip").exists(), reason="Camargo raw archives not present")

# a hand-made body table in the shape the parser returns: masses (kg) and centres of mass in the OpenSim segment frame
TABLE = {"pelvis": (10.0, (-0.07, 0.0, 0.0)), "femur_r": (8.0, (0.0, -0.17, 0.0)), "femur_l": (8.0, (0.0, -0.17, 0.0)),
         "tibia_r": (3.0, (0.0, -0.20, 0.0)), "tibia_l": (3.0, (0.0, -0.20, 0.0)),
         "talus_r": (0.1, (0, 0, 0)), "calcn_r": (1.0, (0.1, 0.03, 0)), "toes_r": (0.2, (0.03, 0.006, -0.018)),
         "talus_l": (0.1, (0, 0, 0)), "calcn_l": (1.0, (0.1, 0.03, 0)), "toes_l": (0.2, (0.03, 0.006, 0.018)),
         "torso": (36.0, (-0.03, 0.34, 0.0))}


def test_substituted_masses_follow_the_dataset_fractions_and_keep_the_total(model):
    total = float(model.body_mass.sum())
    copy = datasetmass.with_dataset_masses(model, TABLE, length_ratio=0.9, hip_in_pelvis=(-0.0737, -0.0689))
    assert float(copy.body_mass.sum()) == pytest.approx(total, rel=1e-12)
    M = sum(m for m, _ in TABLE.values())
    bid = lambda n: mujoco.mj_name2id(copy, mujoco.mjtObj.mjOBJ_BODY, n)
    assert copy.body_mass[bid("thigh_right")] == pytest.approx(total * 8.0 / M, rel=1e-12)
    assert copy.body_mass[bid("shank_left")] == pytest.approx(total * 3.0 / M, rel=1e-12)
    assert copy.body_mass[bid("foot_right")] == pytest.approx(total * 1.3 / M, rel=1e-12)  # talus + calcn + toes
    assert copy.body_mass[bid("pelvis")] == pytest.approx(total * 10.0 / M, rel=1e-12)
    trunk = [n for n in ("abdomen", "thorax", "head_and_neck", "upper_arm_right", "forearm_right", "hand_right", "upper_arm_left", "forearm_left", "hand_left")]
    assert sum(copy.body_mass[bid(n)] for n in trunk) == pytest.approx(total * 36.0 / M, rel=1e-12)


def test_limb_centres_of_mass_move_along_the_bone_and_the_original_model_is_untouched(model):
    before = model.body_mass.copy(), model.body_ipos.copy()
    copy = datasetmass.with_dataset_masses(model, TABLE, length_ratio=0.9, hip_in_pelvis=(-0.0737, -0.0689))
    bid = lambda n: mujoco.mj_name2id(copy, mujoco.mjtObj.mjOBJ_BODY, n)
    # OpenSim y (down the bone, negative) is the model's z; scaled by the leg-length ratio
    assert copy.body_ipos[bid("thigh_right")] == pytest.approx([0.0, 0.0, -0.17 * 0.9])
    assert copy.body_ipos[bid("shank_left")] == pytest.approx([0.0, 0.0, -0.20 * 0.9])
    assert np.array_equal(model.body_mass, before[0]) and np.array_equal(model.body_ipos, before[1])  # in memory only
    assert not np.array_equal(copy.body_mass, model.body_mass)


@data_needed
def test_the_real_osim_table_parses_with_the_expected_bodies():
    import zipfile
    table = datasetmass.read_body_table(zipfile.ZipFile(RAW / "AB06.zip"), "AB06")
    assert set(table) >= {"pelvis", "femur_r", "tibia_l", "calcn_r", "torso"}
    assert table["femur_r"][0] == pytest.approx(9.6645, abs=1e-3) and table["femur_r"][1][1] == pytest.approx(-0.17459, abs=1e-5)
