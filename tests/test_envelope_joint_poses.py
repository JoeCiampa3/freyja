"""Hinge-chain poses (upper-arm characterization brief, T7; Joe's rulings 2026-11-14, points 2 and 4): the pose of an owner body in a host body's frame over the hinges between
them, built on the MuJoCo model with the convention and frame helpers of foreign.py. Offline; no envelope cache."""
import csv
import sys
from pathlib import Path

import numpy as np
import pytest
from scipy.spatial.transform import Rotation

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "tools"))

from envelope import foreign, joint_poses  # noqa: E402
from envelope.sheet import StopAndAsk  # noqa: E402


@pytest.fixture(scope="module")
def model():
    return foreign.load_model()


def snap():
    with open(REPO / "params" / "snapshot.csv", newline="", encoding="utf-8") as fh:
        return {r["placeholder"]: float(r["value"]) for r in csv.DictReader(fh)}


def test_the_chain_between_upper_arm_and_forearm_is_the_elbow_hinge_read_from_the_model(model):
    ch = joint_poses.hinge_chain(model, "upper_arm_right", "forearm_right")
    assert [j["name"] for j in ch] == ["elbow_right"]
    assert np.allclose(ch[0]["axis"], [0, -1, 0])
    assert ch[0]["range_deg"] == pytest.approx((-4.7, 150.0))


def test_the_shoulder_hinges_are_not_in_the_chain_and_a_body_not_below_the_host_stops(model):
    assert [j["name"] for j in joint_poses.hinge_chain(model, "upper_arm_right", "hand_right")] == ["elbow_right", "wrist_right"]
    with pytest.raises(StopAndAsk):
        joint_poses.hinge_chain(model, "forearm_right", "upper_arm_right")       # the host is below the owner
    with pytest.raises(StopAndAsk):
        joint_poses.hinge_chain(model, "upper_arm_right", "upper_arm_right")     # no hinge between a body and itself


def test_at_zero_the_forearm_frame_sits_the_sheet_upper_arm_length_below_the_host_origin_unrotated(model):
    L = snap()["upper_arm_right_length"] * 1000.0
    T = joint_poses.relative_transforms(model, "upper_arm_right", "forearm_right", ["elbow_right"], [[0.0]])[0]
    assert np.allclose(T[:3, :3], np.eye(3), atol=1e-12)
    assert np.allclose(T[:3, 3], [0.0, 0.0, -L], atol=1e-6)


@pytest.mark.parametrize("theta", [30.0, 90.0, 120.0, 157.0])
def test_flexion_is_the_analytic_rotation_about_the_hinge_with_the_polarity_files_sign_and_is_not_clamped(model, theta):
    L = snap()["upper_arm_right_length"] * 1000.0
    T = joint_poses.relative_transforms(model, "upper_arm_right", "forearm_right", ["elbow_right"], [[theta]])[0]
    R = Rotation.from_rotvec(np.radians(theta) * np.array([0.0, -1.0, 0.0])).as_matrix()     # the model's hinge axis, positive = flexion (polarity file sign +1)
    assert np.allclose(T[:3, :3], R, atol=1e-9)
    assert np.allclose(T[:3, 3], [0.0, 0.0, -L], atol=1e-6)                                   # the hinge is at the forearm body's origin
    tip = joint_poses.apply(T, [[0.0, 0.0, -250.0]])[0]
    assert tip[0] > 0                                                                         # flexion brings the hand forward (the file's why)


def test_157_degrees_is_past_the_models_limit_and_is_posed_there_not_at_150(model):
    a = joint_poses.relative_transforms(model, "upper_arm_right", "forearm_right", ["elbow_right"], [[150.0], [157.0]])
    ang = np.degrees(np.arccos(np.clip((np.trace(a[0][:3, :3].T @ a[1][:3, :3]) - 1) / 2, -1, 1)))
    assert ang == pytest.approx(7.0, abs=1e-9)


def test_the_probe_check_passes_on_the_model_and_the_polarity_file(model):
    T = joint_poses.relative_transforms(model, "upper_arm_right", "forearm_right", ["elbow_right"], [[30.0]])[0]
    joint_poses.check_probe_direction(model, "upper_arm_right", "forearm_right", "elbow_right", 30.0, T)


def test_mutation_a_broken_hinge_sign_fails_the_probe_check(model):
    bad = joint_poses.relative_transforms(model, "upper_arm_right", "forearm_right", ["elbow_right"], [[30.0]], polarity={"elbow_right": -1})[0]
    with pytest.raises(StopAndAsk, match="elbow_right"):
        joint_poses.check_probe_direction(model, "upper_arm_right", "forearm_right", "elbow_right", 30.0, bad)


def test_a_model_whose_hinge_axis_is_reversed_still_flexes_forward(model, tmp_path):
    """The model's own sign is measured with the file's probe (foreign.clinical_factor), so a reversed axis in the model is compensated, not followed."""
    xml = (REPO / "sim" / "models" / "freyja.xml").read_text(encoding="utf-8")
    old = '<joint name="elbow_right" type="hinge" axis="0 -1 0"'
    assert xml.count(old) == 1
    p = tmp_path / "freyja.xml"
    p.write_text(xml.replace(old, '<joint name="elbow_right" type="hinge" axis="0 1 0"'), encoding="utf-8")
    m2 = foreign.load_model(p)
    T = joint_poses.relative_transforms(m2, "upper_arm_right", "forearm_right", ["elbow_right"], [[60.0]])[0]
    assert joint_poses.apply(T, [[0.0, 0.0, -250.0]])[0][0] > 0
    joint_poses.check_probe_direction(m2, "upper_arm_right", "forearm_right", "elbow_right", 60.0, T)


def test_a_joint_outside_the_chain_is_refused(model):
    with pytest.raises(StopAndAsk, match="wrist_right"):
        joint_poses.relative_transforms(model, "upper_arm_right", "forearm_right", ["wrist_right"], [[10.0]])


def test_the_left_side_is_refused(model):
    with pytest.raises(NotImplementedError):
        joint_poses.relative_transforms(model, "upper_arm_left", "forearm_left", ["elbow_left"], [[10.0]])


def test_foreign_py_is_imported_not_copied():
    src = (REPO / "tools" / "envelope" / "joint_poses.py").read_text(encoding="utf-8")
    assert "from .foreign import" in src or "from . import foreign" in src
    for name in ("def clinical_factor", "def _probe_sign", "def _transforms", "def load_polarity"):
        assert name not in src
