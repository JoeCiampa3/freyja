"""
Stage 2 T3c.5: where Freyja's whole-body CoP comes from, by segment group. The CoP that balances the horizontal moments is

    p = c_xy - (c_z / F_z) F_xy + (-Hdot_y, +Hdot_x) / F_z,

with c the whole-body CoM, F the total ground force m (a + g) and Hdot the rate of change of the angular momentum about the CoM. Every
piece is a sum over bodies, so it splits by group exactly:

    p = ankle_xy + sum_g (m_g / m) (c_g - ankle_xy)                       (where the group's mass sits)
              + sum_g [ -(c_z / F_z) F_g,xy + (-Hdot_g,y, +Hdot_g,x) / F_z ]   (what the group's motion adds)

F_g = sum over the group of m_i (a_i + g) and Hdot_g = sum of (c_i - c) x m_i a_i + I_i alpha_i + omega_i x (I_i omega_i). Groups: the
stance leg, the swing leg, and the pelvis with the trunk, head and arms.
"""
from __future__ import annotations

import mujoco
import numpy as np

VERSION = "1"
EPS = 1e-6  # s. The rate of change of a body Jacobian along the motion is a central difference of exact Jacobians


def _groups(stance_foot: str) -> dict:
    side = "right" if stance_foot.endswith("right") else "left"
    other = "left" if side == "right" else "right"
    leg = lambda s: [f"thigh_{s}", f"shank_{s}", f"foot_{s}"]
    return {"stance_leg": leg(side), "swing_leg": leg(other),
            "pelvis_trunk": ["pelvis", "abdomen", "thorax", "head_and_neck"] + [f"{seg}_{s}" for s in ("right", "left") for seg in ("upper_arm", "forearm", "hand")]}


def _jacobians(model, q):
    d = mujoco.MjData(model)
    d.qpos[:] = q
    mujoco.mj_kinematics(model, d)
    mujoco.mj_comPos(model, d)
    jp = np.zeros((model.nbody, 3, model.nv))
    jr = np.zeros((model.nbody, 3, model.nv))
    for b in range(1, model.nbody):
        mujoco.mj_jacBodyCom(model, d, jp[b], jr[b], b)
    return d, jp, jr


def body_motion(model, q, qd, qdd) -> dict:
    """Per body: mass, centre of mass, linear acceleration, angular velocity and acceleration (world frame), world inertia."""
    d, jp, jr = _jacobians(model, q)
    qp, qm = q.copy(), q.copy()
    mujoco.mj_integratePos(model, qp, qd, EPS)
    mujoco.mj_integratePos(model, qm, qd, -EPS)
    _, jpp, jrp = _jacobians(model, qp)
    _, jpm, jrm = _jacobians(model, qm)
    out = {}
    for b in range(1, model.nbody):
        name = mujoco.mj_id2name(model, mujoco.mjtObj.mjOBJ_BODY, b)
        a = jp[b] @ qdd + (jpp[b] - jpm[b]) / (2 * EPS) @ qd
        w = jr[b] @ qd
        alpha = jr[b] @ qdd + (jrp[b] - jrm[b]) / (2 * EPS) @ qd
        r = d.ximat[b].reshape(3, 3)
        out[name] = {"mass": float(model.body_mass[b]), "com": d.xipos[b].copy(), "a": a, "w": w, "alpha": alpha,
                     "inertia": r @ np.diag(model.body_inertia[b]) @ r.T}
    return out


def cop_partition(model, q, qd, qdd, stance_foot, ankle_xy, gravity=9.81) -> dict:
    """Per group: mass_fraction, com_minus_ankle_xy (m_g/m (c_g - ankle)) and dynamic_xy. They add to the whole-body CoP:
    ankle + sum(com_minus_ankle_xy) + sum(dynamic_xy) = CoP."""
    bodies = body_motion(model, q, qd, qdd)
    g_vec = np.array([0.0, 0.0, gravity])
    m = sum(v["mass"] for v in bodies.values())
    c = sum(v["mass"] * v["com"] for v in bodies.values()) / m
    force = {n: v["mass"] * (v["a"] + g_vec) for n, v in bodies.items()}
    hdot = {n: np.cross(v["com"] - c, v["mass"] * v["a"]) + v["inertia"] @ v["alpha"] + np.cross(v["w"], v["inertia"] @ v["w"]) for n, v in bodies.items()}
    fz = sum(f[2] for f in force.values())
    out = {}
    for group, names in _groups(stance_foot).items():
        mg = sum(bodies[n]["mass"] for n in names)
        cg = sum(bodies[n]["mass"] * bodies[n]["com"] for n in names) / mg
        fg = sum(force[n] for n in names)
        hg = sum(hdot[n] for n in names)
        out[group] = {"mass_fraction": mg / m, "com_minus_ankle_xy": (mg / m) * (cg[:2] - np.asarray(ankle_xy, float)),
                      "dynamic_xy": -(c[2] / fz) * fg[:2] + np.array([-hg[1], hg[0]]) / fz}
    return out
