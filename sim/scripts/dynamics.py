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
    # double support (T3c.3): the total CoP is fixed by the root rows; the frame is feasible when it lies in the hull of the two feet's
    # contact polygons. `feasible_nominal` is the older test of the nominal rule's own placement (each CoP inside its foot).
    total_cop: np.ndarray | None = None
    ds_feasible: bool | None = None
    ds_outside_m: float | None = None
    ds_solutions: list = field(default_factory=list)  # (alpha, p_R, p_L) satisfying alpha p_R + (1 - alpha) p_L = total CoP
    polygons: tuple | None = None  # (right, left) contact polygons, hull vertices
    feasible_nominal: bool | None = None
    nominal_in_set: bool | None = None


def root_closes(r: FrameResult) -> bool:
    return bool(np.abs(r.residual[:3]).max() <= ROOT_TOL * r.weight_n and np.abs(r.residual[3:5]).max() <= ROOT_TOL * r.weight_n)


def _toes(model, body):
    """The child bodies of a foot body (its toe), whose boxes are part of the sole at the toe's current angle."""
    return [b for b in range(model.nbody) if int(model.body_parentid[b]) == body]


def _contact_body(model, d, foot, point):
    """The body a ground force at the floor point `point` acts on: the foot's toe when the point is ahead of the toe's hinge along the foot's long axis, else the
    foot. The ankle rows of the Jacobian are the same either way (the point is the same); the toe's own row is not. `d` has its kinematics done."""
    toes = _toes(model, foot)
    if not toes:
        return foot
    ax = d.xmat[foot].reshape(3, 3)[:2, 0]
    n = np.linalg.norm(ax)
    ax = ax / n if n > 0 else np.array([1.0, 0.0])
    return toes[0] if float((np.asarray(point, float)[:2] - d.xpos[toes[0]][:2]) @ ax) > 0.0 else foot


def _foot_boxes(model, d, body):
    """World corners of the box geoms of a foot body and of its toe, plus the floor-projected centre and long-axis half vector of the foot's sole (from the first
    box's long axis, spanning every box along it: a toe makes the sole longer) and the first box's friction mu."""
    corners, first, lo_hi = [], None, None
    for g in range(model.ngeom):
        if int(model.geom_bodyid[g]) in (body, *_toes(model, body)) and model.geom_type[g] == mujoco.mjtGeom.mjGEOM_BOX:
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
                first = [c.copy(), ax, float(model.geom_friction[g][0])]
                lo_hi = [float(c[:2] @ ax[:2]) - s[0], float(c[:2] @ ax[:2]) + s[0]]
            else:  # a further box (the toe) widens the sole along the first box's axis
                along = float(c[:2] @ first[1][:2])
                lo_hi = [min(lo_hi[0], along - s[0]), max(lo_hi[1], along + s[0])]
    if first is not None:
        c, ax, mu = first
        base = c[:2] - (c[:2] @ ax[:2]) * ax[:2]  # the first box's centre without its position along the axis
        mid, half = 0.5 * (lo_hi[0] + lo_hi[1]), 0.5 * (lo_hi[1] - lo_hi[0])
        first = (np.array([base[0] + mid * ax[0], base[1] + mid * ax[1], 0.0]), half * ax, mu)
    return np.array(corners), first


def _hinges(model):
    return [(mujoco.mj_id2name(model, mujoco.mjtObj.mjOBJ_JOINT, j), int(model.jnt_dofadr[j]))
            for j in range(model.njnt) if model.jnt_type[j] == mujoco.mjtJoint.mjJNT_HINGE]


N_PR = 5  # points along the feasible segment of the right-foot CoP, per feasible split (the brief's default)
PLANE_TOL_M = 1e-9  # m. A point this close to a polygon boundary is inside: round-off, not a threshold


def contact_polygon(corners, band_m=HULL_BAND_M):
    """Hull vertices (counter-clockwise; fewer than three for a foot on an edge or a point) of the foot-box vertices within band_m of the
    lowest one, projected on the floor."""
    return metrics.convex_hull(corners[corners[:, 2] <= corners[:, 2].min() + band_m][:, :2])


def margin_in_polygon(poly, p) -> float:
    """Signed distance of the floor point p to the polygon, positive inside (a segment or a point is never positive)."""
    return float(metrics.support_margin(poly, np.asarray(p, float)))


def _minkowski(poly_r, poly_l, alpha):
    return metrics.convex_hull([alpha * np.asarray(a) + (1.0 - alpha) * np.asarray(b) for a in poly_r for b in poly_l])


def share_in_set(poly_r, poly_l, p, alpha) -> bool:
    """Whether a right-foot force share alpha can produce the total CoP p with both CoPs inside their polygons: p must lie in
    alpha P_R + (1 - alpha) P_L."""
    return margin_in_polygon(_minkowski(poly_r, poly_l, alpha), p) >= -PLANE_TOL_M


def _centroid(poly):
    return np.mean(np.asarray(poly, float), axis=0)


def double_support_set(poly_r, poly_l, p, n_alpha=N_SWEEP, n_pr=N_PR) -> dict:
    """The feasible set of double support for the total CoP p: every split alpha (right-foot share) on an n_alpha grid for which
    alpha p_R + (1 - alpha) p_L = p has a solution with p_R in poly_r and p_L in poly_l, and, for each, n_pr points along the segment of
    feasible p_R (extremes found by linear programs along the polygon's longest direction). The set is non-empty exactly when p lies in
    the convex hull of the two polygons, and `feasible` is that test. Returns feasible, outside_m (distance from p to that hull, 0 when
    inside), alpha_range and solutions [(alpha, p_R, p_L)]; every solution satisfies the weighted-mean identity to round-off."""
    from scipy.optimize import linprog
    p = np.asarray(p, float)
    hull_margin = margin_in_polygon(metrics.convex_hull(list(poly_r) + list(poly_l)), p)
    if hull_margin < -PLANE_TOL_M:
        return {"feasible": False, "outside_m": -hull_margin, "alpha_range": None, "solutions": []}
    vr, vl = np.asarray(poly_r, float), np.asarray(poly_l, float)
    far = max(((np.linalg.norm(a - b), a - b) for a in vr for b in vr), key=lambda x: x[0])
    e = far[1] / far[0] if far[0] > 0 else np.array([1.0, 0.0])
    sols, alphas = [], []
    for alpha in np.linspace(0.0, 1.0, n_alpha):
        alpha = float(alpha)
        if alpha == 1.0:
            if margin_in_polygon(poly_r, p) >= -PLANE_TOL_M:
                alphas.append(alpha); sols.append((alpha, p.copy(), _centroid(poly_l)))
            continue
        if alpha == 0.0:
            if margin_in_polygon(poly_l, p) >= -PLANE_TOL_M:
                alphas.append(alpha); sols.append((alpha, _centroid(poly_r), p.copy()))
            continue
        if not share_in_set(poly_r, poly_l, p, alpha):
            continue
        nr, nl = len(vr), len(vl)
        a_eq = np.zeros((4, nr + nl))
        a_eq[0, :nr] = 1.0
        a_eq[1, nr:] = 1.0
        a_eq[2:, :nr] = alpha * vr.T
        a_eq[2:, nr:] = (1.0 - alpha) * vl.T
        b_eq = np.r_[1.0, 1.0, p]
        ends = []
        for sign in (1.0, -1.0):
            c = np.r_[sign * (vr @ e), np.zeros(nl)]
            res = linprog(c, A_eq=a_eq, b_eq=b_eq, bounds=(0, None), method="highs")
            if res.status == 0:
                ends.append(res.x[:nr] @ vr)
        if not ends:
            continue
        alphas.append(alpha)
        lo, hi = (ends[0], ends[-1])
        pts = [lo + (hi - lo) * k / (n_pr - 1) for k in range(n_pr)] if np.linalg.norm(hi - lo) > 1e-12 else [lo]
        for pr in pts:
            sols.append((alpha, pr, (p - alpha * pr) / (1.0 - alpha)))
    # feasibility is the hull test; the grid only samples the set, so a very thin set can fall between grid points (no solutions listed)
    return {"feasible": True, "outside_m": 0.0, "alpha_range": (min(alphas), max(alphas)) if alphas else None, "solutions": sols}


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
            mujoco.mj_jac(model, d, jp, None, cops[n], _contact_body(model, d, bodies[n], cops[n]))
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
    total_cop = ds_feasible = ds_outside = polygons = feasible_nominal = nominal_in_set = None
    ds_solutions = []
    if len(stance) == 1 and F[2] != 0:
        total_cop = cop_single(F)
    if support == "double":
        total_cop = cop_single(F) if F[2] != 0 else np.full(3, np.nan)
        polygons = tuple(contact_polygon(geo[n][0], band_m) for n in stance)
        feasible_nominal = not any("CoP outside" in r or "no vertical" in r for r in reasons)
        found = double_support_set(polygons[0], polygons[1], total_cop[:2], n_alpha=n_sweep) if np.all(np.isfinite(total_cop)) else \
            {"feasible": False, "outside_m": float("nan"), "alpha_range": None, "solutions": []}
        ds_feasible, ds_outside = found["feasible"], found["outside_m"]
        nominal_in_set = bool(share_in_set(polygons[0], polygons[1], total_cop[:2], split_right)) if np.all(np.isfinite(total_cop)) else False
        # the decided rule: a double-support frame is feasible when the total CoP lies in the hull of the two polygons (and the friction holds)
        reasons = [r for r in reasons if "CoP outside" not in r]
        if not ds_feasible:
            reasons.append(f"total CoP outside the hull of the two contact polygons by {1000 * ds_outside:.1f} mm")
        if sweep and ds_feasible and found["solutions"]:
            ds_solutions = found["solutions"]
            feasible_split = found["alpha_range"]
            ranges = [(torque, torque)] if feasible_nominal else []
            first = {}
            for alpha, p_r, p_l in ds_solutions:
                forces2 = {stance[0]: alpha * F, stance[1]: (1.0 - alpha) * F}
                cops2 = {stance[0]: np.r_[p_r, 0.0], stance[1]: np.r_[p_l, 0.0]}
                net2, _ = assemble(forces2, cops2)
                for n, dof in hinges:
                    v = float(net2[dof])
                    lo, hi = first.get(n, (v, v))
                    first[n] = (min(lo, v), max(hi, v))
            if first:
                rng = {n: (min(first[n][0], torque[n]) if feasible_nominal else first[n][0],
                           max(first[n][1], torque[n]) if feasible_nominal else first[n][1]) for n in first}
    return FrameResult(torque=torque, torque_range=rng, force=forces, cop=cops, support=support, split_right=split_right,
                       residual=residual, yaw_moment_nm=float(residual[5]), weight_n=weight, cop_margin_m=margin,
                       friction_ratio=fric, hull_degenerate=degenerate, feasible=not reasons, reasons=reasons, feasible_split=feasible_split, qfrc_net=net,
                       total_cop=total_cop, ds_feasible=ds_feasible, ds_outside_m=ds_outside, ds_solutions=ds_solutions, polygons=polygons,
                       feasible_nominal=feasible_nominal, nominal_in_set=nominal_in_set)


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
        foot = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_BODY, n)
        mujoco.mj_jac(model, d, jp, None, np.asarray(cops[n], float), _contact_body(model, d, foot, cops[n]))
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


def polygon_outside_m(model, qpos, stance, xy, band_m=HULL_BAND_M) -> float:
    """Distance from the floor point xy to the contact polygon of the stance feet, 0 when inside: the polygon of the one stance foot, or
    in double support the convex hull of the two feet's polygons. band_m is which vertices form a polygon (the foot box's vertices within
    band_m of that foot's lowest one), a geometric definition and not a threshold."""
    d = mujoco.MjData(model)
    d.qpos[:] = qpos
    mujoco.mj_kinematics(model, d)
    pts = []
    for n in stance:
        corners, _ = _foot_boxes(model, d, mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_BODY, n))
        pts += contact_polygon(corners, band_m)
    return max(0.0, -margin_in_polygon(metrics.convex_hull(pts), np.asarray(xy, float)[:2]))
