"""
Lean-pose solver (Stage 1b T1): the rigid lean about the ankle that puts the whole-body CoM a chosen distance in
front of the ankle.

Every joint is neutral except the ankle dorsiflexion of each foot, which is the lean angle. The free root's pitch
is solved so the soles are flat (the foot's x axis is horizontal) and its position so the ankle keeps its neutral
x and the lowest point of the feet is on z = 0. Everything is found by forward kinematics and bisection, so no
sign convention is assumed: the angle that comes back is in the model's own convention. A target the ankle range
cannot reach is an error, never a clipped pose.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import mujoco
import numpy as np

POLARITY_FILE = Path(__file__).resolve().parents[2] / "checks" / "joint_polarity.yaml"
# pose parameter -> the hinge joints it sets (degrees, positive in the model's flexion direction). A pelvic tilt is a hip
# flexion on both sides: the pelvis rotates forward about the hip axes and the legs stay where they are.
POSE_JOINTS = {"lsj_fe_deg": ("lsj_fe",), "tj_fe_deg": ("tj_fe",), "cj_fe_deg": ("cj_fe",),
               "pelvic_tilt_deg": ("hip_fe_right", "hip_fe_left")}

ROOT_XTOL = 1e-14  # rad: stop when the iterate moves less than this, far below the 0.1 mm the pose is checked to
MAX_ROOT_ITERATIONS = 200  # a guard; the smooth functions here converge in under ten
PITCH_BRACKET_RAD = 1.5  # rad: the search range of the root pitch (a level sole needs the pitch to cancel the ankle angle, at most 62 deg)


class LeanError(ValueError):
    """The requested lean cannot be reached."""


@dataclass
class Lean:
    qpos: np.ndarray  # the full pose
    lean_rad: float  # the ankle angle of every foot, model sign convention
    com_offset_m: float  # achieved whole-body CoM x minus ankle x
    root_pitch_rad: float
    offsets: dict | None = None  # joint name -> rad set before the lean was solved


def _bisect(f, lo, hi):
    """Root of f in [lo, hi] (f changes sign there): the Illinois form of regula falsi, which is bracketed like bisection
    but converges in a handful of evaluations on the smooth, nearly linear functions of a pose. Stops when the iterate moves
    by less than ROOT_XTOL or f is zero."""
    flo, fhi = f(lo), f(hi)
    if flo == 0.0:
        return lo
    if fhi == 0.0:
        return hi
    side, x_prev = 0, None
    for _ in range(MAX_ROOT_ITERATIONS):
        x = (lo * fhi - hi * flo) / (fhi - flo)
        fx = f(x)
        if fx == 0.0 or (x_prev is not None and abs(x - x_prev) < ROOT_XTOL):
            return x
        x_prev = x
        if (fx > 0) == (flo > 0):
            lo, flo = x, fx
            if side == 1:
                fhi *= 0.5
            side = 1
        else:
            hi, fhi = x, fx
            if side == -1:
                flo *= 0.5
            side = -1
    return x


def _bottom_z(model, data, bodies):
    """Lowest world z over the box geoms of the given bodies."""
    low = np.inf
    for g in range(model.ngeom):
        if model.geom_bodyid[g] in bodies and model.geom_type[g] == mujoco.mjtGeom.mjGEOM_BOX:
            low = min(low, data.geom_xpos[g][2] - float(np.sum(np.abs(data.geom_xmat[g].reshape(3, 3)[2]) * model.geom_size[g])))
    return low


def flexion_sign(model, joint: str) -> float:
    """+1 when a positive qpos of `joint` moves its probe the way checks/joint_polarity.yaml says flexion does, -1 when
    it moves it the other way. Found by forward kinematics, not assumed."""
    import yaml
    row = yaml.safe_load(POLARITY_FILE.read_text(encoding="utf-8"))["joints"][joint]
    j = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_JOINT, joint)
    body, axis = int(model.jnt_bodyid[j]), "xyz".index(row["axis"])
    data = mujoco.MjData(model)

    def probe():
        mujoco.mj_forward(model, data)
        return data.xpos[body] + data.xmat[body].reshape(3, 3) @ np.array(row["probe"], dtype=float)
    data.qpos[:] = model.qpos0
    before = probe()
    data.qpos[model.jnt_qposadr[j]] += 0.1
    moved = (probe() - before)[axis]
    if abs(moved) < 1e-6:
        raise LeanError(f"the polarity probe of {joint} does not move; cannot find its flexion direction")
    return 1.0 if np.sign(moved) == np.sign(row["sign"]) else -1.0


def pose_offsets(model, pose: dict) -> dict:
    """{joint: rad} for the sagittal pose parameters in `pose` (the others, such as com_x_rel_ankle_m, are ignored)."""
    out = {}
    for key, joints in POSE_JOINTS.items():
        value = float(pose.get(key, 0.0))
        if value == 0.0:
            continue  # a zero parameter sets nothing (and a model without that joint is fine)
        for joint in joints:
            out[joint] = flexion_sign(model, joint) * np.radians(value)
    return out


def solve_pose(model, pose: dict, feet: dict) -> Lean:
    """The standing pose a scenario's `pose` block describes: sagittal offsets first, then the rigid lean about the ankle
    that puts the CoM `com_x_rel_ankle_m` in front of it. Unknown keys and a missing CoM target are errors."""
    unknown = sorted(set(pose) - set(POSE_JOINTS) - {"com_x_rel_ankle_m"})
    if unknown:
        raise LeanError(f"unknown pose parameter(s): {', '.join(unknown)}")
    if "com_x_rel_ankle_m" not in pose:
        raise LeanError("pose needs com_x_rel_ankle_m")
    return solve_lean(model, float(pose["com_x_rel_ankle_m"]), feet, pose_offsets(model, pose))


def design_stance(model, tilt_deg: float, feet: dict, com_x_rel_ankle_m: float = 0.0, upright: bool = False) -> Lean:
    """The design standing posture (decisions/0004): the pelvis tilted forward by `tilt_deg`, the hips flexed by it (the thighs then hang plumb) and the lumbosacral joint
    extended by it (the trunk stack is plumb). Then the rigid lean about the ankle that puts the CoM `com_x_rel_ankle_m` in front of it, as solve_lean does; with
    `upright` there is no lean (ankle at zero, soles flat), the posture a stature is measured in. A tilt past a joint's range is an error."""
    offsets = pose_offsets(model, {"pelvic_tilt_deg": tilt_deg, "lsj_fe_deg": -tilt_deg})
    if upright:
        return solve_lean(model, None, feet, offsets, ankle_rad=0.0)
    return solve_lean(model, com_x_rel_ankle_m, feet, offsets)


def solve_lean(model, com_x_rel_ankle_m: float | None, feet: dict, offsets: dict | None = None, ankle_rad: float | None = None) -> Lean:
    """`feet` maps each foot body name to its ankle dorsiflexion joint name. `offsets` ({joint: rad}) are set before the
    lean is solved. With `ankle_rad` the ankle angle is given and there is no CoM target (`com_x_rel_ankle_m` may be None): the pose at that
    angle, soles flat, lowest point on the floor. Returns the pose."""
    offsets = {k: float(v) for k, v in (offsets or {}).items() if float(v) != 0.0}
    set_q = []
    for name, value in offsets.items():
        jj = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_JOINT, name)
        if jj < 0:
            raise LeanError(f"no joint {name}")
        if model.jnt_limited[jj] and not model.jnt_range[jj][0] <= value <= model.jnt_range[jj][1]:
            raise LeanError(f"{name} = {np.degrees(value):+.2f} deg is outside its range "
                            f"{np.degrees(model.jnt_range[jj][0]):.1f} to {np.degrees(model.jnt_range[jj][1]):.1f} deg")
        set_q.append((int(model.jnt_qposadr[jj]), value))
    bid = lambda n: mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_BODY, n)  # noqa: E731
    jid = lambda n: mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_JOINT, n)  # noqa: E731
    roots = [j for j in range(model.njnt) if model.jnt_type[j] == mujoco.mjtJoint.mjJNT_FREE]
    if len(roots) != 1:
        raise LeanError("the model needs exactly one free root joint")
    r = int(model.jnt_qposadr[roots[0]])
    if not np.allclose(model.qpos0[r + 3:r + 7], [1, 0, 0, 0]):
        raise LeanError("the neutral root orientation must be the identity")
    foot_ids = {bid(n) for n in feet}
    foot_ids |= {b for b in range(model.nbody) if int(model.body_parentid[b]) in foot_ids}  # the toe hangs from the foot and is part of the sole
    ankle = [(int(model.jnt_qposadr[jid(j)]), tuple(model.jnt_range[jid(j)])) for j in feet.values()]
    first = bid(next(iter(feet)))
    lo = max(rng[0] for _, rng in ankle)
    hi = min(rng[1] for _, rng in ankle)
    data = mujoco.MjData(model)
    x_ankle0 = None

    def fk(theta, pitch, shift=(0.0, 0.0)):
        data.qpos[:] = model.qpos0
        for adr, value in set_q:
            data.qpos[adr] = value
        for adr, _ in ankle:
            data.qpos[adr] = theta
        data.qpos[r + 0] += shift[0]
        data.qpos[r + 2] += shift[1]
        data.qpos[r + 3:r + 7] = [np.cos(pitch / 2), 0.0, np.sin(pitch / 2), 0.0]
        mujoco.mj_forward(model, data)

    mujoco.mj_forward(model, data)
    x_ankle0 = float(data.xpos[first][0])

    def pose(theta):
        """-> (pitch, shift, offset): soles flat, ankle at its neutral x, lowest sole on z = 0"""
        g = lambda ph: (fk(theta, ph), float(data.xmat[first][6]))[1]  # noqa: E731  x axis of the foot: its z component
        if g(-PITCH_BRACKET_RAD) * g(PITCH_BRACKET_RAD) > 0:
            raise LeanError(f"cannot level the soles at ankle angle {theta:.4f} rad")
        pitch = _bisect(g, -PITCH_BRACKET_RAD, PITCH_BRACKET_RAD)
        fk(theta, pitch)
        shift = (x_ankle0 - float(data.xpos[first][0]), -_bottom_z(model, data, foot_ids))
        fk(theta, pitch, shift)
        return pitch, shift, float(data.subtree_com[0][0] - data.xpos[first][0])

    if ankle_rad is not None:
        if not lo <= ankle_rad <= hi:
            raise LeanError(f"ankle angle {np.degrees(ankle_rad):+.2f} deg is outside the ankle range {np.degrees(lo):.1f} to {np.degrees(hi):.1f} deg")
        pitch, shift, achieved = pose(float(ankle_rad))
        return Lean(data.qpos.copy(), float(ankle_rad), achieved, float(pitch), offsets)
    offset = lambda th: pose(th)[2]  # noqa: E731
    o_lo, o_hi = offset(lo), offset(hi)
    target = float(com_x_rel_ankle_m)
    if not min(o_lo, o_hi) <= target <= max(o_lo, o_hi):
        raise LeanError(f"unreachable: a CoM {target:+.4f} m from the ankle needs more than the ankle range "
                        f"{np.degrees(lo):.1f} to {np.degrees(hi):.1f} deg, which reaches {min(o_lo, o_hi):+.4f} to {max(o_lo, o_hi):+.4f} m")
    theta = _bisect(lambda th: offset(th) - target, lo, hi)
    pitch, shift, achieved = pose(theta)
    return Lean(data.qpos.copy(), float(theta), achieved, float(pitch), offsets)
