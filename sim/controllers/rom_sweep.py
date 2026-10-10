"""
rom_sweep: gantry inverse-dynamics playback. Each limited joint in turn moves, slowly, across `fraction` of its
model range (neutral -> upper -> lower -> neutral, cosine-eased so velocity is zero at every turning point) with
every other joint at neutral. Its own time segment is the measurement window of that joint.

A joint with no model range is not swept: no span is invented. It is reported as skipped with reason 'unlimited'.

params: sweep_s (seconds per joint), fraction (of each limit, default 0.99). The scenario's duration_s must be
sweep_s times the number of limited joints; the runner records what it ran.
"""
import math

import numpy as np

VERSION = "1"

_state = {}


def _joints(model):
    import mujoco
    out = []
    for j in range(model.njnt):
        if model.jnt_type[j] == mujoco.mjtJoint.mjJNT_HINGE:
            out.append((mujoco.mj_id2name(model, mujoco.mjtObj.mjOBJ_JOINT, j), j, bool(model.jnt_limited[j])))
    return out


def measured_joints(model, params):
    return [name for name, _, limited in _joints(model) if limited]


def skipped(model, params):
    return {name: "unlimited" for name, _, limited in _joints(model) if not limited}


def segments(model, params):
    t = float(params["sweep_s"])
    return {name: (i * t, (i + 1) * t) for i, name in enumerate(measured_joints(model, params))}


def reset(model, data, params):
    t = float(params["sweep_s"])
    frac = float(params.get("fraction", 0.99))
    dt = float(model.opt.timestep)
    sweeps = []
    for i, name in enumerate(measured_joints(model, params)):
        j = next(j for n, j, _ in _joints(model) if n == name)
        lo, hi = model.jnt_range[j]
        waypoints = [0.0, frac * hi, frac * lo, 0.0]
        legs = np.abs(np.diff(waypoints))  # leg durations proportional to the distance travelled, so speed is even
        durations = t * legs / legs.sum()
        edges = np.round(np.concatenate([[0.0], np.cumsum(durations)]) / dt) * dt  # turning points on sample times, so the
        edges[-1] = t  #                                                          sweep lands exactly on its extremes
        sweeps.append({"t0": i * t, "t1": (i + 1) * t, "q": int(model.jnt_qposadr[j]), "dof": int(model.jnt_dofadr[j]),
                       "waypoints": waypoints, "edges": edges})
    _state.update(sweeps=sweeps, q0=data.qpos.copy(), dt=dt)


def _profile(sweep, u):
    """Position, velocity and acceleration at time u (s) into a joint's own segment."""
    edges, w = sweep["edges"], sweep["waypoints"]
    k = int(np.clip(np.searchsorted(edges, u, side="right") - 1, 0, len(w) - 2))
    d = edges[k + 1] - edges[k]
    s = min(max((u - edges[k]) / d, 0.0), 1.0)
    span = w[k + 1] - w[k]
    return (w[k] + span * (1 - math.cos(math.pi * s)) / 2,
            span * math.pi * math.sin(math.pi * s) / (2 * d),
            span * math.pi ** 2 * math.cos(math.pi * s) / (2 * d * d))


def prescribe(model, data, t):
    data.qpos[:] = _state["q0"]
    data.qvel[:] = 0.0
    data.qacc[:] = 0.0
    for sw in _state["sweeps"]:
        if sw["t0"] <= t < sw["t1"]:
            # whole steps into the segment, so a turning point falls on the same side of its edge whatever the offset
            q, qd, qdd = _profile(sw, round((t - sw["t0"]) / _state["dt"]) * _state["dt"])
            data.qpos[sw["q"]], data.qvel[sw["dof"]], data.qacc[sw["dof"]] = q, qd, qdd
            return
