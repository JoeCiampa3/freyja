"""
pd_hold: ideal-torque PD that holds every hinge at the angle it has at reset (the neutral pose).

The torque is written to data.qfrc_applied, so the integrator sees it explicitly. That is only stable while
the gain times the timestep stays small against the joint's effective inertia, and the light distal joints
(hands, ankle inversion) have very little. So each joint's gains are scaled to its own effective inertia at the
pose (the mass-matrix diagonal, taken once at reset) and capped:

    kp_j = min(kp_nm_per_rad, I_j * (stability_cap / dt)^2)      N m/rad
    kd_j = 2 * damping_ratio * sqrt(kp_j * I_j)                  N m s/rad

stability_cap is the largest natural-frequency-times-timestep product allowed (explicit PD is stable below about
2; 0.25 leaves a wide margin). The gains actually used are recorded in the scenario file (params) and not
hidden here; params: kp_nm_per_rad, damping_ratio, stability_cap.
"""
import numpy as np

VERSION = "1"

_state = {}


def reset(model, data, params):
    import mujoco
    hinges = [j for j in range(model.njnt) if model.jnt_type[j] == mujoco.mjtJoint.mjJNT_HINGE]
    dof = np.array([model.jnt_dofadr[j] for j in hinges])
    qadr = np.array([model.jnt_qposadr[j] for j in hinges])
    mass = np.zeros((model.nv, model.nv))
    mujoco.mj_fullM(model, data, mass)
    inertia = np.diag(mass)[dof]
    cap = float(params.get("stability_cap", 0.25)) / model.opt.timestep
    kp = np.minimum(float(params["kp_nm_per_rad"]), inertia * cap ** 2)
    kd = 2.0 * float(params.get("damping_ratio", 1.0)) * np.sqrt(kp * inertia)
    _state.update(dof=dof, qadr=qadr, kp=kp, kd=kd, target=data.qpos[qadr].copy())


def step(model, data, t):
    s = _state
    data.qfrc_applied[s["dof"]] = s["kp"] * (s["target"] - data.qpos[s["qadr"]]) - s["kd"] * data.qvel[s["dof"]]
