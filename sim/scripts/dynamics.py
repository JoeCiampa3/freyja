"""
Stage 2 T3: dynamic wrench solver for Freyja's gait loads. This first part is the frame-level inverse dynamics: `mj_inverse`
with contacts and joint-limit constraints both disabled (a stop would otherwise carry load and understate the torque the
joints need on frames past a limit). The contact solver is never used for loads (CONVENTIONS section 6, method constraint).

For the free root, the first three rows of qfrc_inverse are the net external force in the world frame that realises the
prescribed qacc: m (a_com + g). The remaining rows are filled in by the ground-wrench solve (later in T3).
"""
from __future__ import annotations

import mujoco
import numpy as np

VERSION = "1"
_OFF = int(mujoco.mjtDisableBit.mjDSBL_CONTACT) | int(mujoco.mjtDisableBit.mjDSBL_LIMIT)


def inverse_frame(model, qpos, qvel, qacc) -> np.ndarray:
    """qfrc_inverse for one frame with contacts and limits disabled; the model's flags are restored and its data untouched."""
    flags = int(model.opt.disableflags)
    try:
        model.opt.disableflags = flags | _OFF
        d = mujoco.MjData(model)
        d.qpos[:], d.qvel[:], d.qacc[:] = qpos, qvel, qacc
        mujoco.mj_inverse(model, d)
        return d.qfrc_inverse.copy()
    finally:
        model.opt.disableflags = flags


# ======================================================================== ground wrench and joint torque (T3)
#
# qfrc_inverse's root rows are the net external wrench that realises the prescribed motion: rows 0-2 the force in the world frame,
# rows 3-5 the moment about the root origin in the root's own frame (the free joint's rotational dofs are body-fixed). The
# ground supplies that wrench:
#   single support  the whole force F acts at a CoP on the floor plane; the two horizontal-moment equations fix it, the vertical-axis
#                   moment is left in the root rows and reported (a foot on a belt can supply it as free torque; we do not)
#   double support  F is split between the feet in proportion to the CoM's position between them; each foot's horizontal force
#                   follows the same split; both CoPs sit at the same normalised offset u along their own box with a shared lateral
#                   shift v, and the two moment equations fix (u, v)
#   swing foot      zero
# Joint torque is the joint rows of qfrc_inverse - qfrc_ground, with qfrc_ground = sum J_p(p_i)^T f_i from mj_jac, which is
# independent of the algebra above: the root residual measures whether the algebra is right.

from dataclasses import dataclass, field

import metrics

FEET = ("foot_right", "foot_left")
HULL_BAND_M = 0.025  # m. A foot-box vertex within this of that foot's lowest point belongs to its contact polygon, so a foot that
#                      floats slightly still has one (the brief's default).
ROOT_TOL = 1e-9  # root residual limit as a fraction of body weight (N) and of weight times 1 m (N m), as in statics
N_SWEEP = 21  # force-split values in the double-support bound


@dataclass
class FrameResult:
    torque: dict  # hinge joint -> N m about its axis, nominal split
    torque_range: dict  # hinge joint -> (min, max) over the feasible splits (nominal only outside double support)
    force: dict  # stance foot -> world force (3,)
    cop: dict  # stance foot -> CoP on the floor (3,)
    support: str  # single_right, single_left, double, none
    split_right: float | None
    residual: np.ndarray  # [force x y z, horizontal moment x y, vertical moment] left in the root rows, world frame
    yaw_moment_nm: float
    weight_n: float
    cop_margin_m: dict  # signed distance of the CoP to its foot's contact polygon, positive inside
    friction_ratio: dict
    hull_degenerate: dict  # stance foot -> True when its contact polygon is a segment or a point (foot rolling on an edge)
    feasible: bool
    reasons: list = field(default_factory=list)
    feasible_split: tuple | None = None  # (lowest, highest) feasible right-foot share in double support
    qfrc_net: np.ndarray | None = None


def root_closes(r: FrameResult) -> bool:
    return bool(np.abs(r.residual[:3]).max() <= ROOT_TOL * r.weight_n and np.abs(r.residual[3:5]).max() <= ROOT_TOL * r.weight_n)


def _foot_boxes(model, d, body):
    """World corners of the box geoms of a foot body, plus the first box's floor-projected centre, long-axis half vector, mu."""
    corners, first = [], None
    for g in range(model.ngeom):
        if model.geom_bodyid[g] == body and model.geom_type[g] == mujoco.mjtGeom.mjGEOM_BOX:
            r, c, s = d.geom_xmat[g].reshape(3, 3), d.geom_xpos[g], model.geom_size[g]
            for sx in (-1, 1):
                for sy in (-1, 1):
                    for sz in (-1, 1):
                        corners.append(c + r @ (np.array([sx, sy, sz]) * s))
            if first is None:
                ax = r[:, 0].copy()
                ax[2] = 0.0
                n = np.linalg.norm(ax)
                ax = ax / n if n > 0 else np.array([1.0, 0.0, 0.0])
                first = (np.array([c[0], c[1], 0.0]), s[0] * ax, float(model.geom_friction[g][0]))
    return np.array(corners), first


def _hinges(model):
    return [(mujoco.mj_id2name(model, mujoco.mjtObj.mjOBJ_JOINT, j), int(model.jnt_dofadr[j]))
            for j in range(model.njnt) if model.jnt_type[j] == mujoco.mjtJoint.mjJNT_HINGE]


SEGMENT_TOL_M = HULL_BAND_M  # m. A foot rolling on its heel or toe edge has a segment for a contact polygon; a CoP within this of the
#                              segment counts as inside, because a sole is not zero-width. Used by the polygon baseline (T3b step 4).


def contact_margin(corners, xy, band_m=HULL_BAND_M, segment_tol_m=0.0):
    """Signed distance of the floor point xy to a foot's contact polygon (positive inside) and whether the polygon is degenerate.
    `corners` are the foot box's world vertices; the polygon is the hull of those within band_m of the lowest one. A degenerate
    polygon (a segment or a point) gives minus the distance to it, raised by segment_tol_m so that a point within the tolerance of
    the segment is not outside."""
    pts = corners[corners[:, 2] <= corners[:, 2].min() + band_m][:, :2]
    margin = float(metrics.support_margin(pts, xy))
    degenerate = len(metrics.convex_hull(pts)) < 3
    if degenerate:
        margin += segment_tol_m
    return margin, degenerate


def foot_polygon_margin(model, qpos, foot, xy, band_m=HULL_BAND_M, segment_tol_m=0.0):
    """contact_margin for the named foot of the pose qpos."""
    d = mujoco.MjData(model)
    d.qpos[:] = qpos
    mujoco.mj_kinematics(model, d)
    corners, _ = _foot_boxes(model, d, mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_BODY, foot))
    return contact_margin(corners, np.asarray(xy, float)[:2], band_m, segment_tol_m)


def solve_frame(model, qpos, qvel, qacc, stance=FEET, feet=FEET, sweep=False, band_m=HULL_BAND_M, n_sweep=N_SWEEP,
                _ground_sign: float = 1.0, qfrc=None, split_right_override=None, segment_tol_m=0.0) -> FrameResult:
    """Ground wrench, CoPs, joint torques and feasibility for one frame. `stance` lists the feet on the ground. With `sweep` and
    two stance feet, the right-foot force share is swept over its feasible range and the worst case per joint is kept in
    `torque_range`. `_ground_sign` exists for the mutation test only."""
    if qfrc is None:
        qfrc = inverse_frame(model, qpos, qvel, qacc)
    d = mujoco.MjData(model)
    d.qpos[:] = qpos
    mujoco.mj_kinematics(model, d)
    mujoco.mj_comPos(model, d)
    root = int(model.jnt_bodyid[0])
    R = d.xmat[root].reshape(3, 3)
    p0 = np.asarray(qpos[:3], float)
    F = qfrc[:3].copy()
    M = R @ qfrc[3:6]  # moment about the root origin, world frame
    weight = float(model.body_mass.sum() * abs(model.opt.gravity[2]))
    bodies = {n: mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_BODY, n) for n in feet}
    stance = tuple(n for n in feet if n in stance)
    geo = {n: _foot_boxes(model, d, bodies[n]) for n in stance}
    hinges = _hinges(model)

    def cop_single(f):
        h = p0[2]
        return np.array([p0[0] - (M[1] + h * f[0]) / f[2], p0[1] + (M[0] - h * f[1]) / f[2], 0.0])

    def assemble(forces, cops):
        g = np.zeros(model.nv)
        jp = np.zeros((3, model.nv))
        for n in stance:
            mujoco.mj_jac(model, d, jp, None, cops[n], bodies[n])
            g += jp.T @ (_ground_sign * forces[n])
        net = qfrc - g
        return net, np.r_[net[:3], R @ net[3:6]]

    def feasibility(forces, cops):
        reasons, margin, fric, degenerate = [], {}, {}, {}
        for n in stance:
            corners, (_, _, mu) = geo[n]
            margin[n], degenerate[n] = contact_margin(corners, cops[n][:2], band_m, segment_tol_m)
            fz = forces[n][2]
            fric[n] = float(np.hypot(forces[n][0], forces[n][1]) / fz) if fz > 0 else float("inf")
            if not fz > 0:
                reasons.append(f"{n}: no vertical force")
            if not margin[n] >= 0:
                reasons.append(f"{n}: CoP outside the contact polygon by {-margin[n] * 1000:.1f} mm")
            if not fric[n] <= mu:
                reasons.append(f"{n}: friction ratio {fric[n]:.2f} above mu {mu:.2f}")
        return margin, fric, reasons, degenerate

    ey = np.array([0.0, 1.0, 0.0])

    def double(share_r):
        shares = {stance[0]: share_r, stance[1]: 1.0 - share_r}
        forces = {n: shares[n] * F for n in stance}
        rhs = M[:2].copy()
        a = np.zeros((2, 2))
        for n in stance:
            o, e, _ = geo[n][1]
            rhs -= np.cross(o - p0, forces[n])[:2]
            a[:, 0] += np.cross(e, forces[n])[:2]
        a[:, 1] = np.cross(ey, F)[:2]
        try:
            u, v = np.linalg.solve(a, rhs)
        except np.linalg.LinAlgError:
            u = v = float("nan")
        return forces, {n: geo[n][1][0] + u * geo[n][1][1] + v * ey for n in stance}

    support, split_right = "none", None
    if len(stance) == 0:
        forces, cops = {}, {}
    elif len(stance) == 1:
        support = "single_right" if stance[0] == feet[0] else "single_left"
        forces = {stance[0]: F.copy()}
        cops = {stance[0]: cop_single(F) if F[2] != 0 else np.full(3, np.nan)}
    else:
        support = "double"
        com = d.subtree_com[0]
        pr, pl = d.xpos[bodies[stance[0]]][:2], d.xpos[bodies[stance[1]]][:2]
        axis = pl - pr
        s = float(np.clip(np.dot(com[:2] - pr, axis) / np.dot(axis, axis), 0.0, 1.0))
        split_right = 1.0 - s if split_right_override is None else float(split_right_override)  # an override is a control property the kinematics cannot predict
        forces, cops = double(split_right)
    net, residual = assemble(forces, cops)
    margin, fric, reasons, degenerate = feasibility(forces, cops)
    torque = {n: float(net[dof]) for n, dof in hinges}
    rng = {n: (v, v) for n, v in torque.items()}
    feasible_split = None
    if sweep and support == "double":
        ok = []
        for r_share in np.linspace(0.0, 1.0, n_sweep):
            f2, c2 = double(float(r_share))
            net2, _ = assemble(f2, c2)
            if not feasibility(f2, c2)[2]:
                ok.append(float(r_share))
                for n, dof in hinges:
                    lo, hi = rng[n]
                    rng[n] = (min(lo, float(net2[dof])), max(hi, float(net2[dof])))
        if ok:
            feasible_split = (min(ok), max(ok))
    return FrameResult(torque=torque, torque_range=rng, force=forces, cop=cops, support=support, split_right=split_right,
                       residual=residual, yaw_moment_nm=float(residual[5]), weight_n=weight, cop_margin_m=margin,
                       friction_ratio=fric, hull_degenerate=degenerate, feasible=not reasons, reasons=reasons, feasible_split=feasible_split, qfrc_net=net)


def solve_given(model, qpos, qfrc, forces, cops, feet=FEET):
    """Joint torques and the root residual when the ground wrench is GIVEN (methods A and H) instead of solved: `forces` and
    `cops` map the loaded feet to a world force and a point on the floor. `qfrc` is the frame's qfrc_inverse. Returns
    (torque dict, residual [force xyz, moment xyz in the world frame about the root origin], net generalized force)."""
    d = mujoco.MjData(model)
    d.qpos[:] = qpos
    mujoco.mj_kinematics(model, d)
    mujoco.mj_comPos(model, d)
    R = d.xmat[int(model.jnt_bodyid[0])].reshape(3, 3)
    g = np.zeros(model.nv)
    jp = np.zeros((3, model.nv))
    for n, f in forces.items():
        mujoco.mj_jac(model, d, jp, None, np.asarray(cops[n], float), mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_BODY, n))
        g += jp.T @ np.asarray(f, float)
    net = qfrc - g
    return {n: float(net[dof]) for n, dof in _hinges(model)}, np.r_[net[:3], R @ net[3:6]], net


def cop_decomposition(model, qpos, qfrc):
    """The whole-body CoP (the point where the total ground force must act for the horizontal moments to close) split into
    its point-mass term, p = c_xy - (c_z / F_z) F_xy (CoM position and total force only), and the remainder, the
    angular-momentum term (the rate of change of the angular momentum about the CoM over F_z). Returns (full, point_mass,
    angular_momentum), each a floor point (3,). Independent of how the force is shared between the feet."""
    d = mujoco.MjData(model)
    d.qpos[:] = qpos
    mujoco.mj_kinematics(model, d)
    mujoco.mj_comPos(model, d)
    root = int(model.jnt_bodyid[0])
    F = np.asarray(qfrc[:3], float)
    M = d.xmat[root].reshape(3, 3) @ qfrc[3:6]
    p0 = np.asarray(qpos[:3], float)
    full = np.array([p0[0] - (M[1] + p0[2] * F[0]) / F[2], p0[1] + (M[0] - p0[2] * F[1]) / F[2], 0.0])
    com = d.subtree_com[0]
    pm = np.array([com[0] - com[2] * F[0] / F[2], com[1] - com[2] * F[1] / F[2], 0.0])
    return full, pm, full - pm


def foot_floor_segments(model, qpos, feet=FEET):
    """Foot -> (rear, front) points of its box's long axis projected on the floor, for the pose qpos (model xy)."""
    d = mujoco.MjData(model)
    d.qpos[:] = qpos
    mujoco.mj_kinematics(model, d)
    out = {}
    for n in feet:
        _, (centre, half, _) = _foot_boxes(model, d, mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_BODY, n))
        out[n] = (centre[:2] - half[:2], centre[:2] + half[:2])
    return out
