"""Foreign components (volume-extractor brief 6, item 5): the poses of a part that is fixed to another body (the owner, e.g. the pelvis) in the frame of the host segment (e.g. the right
thigh) as the joints between them move, built on the MuJoCo model.

For each joint-angle sample the model is put at qpos0 with the sampled hinges set, `mj_kinematics` runs, and the part's pose in the host body frame is
    T_host_part(q) = inv(T_world_host) @ T_world_owner @ T_owner_part
with T_owner_part the part's static placement in the owner body's frame. Joint names, axes, order and ranges are read from the model; nothing is assumed about the order of the hip's
hinges (MuJoCo composes the hinges of one body in the order the model lists them). Angles are degrees in the clinical sign of `checks/joint_polarity.yaml` (hip flexion, adduction and
internal rotation positive); the model's own sign of each hinge is measured with that file's probe and the sample is flipped if they disagree, so the file, not the axis arithmetic, decides.

Frames. The owner placement is in the owner's *model* body frame (origin at the body origin, axes parallel to the world at q = 0): for the pelvis that is the lumbosacral joint, which is
not the origin of the oracle's pelvis body (that one sits on the knee's vertical line; the model's pelvis origin is `thigh_<side>_pos_x` behind the hip). The host frame is the oracle
segment frame of the thigh: the model's thigh body (origin at the hip joint centre, axes parallel to the world at q = 0). The poses CSV is the schema of `oracle.read_poses`.
Right side only: the left side's convention is an open item (the sampling is built for both).
"""
from __future__ import annotations

import csv
import itertools
import warnings
from pathlib import Path

import numpy as np
import yaml
from scipy.spatial.transform import Rotation

from . import oracle
from .sheet import StopAndAsk

REPO = Path(__file__).resolve().parents[2]
MODEL_FILE = REPO / "sim" / "models" / "freyja.xml"           # the model the sim runs (sim/scripts/simrun.py: MODEL_FILE)
POLARITY_FILE = REPO / "checks" / "joint_polarity.yaml"
HIP_JOINTS = ("hip_fe", "hip_aa", "hip_ier")
SWEEP_STEP_DEG = 5.0              # the brief: single-axis sweeps over each full range at 5 degree steps
GRID_STEP_DEG = 15.0              # and the three-axis grid at 15 degree steps over the limits
PROBE_RAD = 0.1                   # as check.mjcf.joint_signs
BODY_NAMES = {"thigh_R": "thigh_right", "thigh_L": "thigh_left", "shank_R": "shank_right", "shank_L": "shank_left", "foot_R": "foot_right", "foot_L": "foot_left"}


def load_model(path=None):
    import mujoco
    return mujoco.MjModel.from_xml_path(str(path or MODEL_FILE))


def body_name(name: str) -> str:
    """The model's body name for an oracle segment name (thigh_R -> thigh_right); other names pass through."""
    return BODY_NAMES.get(name, name)


def load_polarity(path=None) -> dict:
    spec = yaml.safe_load(Path(path or POLARITY_FILE).read_text(encoding="utf-8"))
    return {k: int(v["sign"]) for k, v in spec["joints"].items()}, {k: v for k, v in spec["joints"].items()}


def _body_id(model, name):
    import mujoco
    i = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_BODY, body_name(name))
    if i < 0:
        raise KeyError(f"the model has no body {body_name(name)!r}")
    return i


def joints_of(model, host: str) -> list:
    """The hinges of a body, in the order the model lists them (the order MuJoCo composes them): name, qpos address, axis in the body frame, anchor, range in degrees."""
    import mujoco
    b = _body_id(model, host)
    out = []
    for j in range(model.njnt):
        if model.jnt_bodyid[j] == b and model.jnt_type[j] == mujoco.mjtJoint.mjJNT_HINGE:
            lim = np.degrees(model.jnt_range[j]) if model.jnt_limited[j] else None
            out.append({"name": mujoco.mj_id2name(model, mujoco.mjtObj.mjOBJ_JOINT, j), "id": j, "qpos": int(model.jnt_qposadr[j]), "axis": model.jnt_axis[j].copy(),
                        "anchor": model.jnt_pos[j].copy(), "range_deg": None if lim is None else (float(lim[0]), float(lim[1]))})
    return out


def check_hip_chain(model, host: str, tol=1e-9) -> list:
    """The stop condition of the brief: the hip must be three serial hinges about the hip joint centre (anchors at the body origin), the host body must have no rotation of its own and
    parent the owner at q = 0 with parallel axes. Returns the hinges; raises StopAndAsk otherwise."""
    hj = joints_of(model, host)
    names = [j["name"] for j in hj]
    if len(hj) != 3 or not all(any(n.startswith(h) for n in names) for h in HIP_JOINTS):
        raise StopAndAsk(f"{body_name(host)} carries the hinges {names}, not the three serial hip rotations hip_fe, hip_aa, hip_ier")
    if any(np.abs(j["anchor"]).max() > tol for j in hj):
        raise StopAndAsk(f"the hip hinges of {body_name(host)} are not all about the body origin (anchors {[j['anchor'].tolist() for j in hj]})")
    b = _body_id(model, host)
    if np.abs(model.body_quat[b] - np.array([1.0, 0, 0, 0])).max() > tol:
        raise StopAndAsk(f"{body_name(host)} is rotated relative to its parent at q = 0: its frame is not the oracle segment frame")
    return hj


def _transforms(model, data, qpos0, assign):
    import mujoco
    data.qpos[:] = qpos0
    for adr, rad in assign.items():
        data.qpos[adr] = rad
    mujoco.mj_kinematics(model, data)


def _T(data, b):
    T = np.eye(4)
    T[:3, :3] = data.xmat[b].reshape(3, 3)
    T[:3, 3] = data.xpos[b]
    return T


def _probe_sign(model, jname, row):
    import mujoco
    spec = row or POLARITY_ROWS[jname]
    j = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_JOINT, jname)
    b = int(model.jnt_bodyid[j])
    data = mujoco.MjData(model)
    adr = int(model.jnt_qposadr[j])
    _transforms(model, data, model.qpos0, {})
    p0 = data.xpos[b] + data.xmat[b].reshape(3, 3) @ np.asarray(spec["probe"], float)
    _transforms(model, data, model.qpos0, {adr: model.qpos0[adr] + PROBE_RAD})
    p1 = data.xpos[b] + data.xmat[b].reshape(3, 3) @ np.asarray(spec["probe"], float)
    d = (p1 - p0)["xyz".index(spec["axis"])]
    if abs(d) < 1e-3:
        raise StopAndAsk(f"{jname}: the polarity probe moves {d * 1000:.2f} mm along {spec['axis']}, under the file's 1 mm")
    return 1 if d > 0 else -1


_POL = load_polarity()
POLARITY, POLARITY_ROWS = _POL


def clinical_factor(model, jname, polarity=None) -> int:
    """+1 when a positive clinical angle is a positive hinge angle in the model, -1 when the model's hinge runs the other way (the file's sign over the measured one)."""
    want = int((polarity or POLARITY)[jname])
    return want * _probe_sign(model, jname, None)


# ---- sampling ----------------------------------------------------------------------------------------------------------------------------

def _values(lo, hi, step):
    v = {float(k) * step for k in range(int(np.ceil(lo / step)), int(np.floor(hi / step)) + 1)}
    return sorted(v | {float(lo), float(hi)})


def default_samples(model, host="thigh_R", side=None):
    """(joint names, (n, 3) degrees) of the default sampling for the three hip hinges of `host`: a single-axis sweep of each over its full range at 5 degree steps (the other two
    neutral), then the three-axis grid at 15 degree steps over the limits; rows are unique and in a stable order (sweeps first, then the grid). The ranges come from the model."""
    hj = check_hip_chain(model, host)
    names = [j["name"] for j in hj]
    rng = [j["range_deg"] for j in hj]
    if any(r is None for r in rng):
        raise StopAndAsk("a hip hinge has no range in the model; the default sampling needs the limits")
    rows, seen = [], set()

    def add(r):
        key = tuple(round(x, 6) for x in r)
        if key not in seen:
            seen.add(key)
            rows.append(list(r))
    add((0.0, 0.0, 0.0))
    for k, (lo, hi) in enumerate(rng):
        for v in _values(lo, hi, SWEEP_STEP_DEG):
            r = [0.0, 0.0, 0.0]
            r[k] = v
            add(r)
    for r in itertools.product(*[_values(lo, hi, GRID_STEP_DEG) for lo, hi in rng]):
        add(r)
    return names, np.array(rows)


def read_samples(path) -> tuple:
    """(joint names, (n, k) degrees) from a CSV with one column per model joint name; lines starting with # are comments."""
    with open(path, newline="", encoding="utf-8") as fh:
        rows = list(csv.DictReader(line for line in fh if not line.startswith("#")))
    if not rows:
        raise ValueError(f"{path}: no samples")
    names = list(rows[0])
    return names, np.array([[float(r[n] or 0) for n in names] for r in rows])


# ---- the poses ---------------------------------------------------------------------------------------------------------------------------

def placement_matrix(placement) -> np.ndarray:
    """4x4 transform of a 6-DOF placement (tx, ty, tz mm; rx, ry, rz degrees, the oracle's extrinsic x-y-z convention), translation in metres."""
    p = np.asarray(placement, float)
    T = np.eye(4)
    T[:3, :3] = Rotation.from_euler("xyz", p[3:], degrees=True).as_matrix()
    T[:3, 3] = p[:3] / 1000.0
    return T


def pose_row(T) -> list:
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")                  # at ry = +-90 the split between rx and rz is arbitrary; the rotation is not
        e = Rotation.from_matrix(T[:3, :3]).as_euler("xyz", degrees=True)
    return [*(T[:3, 3] * 1000.0).tolist(), *e.tolist()]


def foreign_poses(model, owner: str, host: str, placement, names, angles_deg, polarity=None, side="right") -> np.ndarray:
    """(n, 6) poses (tx, ty, tz mm; rx, ry, rz degrees) of a part fixed in the `owner` body's frame, in the `host` body's frame, one per row of `angles_deg` (columns `names`, model joint
    names; joints not named stay at qpos0). Only the right side is built."""
    import mujoco
    if side != "right" or str(host).endswith("_L") or body_name(host).endswith("left"):
        raise NotImplementedError("foreign poses are built for the right side only; the left-side convention is an open item (ask Joe)")
    check_hip_chain(model, host)
    jid = {n: mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_JOINT, n) for n in names}
    for n, j in jid.items():
        if j < 0:
            raise KeyError(f"the model has no joint {n!r}")
    adr = {n: int(model.jnt_qposadr[j]) for n, j in jid.items()}
    fac = {n: clinical_factor(model, n, polarity) for n in names}
    data = mujoco.MjData(model)
    bo, bh = _body_id(model, owner), _body_id(model, host)
    Tp = placement_matrix(placement)
    out = []
    for row in np.atleast_2d(np.asarray(angles_deg, float)):
        _transforms(model, data, model.qpos0, {adr[n]: model.qpos0[adr[n]] + fac[n] * np.radians(a) for n, a in zip(names, row)})
        Th, To = _T(data, bh), _T(data, bo)
        out.append(pose_row(np.linalg.inv(Th) @ To @ Tp))
    return np.array(out)


def write_poses(path, poses, source: str) -> None:
    """The poses CSV (`oracle.read_poses`' schema) with a banner comment (CONVENTIONS section 4: it is generated)."""
    lines = [f"# GENERATED by fy envelope foreign from {source}. Do not edit; change the inputs and rerun.", ",".join(oracle.POSE_COLUMNS)]
    lines += [",".join(f"{x:.4f}" for x in r) for r in poses]
    Path(path).write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
