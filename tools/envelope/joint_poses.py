"""Hinge-chain poses (upper-arm characterization brief, T7; Joe's rulings 2026-11-14): the pose of an owner body (e.g. the right forearm) in the frame of a host body above it in the
model tree (e.g. the right upper arm) as the hinges between them move, built on the MuJoCo model.

This is foreign.py's construction without its hip-specific stop: for each sample the model is put at qpos0 with the sampled hinges set, `mj_kinematics` runs, and
    T_host_owner(q) = inv(T_world_host) @ T_world_owner.
Hinge names, axes, anchors and order are read from the model; the chain is every hinge on the bodies from just below the host down to the owner. Angles are degrees in the clinical
sign of `checks/joint_polarity.yaml`: the model's own sign of each hinge is measured with that file's probe and the sample is flipped if they disagree (foreign.clinical_factor), so the file,
not the axis arithmetic, decides. Angles are not clamped to the model's limits: a sweep may run past a hinge's range (the elbow's mechanism end, 157 degrees, against the model's 150).

Frames are the model body frames (origin at the body origin, axes parallel to the world at q = 0), in mm. The convention and frame helpers are imported from foreign.py, never copied.
Right side only, as foreign.py.
"""
from __future__ import annotations

import numpy as np

from .foreign import POLARITY_ROWS, _body_id, _T, _transforms, body_name, clinical_factor, joints_of
from .sheet import StopAndAsk

PROBE_MIN_MM = 1.0           # the polarity file's own threshold (foreign._probe_sign): a probe that moves less than this decides nothing


def hinge_chain(model, host: str, owner: str) -> list:
    """The hinges between `host` and `owner` (owner strictly below host in the model tree), proximal first and, within a body, in the model's order: the joints_of rows."""
    import mujoco
    bh, b = _body_id(model, host), _body_id(model, owner)
    path = []
    while b != bh:
        if b <= 0:
            raise StopAndAsk(f"{body_name(owner)} is not below {body_name(host)} in the model tree")
        path.append(b)
        b = int(model.body_parentid[b])
    out = []
    for bid in reversed(path):
        out += joints_of(model, mujoco.mj_id2name(model, mujoco.mjtObj.mjOBJ_BODY, bid))
    if not out:
        raise StopAndAsk(f"no hinge between {body_name(host)} and {body_name(owner)}")
    return out


def _check_side(*names):
    for n in names:
        if str(n).endswith("_L") or body_name(n).endswith("left"):
            raise NotImplementedError("joint poses are built for the right side only; the left-side convention is an open item (ask Joe)")


def relative_transforms(model, host: str, owner: str, names, angles_deg, polarity=None) -> np.ndarray:
    """(n, 4, 4) transforms T_host_owner, translation in mm, one per row of `angles_deg` (columns `names`, hinges of the chain between host and owner; hinges not named stay at qpos0)."""
    import mujoco
    _check_side(host, owner)
    chain = {j["name"]: j for j in hinge_chain(model, host, owner)}
    for n in names:
        if n not in chain:
            raise StopAndAsk(f"{n} is not a hinge between {body_name(host)} and {body_name(owner)} (the chain is {sorted(chain)})")
    adr = {n: chain[n]["qpos"] for n in names}
    fac = {n: clinical_factor(model, n, polarity) for n in names}
    data = mujoco.MjData(model)
    bh, bo = _body_id(model, host), _body_id(model, owner)
    out = []
    for row in np.atleast_2d(np.asarray(angles_deg, float)):
        _transforms(model, data, model.qpos0, {adr[n]: model.qpos0[adr[n]] + fac[n] * np.radians(a) for n, a in zip(names, row)})
        T = np.linalg.inv(_T(data, bh)) @ _T(data, bo)
        T[:3, 3] *= 1000.0
        out.append(T)
    return np.array(out)


def apply(T, points) -> np.ndarray:
    """Points (n, 3) in the owner frame -> the host frame, mm."""
    P = np.atleast_2d(np.asarray(points, float))
    return P @ T[:3, :3].T + T[:3, 3]


def check_probe_direction(model, host: str, owner: str, joint: str, angle_deg: float, T) -> None:
    """Independent of the sign the pose used: the polarity file's probe for `joint` (a point in the joint's body frame), carried by T from the zero pose, must move along the file's axis
    in the file's direction for a positive clinical angle. Raises StopAndAsk otherwise. Read from the file's row, never from the polarity passed to the pose."""
    spec = POLARITY_ROWS[joint]
    if body_name(owner) != _joint_body(model, joint):
        raise StopAndAsk(f"the probe of {joint} is in the frame of {_joint_body(model, joint)}, not {body_name(owner)}")
    T0 = relative_transforms(model, host, owner, [joint], [[0.0]])[0]
    p = np.asarray(spec["probe"], float) * 1000.0
    d = (apply(T, [p]) - apply(T0, [p]))[0]["xyz".index(spec["axis"])] * np.sign(angle_deg)
    if abs(d) < PROBE_MIN_MM:
        raise StopAndAsk(f"{joint}: the probe moves {d:.2f} mm along {spec['axis']} at {angle_deg} deg, under {PROBE_MIN_MM} mm")
    if np.sign(d) != int(spec["sign"]):
        raise StopAndAsk(f"{joint}: a positive clinical angle ({spec['positive']}) moves the probe {d:+.2f} mm along {spec['axis']}; the polarity file wants sign {spec['sign']}")


def _joint_body(model, joint: str) -> str:
    import mujoco
    j = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_JOINT, joint)
    if j < 0:
        raise KeyError(f"the model has no joint {joint!r}")
    return mujoco.mj_id2name(model, mujoco.mjtObj.mjOBJ_BODY, int(model.jnt_bodyid[j]))
