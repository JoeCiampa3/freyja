"""
Static equilibrium solver (Stage 1c T1): the joint torques that hold a pose still on the floor, independent of any
controller gain.

With qvel = qacc = 0 and contacts disabled for the call, mj_inverse's qfrc_inverse is the generalized force that
balances gravity. The ground reaction is not taken from the contact solver (its soft-constraint force is not the force
that balances the pose); it is supplied explicitly: a vertical force equal to body weight at the ground projection of
the whole-body CoM, split between the feet so the lateral moment closes, mapped to generalized forces through each
foot's Jacobian at its point of application. Then

    joint torques = (qfrc_inverse - qfrc_ground)[joint rows]        the six root rows are the residual

The residual vanishes by construction when the wrench is applied correctly, so it tests the implementation, not the
pose. Whether the pose can be held at all is a separate verdict: the CoP (which statics puts under the CoM) must lie
inside the support polygon (the sole corners of the foot boxes within 1 mm of the floor) and every limited joint must be
inside its range. Joint torque is about the model's own hinge axes, not actuator torque for a coupled hip.

The model's contact flag is restored afterwards and the MjData passed in is never modified.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field

import mujoco
import numpy as np

import metrics

VERSION = "1"
ZERO_STOP_TOL_RAD = 1e-9  # rad. A joint this close to a range edge that is exactly 0 stands on a zero-width stop (the sheet's placeholder shoulder adduction, the flat toe)
SOLE_TOL_M = 1e-3  # m. A foot-box corner this close to the floor belongs to the support polygon (the brief's 1 mm).


@dataclass
class StaticResult:
    qpos: np.ndarray
    torque: dict  # hinge joint name -> N m about its axis, model sign convention
    residual_force_n: float  # largest root force row of (qfrc_inverse - qfrc_ground)
    residual_moment_nm: float  # largest root moment row
    cop_xy: tuple  # ground projection of the CoM (m, world)
    cop_x_rel_ankle_m: float  # CoP x minus the first foot's ankle x
    force_split: dict  # foot body -> vertical force N
    support_margin_m: float  # signed distance from the CoP to the support polygon boundary, positive inside
    limit_margin_deg: float | None  # smallest distance to a limit over limited hinges, negative if outside
    limit_joint: str | None
    feasible: bool
    reasons: list = field(default_factory=list)
    zero_width_stops: dict = field(default_factory=dict)  # joint -> "lower" or "upper": joints standing on a range edge of exactly 0, which limit_margin_deg leaves out


def _bottom_corners_xy(model, data, bodies) -> list:
    pts = []
    for g in range(model.ngeom):
        if model.geom_bodyid[g] in bodies and model.geom_type[g] == mujoco.mjtGeom.mjGEOM_BOX:
            r, c, s = data.geom_xmat[g].reshape(3, 3), data.geom_xpos[g], model.geom_size[g]
            for sx in (-1, 1):
                for sy in (-1, 1):
                    for sz in (-1, 1):
                        p = c + r @ (np.array([sx, sy, sz]) * s)
                        if p[2] <= SOLE_TOL_M:
                            pts.append((float(p[0]), float(p[1])))
    return pts


def solve_static(model, data, feet=("foot_right", "foot_left"), _ground_sign: float = 1.0) -> StaticResult:
    """Joint torques and feasibility of the pose in `data` (only its qpos is read). `_ground_sign` exists for the
    mutation test (flipping the ground force must break the residual)."""
    flags = int(model.opt.disableflags)
    try:
        model.opt.disableflags = flags | int(mujoco.mjtDisableBit.mjDSBL_CONTACT)
        work = mujoco.MjData(model)
        work.qpos[:] = data.qpos
        work.qvel[:] = 0.0
        mujoco.mj_forward(model, work)
        work.qacc[:] = 0.0  # after the forward pass, which fills qacc with the free-fall acceleration
        weight = float(model.body_mass.sum() * abs(model.opt.gravity[2]))
        com = work.subtree_com[0].copy()
        ids = []
        for name in feet:
            b = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_BODY, name)
            if b < 0:
                raise ValueError(f"no body {name}")
            ids.append(b)
        ys = [float(work.xpos[b][1]) for b in ids]
        if len(ids) == 1:
            split = [weight]
        elif len(ids) == 2:  # sum F_i = W and sum F_i y_i = W y_com
            first = weight * (com[1] - ys[1]) / (ys[0] - ys[1])
            split = [first, weight - first]
        else:
            raise ValueError("statics supports one or two feet")
        qfrc_ground = np.zeros(model.nv)
        jacp, jacr = np.zeros((3, model.nv)), np.zeros((3, model.nv))
        for b, y, f in zip(ids, ys, split):
            point = np.array([com[0], y, 0.0])  # the CoP's x, the foot's own y, on the floor
            mujoco.mj_jac(model, work, jacp, jacr, point, b)
            qfrc_ground += jacp.T @ np.array([0.0, 0.0, _ground_sign * f])
        mujoco.mj_inverse(model, work)
        net = work.qfrc_inverse - qfrc_ground
        corners = _bottom_corners_xy(model, work, set(ids))
        margin = metrics.support_margin(corners, com[:2])
        torque, lim_margin, lim_joint, zero_stops = {}, None, None, {}
        for j in range(model.njnt):
            if model.jnt_type[j] != mujoco.mjtJoint.mjJNT_HINGE:
                continue
            name = mujoco.mj_id2name(model, mujoco.mjtObj.mjOBJ_JOINT, j)
            torque[name] = float(net[model.jnt_dofadr[j]])
            if model.jnt_limited[j]:
                q = float(work.qpos[model.jnt_qposadr[j]])
                edge = next((side for side, k in (("lower", 0), ("upper", 1)) if model.jnt_range[j][k] == 0.0 and abs(q) <= ZERO_STOP_TOL_RAD), None)
                if edge is not None:  # on a zero-width stop (neutral against an edge at 0): listed apart, not a margin
                    zero_stops[name] = edge
                    continue
                m = math.degrees(min(q - model.jnt_range[j][0], model.jnt_range[j][1] - q))
                if lim_margin is None or m < lim_margin:
                    lim_margin, lim_joint = m, name
        reasons = []
        if not margin >= 0.0:
            reasons.append(f"CoP is outside the support polygon by {-margin * 1000:.1f} mm" if math.isfinite(margin) else "no support polygon")
        if lim_margin is not None and lim_margin < 0.0:
            reasons.append(f"{lim_joint} is outside its range by {-lim_margin:.2f} deg")
        return StaticResult(
            qpos=work.qpos.copy(), torque=torque,
            residual_force_n=float(np.max(np.abs(net[:3]))), residual_moment_nm=float(np.max(np.abs(net[3:6]))),
            cop_xy=(float(com[0]), float(com[1])), cop_x_rel_ankle_m=float(com[0] - work.xpos[ids[0]][0]),
            force_split={n: float(f) for n, f in zip(feet, split)}, support_margin_m=float(margin),
            limit_margin_deg=lim_margin, limit_joint=lim_joint, feasible=not reasons, reasons=reasons, zero_width_stops=zero_stops)
    finally:
        model.opt.disableflags = flags
