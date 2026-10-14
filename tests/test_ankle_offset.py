"""
Stage 2e T3: the per-joint `offset` field of `camargo_mapping.yaml`, read by `retarget.Cycle`, and the criterion that sets its value for the ankle.

Convention under test: the model's hinge angle in degrees is `sign * dataset angle + offset` (offset optional, default 0, in the model's own positive
direction: dorsiflexion for the ankle, so a negative ankle offset tips the foot toe-down).

Run from the repo root:
    python -m pytest tests/test_ankle_offset.py
"""
import copy
import sys
from pathlib import Path

import mujoco
import numpy as np
import pytest
import yaml

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "analysis"))
sys.path.insert(0, str(REPO / "sim" / "scripts"))

import foot_pitch as fp  # noqa: E402
import ingest_camargo as ic  # noqa: E402
import leanpose  # noqa: E402
import retarget  # noqa: E402

MAPPING_FILE = REPO / "sim" / "scenarios" / "gait" / "camargo_mapping.yaml"
MAPPING = yaml.safe_load(MAPPING_FILE.read_text(encoding="utf-8"))
FEET = {"foot_right": "ankle_pdflex_right", "foot_left": "ankle_pdflex_left"}


def _without_offsets(mapping):
    m = copy.deepcopy(mapping)
    for spec in m["joints"].values():
        spec.pop("offset", None)
    return m


@pytest.fixture(scope="module")
def model():
    return mujoco.MjModel.from_xml_path(str(REPO / "sim" / "models" / "freyja.xml"))


@pytest.fixture(scope="module")
def stand(model):
    return leanpose.solve_lean(model, 0.0, FEET).qpos


def _ik():
    """A synthetic walking-like input: every joint channel carries a different sinusoid, so a mix-up of channels shows."""
    names = ic.IK_CHANNELS
    t = np.linspace(0, 2 * np.pi, 101)
    ik = np.zeros((101, len(names)))
    for i, n in enumerate(names):
        ik[:, i] = (3.0 + 0.7 * i) * np.sin(t + 0.3 * i) * (1.0 if n.startswith(("hip", "knee", "ankle", "subtalar")) else 0.0)
    ik[:, names.index("pelvis_rotation")] = 90.0
    ik[:, names.index("pelvis_ty")] = 0.97
    ik[:, names.index("pelvis_tx")] = 0.0
    return ik


def _cycle(model, stand, mapping):
    return retarget.Cycle(model, mapping, stand, _ik(), 1.1, scale=0.95)


def _adr(model, joint):
    return model.jnt_qposadr[mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_JOINT, joint)]


def test_the_field_is_optional_and_zero_changes_nothing(model, stand):
    base = _without_offsets(MAPPING)
    zero = copy.deepcopy(base)
    for spec in zero["joints"].values():
        spec["offset"] = 0.0
    qa, va, aa = _cycle(model, stand, base).grid()
    qb, vb, ab = _cycle(model, stand, zero).grid()
    for a, b in ((qa, qb), (va, vb), (aa, ab)):
        assert np.max(np.abs(a - b)) <= 1e-9


def test_an_offset_shifts_that_joints_angle_by_the_offset_and_nothing_else(model, stand):
    base = _without_offsets(MAPPING)
    off = copy.deepcopy(base)
    off["joints"]["ankle_pdflex_right"]["offset"] = -3.4
    qa, va, aa = _cycle(model, stand, base).grid()
    qb, vb, ab = _cycle(model, stand, off).grid()
    adr = _adr(model, "ankle_pdflex_right")
    assert np.max(np.abs((qb[:, adr] - qa[:, adr]) - np.deg2rad(-3.4))) <= 1e-9
    same = [i for i in range(qa.shape[1]) if i not in (adr, 2)]  # every other coordinate except the root height (qpos 2), which the lowest-foot rule moves
    assert np.max(np.abs(qb[:, same] - qa[:, same])) <= 1e-9
    assert np.max(np.abs(qb[:, 2] - qa[:, 2])) < 0.01  # the root height follows the foot by millimetres, not more
    assert np.max(np.abs(vb[:, adr] - va[:, adr])) <= 1e-9 and np.max(np.abs(ab[:, adr] - aa[:, adr])) <= 1e-9  # a constant has no derivative


def test_the_offset_acts_after_the_sign_so_it_is_in_the_models_direction(model, stand):
    """A joint with sign -1 (the knee) and an offset of +2 moves the model angle by +2, not -2."""
    base = _without_offsets(MAPPING)
    off = copy.deepcopy(base)
    off["joints"]["knee_right"]["offset"] = 2.0
    qa, _, _ = _cycle(model, stand, base).grid()
    qb, _, _ = _cycle(model, stand, off).grid()
    adr = _adr(model, "knee_right")
    assert np.max(np.abs((qb[:, adr] - qa[:, adr]) - np.deg2rad(2.0))) <= 1e-9


def test_a_negative_ankle_offset_tips_the_sole_toe_down_by_that_many_degrees(model, stand):
    """The sign convention in the mapping's comment: at a standing input the model's sole pitch (toe-up positive) is the offset."""
    ik = np.zeros((101, len(ic.IK_CHANNELS)))
    ik[:, ic.IK_CHANNELS.index("pelvis_rotation")] = 90.0
    ik[:, ic.IK_CHANNELS.index("pelvis_ty")] = 0.97
    m = copy.deepcopy(_without_offsets(MAPPING))
    for j in ("ankle_pdflex_right", "ankle_pdflex_left"):
        m["joints"][j]["offset"] = -3.4
    c = retarget.Cycle(model, m, stand, ik, 1.0, scale=1.0)
    q = c.grid()[0][0]
    for foot in FEET:
        assert fp.sole_pitch_deg(model, q, foot) == pytest.approx(-3.4, abs=1e-6)


# ---- the criterion and the choice of the value

def _rows(per_subject):
    """per_subject: {subject: {dec: [model pitches]}} -> rows as foot_pitch.subject_rows gives them (single support)."""
    return [dict(subject=s, dec=d, model=v, data=0.0) for s, decs in per_subject.items() for d, vals in decs.items() for v in vals]


def test_the_criterion_is_minus_the_subject_averaged_model_pitch_over_deciles_three_and_four():
    # two subjects; subject A has three frames in the window, B one: the subjects count once each
    rows = _rows({"A": {2: [2.0, 2.0], 3: [5.0], 4: [99.0]}, "B": {2: [4.0], 5: [99.0]}})
    mean = fp.window_mean_model(rows, (2, 3))
    assert mean == pytest.approx(0.5 * (3.0 + 4.0))
    assert fp.criterion_offset(rows, (2, 3)) == pytest.approx(-3.5)


def test_the_default_is_kept_when_the_criterion_is_within_a_degree_of_it_and_otherwise_the_criterion_is_used_rounded_to_a_tenth():
    assert fp.choose_offset(-3.04, default=-3.4, tol=1.0) == (-3.4, "default")
    assert fp.choose_offset(-4.4, default=-3.4, tol=1.0) == (-3.4, "default")  # exactly 1.0 away is within
    assert fp.choose_offset(-2.3, default=-3.4, tol=1.0) == (-2.3, "criterion")
    assert fp.choose_offset(-4.5123, default=-3.4, tol=1.0) == (-4.5, "criterion")


def test_the_criterion_value_chosen_after_applying_it_leaves_the_pitch_flat_by_the_difference():
    rows = _rows({"A": {2: [3.0], 3: [3.0]}})
    crit = fp.criterion_offset(rows, (2, 3))
    shifted = [dict(r, model=r["model"] + crit) for r in rows]
    assert fp.window_mean_model(shifted, (2, 3)) == pytest.approx(0.0, abs=1e-12)


# ---- the mapping as authored

def test_only_the_two_ankles_carry_an_offset_and_it_is_the_same_on_both_sides():
    offs = {j: s["offset"] for j, s in MAPPING["joints"].items() if "offset" in s}
    assert set(offs) == {"ankle_pdflex_right", "ankle_pdflex_left"}
    assert offs["ankle_pdflex_right"] == offs["ankle_pdflex_left"]
    assert -6.0 <= offs["ankle_pdflex_right"] <= -1.0  # a foot-pitch convention difference of a few degrees (memo11), not a gait feature
    assert round(offs["ankle_pdflex_right"], 1) == offs["ankle_pdflex_right"]


def test_the_mapping_states_the_offsets_sign_convention_in_its_comment():
    text = MAPPING_FILE.read_text(encoding="utf-8")
    assert "offset" in text and "sign * dataset angle + offset" in text and "toe-down" in text


# ---- the diagnostic that compares A's torques with and without the offset

def test_the_effect_statistics_compare_peak_torques_stride_by_stride_and_frame_by_frame():
    import gait_diag as gd
    n = 100
    base = np.sin(np.linspace(0, 2 * np.pi, n))
    base = base / np.abs(base).max()  # the sampled peak is exactly 1
    S0 = [{"subject": "A", "tau": {"knee_right": 10 * base}}, {"subject": "B", "tau": {"knee_right": 20 * base}}]
    S1 = [{"subject": "A", "tau": {"knee_right": 10 * base + 0.5}}, {"subject": "B", "tau": {"knee_right": 21 * base}}]
    e = gd.offset_effect_stats(S0, S1, ["knee_right"])["knee_right"]
    assert e["n"] == 2
    assert e["max_frame_abs_diff"] == pytest.approx(1.0)  # B: |1 * sin| at its peak, A: 0.5
    assert e["max_peak_diff"] == pytest.approx(1.0) and e["mean_peak_diff"] == pytest.approx(0.5 * (0.5 + 1.0))
    assert e["p95_without"] == pytest.approx(np.percentile([10, 20], 95), rel=1e-3) and e["max_with"] == pytest.approx(21.0, rel=1e-3)


def test_mapping_without_offsets_removes_every_offset_and_nothing_else():
    m = {"frame": {"x": 1}, "joints": {"a": {"dataset": "p", "sign": 1, "offset": -3.4}, "b": {"dataset": "q", "sign": -1}}}
    out = retarget.mapping_without_offsets(m)
    assert out["joints"] == {"a": {"dataset": "p", "sign": 1}, "b": {"dataset": "q", "sign": -1}} and out["frame"] == {"x": 1}
    assert m["joints"]["a"]["offset"] == -3.4  # the input is untouched
