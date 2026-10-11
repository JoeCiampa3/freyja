"""
Stage 2 T2: retarget one stride of Camargo et al. kinematics onto Freyja and make it a smooth periodic cycle with analytic
qpos, qvel and qacc, ready for inverse dynamics.

Rules (all recorded in the gait record):
  - Hinges: dataset coordinate x mapping sign (sim/scenarios/gait/camargo_mapping.yaml), degrees to radians. Spine, neck and arms
    are held at the standing pose.
  - Periodic cycle: a stride ends where the next begins but not exactly where it started. The linear drift between the first and
    last sample is removed from every signal (the size is reported as the wrap gap), the 100 unique samples are tiled three times,
    low-passed with a zero-lag (forward-backward) Butterworth, and the middle copy is fitted with a periodic cubic spline. qvel
    and qacc are the spline's analytic first and second derivatives, so they are exactly consistent with qpos.
  - Root orientation: the dataset's pelvis tilt, list and rotation (OpenSim body-fixed order Rz Rx Ry), converted to the model's
    axes. The free joint's angular velocity and acceleration are in the body frame, as MuJoCo expects.
  - Root horizontal position: the dataset's pelvis translation, drift removed, scaled by the leg-length ratio. On a treadmill this
    is the oscillation about a fixed point; the belt carries the ground backward, so the model walks in place.
  - Root height: the lowest corner of either foot box sits on z = 0 (the minimum rule), then the height is low-passed like every
    other signal (the minimum switches feet at each double support and would otherwise leave a velocity kink). The consequence
    is a small penetration and float, reported by `foot_metrics`, never clipped.
"""
from __future__ import annotations

import numpy as np
import mujoco
from scipy.interpolate import CubicSpline
from scipy.signal import butter, filtfilt

VERSION = "1"
CUTOFF_HZ = 6.0  # Hz. The dataset's own inverse dynamics are filtered at 6 Hz (RUN_OSIM.m); gait energy lies below ~10 Hz.
FILTER_ORDER = 2  # per pass; forward-backward makes it a 4th-order zero-lag response
N_UNIQUE = 100  # 101 phase points, the last repeating the first
SUBJECT_LEG_FRACTION = 0.491  # hip-to-ankle length / stature = thigh 0.245 + shank 0.246 (Winter, Biomechanics and Motor Control of Human Movement)
FOOT_BODIES = ("foot_right", "foot_left")

_IK = None  # set lazily to avoid importing the analysis folder at import time


def _channels():
    global _IK
    if _IK is None:
        import sys
        from pathlib import Path
        sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "analysis"))
        import ingest_camargo as ic
        _IK = ic.IK_CHANNELS
    return _IK


def _hinge_adr(model, name):
    return int(model.jnt_qposadr[mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_JOINT, name)])


ROOT_RULES = ("foot_min", "pelvis_dataset")
ROOT_REFS = ("hip_midpoint", "pelvis_origin")


def dataset_hip_mid_lab(ik, hip_in_pelvis):
    """(n, 3) midpoint of the dataset model's hip joint centres in the lab frame (x right, y up, z backward), from the pelvis
    position and orientation (OpenSim body-fixed order Rz Rx Ry of tilt, list, rotation) and the hip centre in the pelvis
    frame ([x forward, y up, half separation], metres). Unfiltered, as measured."""
    names = _channels()
    col = lambda n: ik[:, names.index(n)]
    h = np.array([hip_in_pelvis[0], hip_in_pelvis[1], 0.0])
    out = np.zeros((ik.shape[0], 3))
    for k in range(ik.shape[0]):
        a = np.deg2rad([col("pelvis_tilt")[k], col("pelvis_list")[k], col("pelvis_rotation")[k]])
        E, _, _ = euler_zxy(a, np.zeros(3), np.zeros(3))
        out[k] = np.array([col("pelvis_tx")[k], col("pelvis_ty")[k], col("pelvis_tz")[k]]) + E @ h
    return out


def model_hip_mid(model, q):
    """Midpoint of Freyja's hip joint centres in the world for the pose q, and its offset from the root origin in the root frame
    at the neutral pose (the lumbosacral origin: 56.6 mm anterior, 97.5 mm below in this model)."""
    d = mujoco.MjData(model)
    d.qpos[:] = q
    mujoco.mj_kinematics(model, d)
    ids = [mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_BODY, n) for n in ("thigh_right", "thigh_left")]
    return 0.5 * (d.xpos[ids[0]] + d.xpos[ids[1]])


def model_hip_offset(model):
    """Hip-midpoint minus root origin, in the root frame, at the neutral pose."""
    d = mujoco.MjData(model)
    mujoco.mj_forward(model, d)
    return model_hip_mid(model, d.qpos) - d.xpos[int(model.jnt_bodyid[0])]


def leg_length_ratio(model, height_m: float) -> float:
    """Freyja's hip-to-ankle length at the neutral pose over the subject's estimated one (SUBJECT_LEG_FRACTION x stature)."""
    d = mujoco.MjData(model)
    mujoco.mj_forward(model, d)
    ids = {n: mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_BODY, n) for n in ("thigh_right", "foot_right")}
    leg = float(np.linalg.norm(d.xpos[ids["thigh_right"]] - d.xpos[ids["foot_right"]]))
    return leg / (SUBJECT_LEG_FRACTION * height_m)


# ------------------------------------------------------------------ rotations with derivatives

def _K(axis):
    k = np.zeros((3, 3))
    i, j = [(1, 2), (2, 0), (0, 1)][axis]
    k[i, j], k[j, i] = -1.0, 1.0
    return k  # rotation about the axis by a is expm(a K)


def _R(axis, a):
    k = _K(axis)
    return np.eye(3) + np.sin(a) * k + (1 - np.cos(a)) * (k @ k)


def euler_zxy(a, ad, add):
    """E = Rz(a0) Rx(a1) Ry(a2) and its first and second time derivatives (product rule), for angles a with rates ad, add."""
    axes = (2, 0, 1)
    A = [_R(ax, a[i]) for i, ax in enumerate(axes)]
    K = [_K(ax) for ax in axes]
    dA = [ad[i] * K[i] @ A[i] for i in range(3)]
    ddA = [add[i] * K[i] @ A[i] + ad[i] ** 2 * K[i] @ K[i] @ A[i] for i in range(3)]
    E = A[0] @ A[1] @ A[2]
    dE = dA[0] @ A[1] @ A[2] + A[0] @ dA[1] @ A[2] + A[0] @ A[1] @ dA[2]
    ddE = (ddA[0] @ A[1] @ A[2] + A[0] @ ddA[1] @ A[2] + A[0] @ A[1] @ ddA[2]
           + 2 * (dA[0] @ dA[1] @ A[2] + dA[0] @ A[1] @ dA[2] + A[0] @ dA[1] @ dA[2]))
    return E, dE, ddE


def _vee(s):
    return np.array([s[2, 1], s[0, 2], s[1, 0]])


# ------------------------------------------------------------------ the cycle

def _lowpass_periodic(x, fs, cutoff):
    """x (N_UNIQUE, c): periodic signal. Tile three times, zero-lag low-pass, return the middle copy."""
    b, a = butter(FILTER_ORDER, cutoff / (fs / 2.0))
    ext = np.tile(x, (3, 1))
    return filtfilt(b, a, ext, axis=0)[len(x):2 * len(x)]


def _detrend_periodic(x):
    """x (101, c) -> (100, c) with the linear drift between the first and last samples removed; also returns the wrap gap."""
    ph = np.linspace(0.0, 1.0, x.shape[0])[:, None]
    gap = x[-1] - x[0]
    return (x - gap * ph)[:N_UNIQUE], gap


def filter_cycle(x, T, cutoff_hz=CUTOFF_HZ):
    """x (101, c) over one stride of duration T: the same drift removal and zero-lag low-pass the kinematics get, returned on
    101 points (the last repeats the first). For comparing a measured signal with kinematics-derived ones like for like."""
    x = np.asarray(x, float)
    x = x[:, None] if x.ndim == 1 else x
    xd, _ = _detrend_periodic(x)
    xf = _lowpass_periodic(xd, N_UNIQUE / T, cutoff_hz)
    return np.vstack([xf, xf[:1]])


class Cycle:
    """One stride as a continuous periodic function of time. `ik` is (101, n_ik) in the dataset's channels and units, `T` the
    stride duration in seconds, `scale` the leg-length ratio applied to the pelvis translation."""

    def __init__(self, model, mapping, stand_qpos, ik, T, scale, cutoff_hz=CUTOFF_HZ,
                 tilt_offset_deg=0.0, root_rule="pelvis_dataset", hip_in_pelvis_os=None, root_ref=None):
        if root_rule not in ROOT_RULES:
            raise ValueError(f"root_rule must be one of {ROOT_RULES}")
        self.root_rule = root_rule
        if root_ref is None:
            root_ref = "hip_midpoint" if hip_in_pelvis_os is not None else "pelvis_origin"
        if root_ref not in ROOT_REFS or (root_ref == "hip_midpoint" and hip_in_pelvis_os is None):
            raise ValueError("root_ref hip_midpoint needs the dataset hip centre (hip_in_pelvis_os)")
        self.root_ref = root_ref
        self.model, self.T, self.scale, self.cutoff_hz = model, float(T), float(scale), float(cutoff_hz)
        self._work = mujoco.MjData(model)
        self.stand = np.asarray(stand_qpos, float).copy()
        names = _channels()
        col = lambda n: ik[:, names.index(n)]
        self.lab_to_model = np.array(mapping["frame"]["lab_to_model"], float)
        self.B = np.array(mapping["frame"]["osim_pelvis_to_model"], float)
        self.joint_adr, series = [], []
        for joint, spec in mapping["joints"].items():
            self.joint_adr.append(_hinge_adr(model, joint))
            series.append(np.deg2rad(spec["sign"] * col(spec["dataset"])))
        eul = [np.deg2rad(col(n)) for n in mapping["frame"]["pelvis_euler"]]
        self.h_f = model_hip_offset(model)
        if root_ref == "hip_midpoint":
            hm = dataset_hip_mid_lab(ik, hip_in_pelvis_os)  # from the measured (unadjusted) pelvis orientation
        else:
            hm = np.stack([col("pelvis_tx"), col("pelvis_ty"), col("pelvis_tz")], axis=1)
        # Pelvis pitch: the dataset supplies only the oscillation. The cycle-mean pitch is removed and the mean is set to the design
        # parameter tilt_offset_deg (positive = anterior), relative to the standing pose's pelvis orientation from stand_static.
        # The model's zero and OpenSim's zero need not coincide, and the subject's static pitch is standing posture, not an offset.
        # Which dataset coordinate is the sagittal pitch is a property of the lab frame (see camargo_mapping.yaml): here pelvis_list.
        pitch = mapping["frame"]["pelvis_pitch"]
        pi = mapping["frame"]["pelvis_euler"].index(pitch["coordinate"])
        eul[pi] = eul[pi] - eul[pi][:N_UNIQUE].mean() + pitch["sign"] * np.deg2rad(tilt_offset_deg)
        self.R_stand = np.zeros(9)
        mujoco.mju_quat2Mat(self.R_stand, self.stand[3:7])
        self.R_stand = self.R_stand.reshape(3, 3)
        pos_model = (self.lab_to_model @ hm.T).T  # lab -> model axes
        xy = scale * pos_model[:, :2]
        X = np.column_stack(series + eul + [xy, scale * hm[:, 1]])
        Xd, self.wrap_gap = _detrend_periodic(X)
        fs = N_UNIQUE / self.T
        if cutoff_hz >= fs / 2:
            raise ValueError("cutoff above the Nyquist rate of the phase grid")
        Xf = _lowpass_periodic(Xd, fs, cutoff_hz)
        self._nj, self._ne = len(series), 3
        self._t_grid = np.linspace(0.0, self.T, N_UNIQUE + 1)
        self._spl = self._spline(Xf)
        # root height from the minimum rule on the filtered kinematics, then filtered like the rest
        if root_rule == "foot_min":
            zraw = np.array([-self._lowest_z_at(self._t_grid[k]) for k in range(N_UNIQUE)])[:, None]
            self._zspl = self._spline(_lowpass_periodic(zraw, fs, cutoff_hz))
        else:
            # the dataset's own pelvis height (already filtered above), shifted so the lowest foot point of the whole cycle
            # touches z = 0 and nothing penetrates by more than the filter allows
            zs = Xf[:, self._nj + 5][:, None]
            self._zspl = self._spline(zs)
            lows = np.array([self._lowest_z_at(self._t_grid[k]) for k in range(N_UNIQUE)])  # with the unshifted height
            self._zspl = self._spline(zs - lows.min())

    def _spline(self, X):
        Xc = np.vstack([X, X[:1]])
        return CubicSpline(self._t_grid, Xc, bc_type="periodic")

    # -- evaluation
    def _state(self, t, with_z=True):
        t = t % self.T
        v, d1, d2 = self._spl(t), self._spl(t, 1), self._spl(t, 2)
        z = (self._zspl(t)[0], self._zspl(t, 1)[0], self._zspl(t, 2)[0]) if with_z else (0.0, 0.0, 0.0)
        return v, d1, d2, z

    def _assemble(self, v, d1, d2, z):
        m = self.model
        q, qd, qdd = self.stand.copy(), np.zeros(m.nv), np.zeros(m.nv)
        for i, adr in enumerate(self.joint_adr):
            dof = int(m.jnt_dofadr[np.searchsorted(m.jnt_qposadr, adr)])
            q[adr], qd[dof], qdd[dof] = v[i], d1[i], d2[i]
        nj = self._nj
        E, dE, ddE = euler_zxy(v[nj:nj + 3], d1[nj:nj + 3], d2[nj:nj + 3])
        Rm = self.R_stand @ self.lab_to_model @ E @ self.B.T
        quat = np.zeros(4)
        mujoco.mju_mat2Quat(quat, Rm.ravel())
        w_os = _vee(E.T @ dE)
        a_os = _vee(dE.T @ dE + E.T @ ddE)
        if self.root_ref == "hip_midpoint":
            dRm = self.R_stand @ self.lab_to_model @ dE @ self.B.T
            ddRm = self.R_stand @ self.lab_to_model @ ddE @ self.B.T
            off, doff, ddoff = Rm @ self.h_f, dRm @ self.h_f, ddRm @ self.h_f
            pos = np.array([v[nj + 3] - off[0], v[nj + 4] - off[1], z[0] - off[2]])
            vel = np.array([d1[nj + 3] - doff[0], d1[nj + 4] - doff[1], z[1] - doff[2]])
            acc = np.array([d2[nj + 3] - ddoff[0], d2[nj + 4] - ddoff[1], z[2] - ddoff[2]])
            if self.root_rule == "foot_min":  # the diagnostic rule sets the root height directly
                pos[2], vel[2], acc[2] = z
        else:
            pos, vel, acc = np.array([v[nj + 3], v[nj + 4], z[0]]), np.array([d1[nj + 3], d1[nj + 4], z[1]]), np.array([d2[nj + 3], d2[nj + 4], z[2]])
        q[:3] = pos
        q[3:7] = quat
        qd[:3] = vel
        qd[3:6] = self.B @ w_os
        qdd[:3] = acc
        qdd[3:6] = self.B @ a_os
        return q, qd, qdd

    def eval(self, t):
        return self._assemble(*self._state(t))

    def grid(self):
        """qpos, qvel, qacc at the 101 phase points (the last repeats the first)."""
        out = [self.eval(self.T * k / N_UNIQUE) for k in range(N_UNIQUE + 1)]
        return tuple(np.array([o[i] for o in out]) for i in range(3))

    # -- foot geometry
    def _corner_z(self, q, foot=None):
        m = self.model
        d = self._work
        d.qpos[:] = q
        mujoco.mj_kinematics(m, d)
        zs = []
        for g in range(m.ngeom):
            b = mujoco.mj_id2name(m, mujoco.mjtObj.mjOBJ_BODY, int(m.geom_bodyid[g]))
            if m.geom_type[g] == mujoco.mjtGeom.mjGEOM_BOX and b in FOOT_BODIES and (foot is None or b == FOOT_BODIES[foot]):
                r, c, s = d.geom_xmat[g].reshape(3, 3), d.geom_xpos[g], m.geom_size[g]
                for sx in (-1, 1):
                    for sy in (-1, 1):
                        for sz in (-1, 1):
                            zs.append((c + r @ (np.array([sx, sy, sz]) * s))[2])
        return min(zs)

    def lowest_foot_z(self, q, foot=None):
        """Height of the lowest foot-box corner (of one foot if given) for the pose q."""
        return self._corner_z(q, foot)

    def _lowest_z_at(self, t):
        if self.root_rule == "foot_min":
            v, d1, d2, z = self._state(t, with_z=False)
        else:
            v, d1, d2, z = self._state(t)
        q, _, _ = self._assemble(v, d1, d2, z)
        return self._corner_z(q)

    def wrap_gap_deg(self):
        """Per mapped joint, the drift removed between the first and last sample of the stride (degrees), keyed by model joint."""
        names = [mujoco.mj_id2name(self.model, mujoco.mjtObj.mjOBJ_JOINT, int(np.searchsorted(self.model.jnt_qposadr, a))) for a in self.joint_adr]
        return {n: float(np.degrees(g)) for n, g in zip(names, self.wrap_gap[:self._nj])}


# ------------------------------------------------------------------ reporting (nothing here changes the kinematics)

def limit_fraction(model, qpos_frames):
    """Fraction of frames outside each limited hinge's model range."""
    out = {}
    for j in range(model.njnt):
        if model.jnt_type[j] == mujoco.mjtJoint.mjJNT_HINGE and model.jnt_limited[j]:
            lo, hi = model.jnt_range[j]
            x = qpos_frames[:, model.jnt_qposadr[j]]
            out[mujoco.mj_id2name(model, mujoco.mjtObj.mjOBJ_JOINT, j)] = float(np.mean((x < lo) | (x > hi)))
    return out


def foot_metrics(model, cycle, stance_mask, belt_speed_mps):
    """Penetration, float, swing clearance and slip of the retargeted feet. `stance_mask` is (2, 101) or (101, 2): the dataset's
    stance flags of the right and left foot. Slip is the horizontal velocity of the lowest corner of a stance foot relative to
    the belt, which moves at -belt_speed_mps along x."""
    mask = np.asarray(stance_mask, bool)
    if mask.shape[0] == 2:
        mask = mask.T
    qs, qds, _ = cycle.grid()
    m = model
    pen, flt, clear, slip = [], [], [], []
    d = mujoco.MjData(m)
    for k in range(qs.shape[0]):
        for f in (0, 1):
            low = cycle.lowest_foot_z(qs[k], foot=f)
            if mask[k, f]:
                pen.append(max(0.0, -low)); flt.append(max(0.0, low))
                d.qpos[:] = qs[k]; d.qvel[:] = qds[k]
                mujoco.mj_kinematics(m, d); mujoco.mj_comPos(m, d)
                slip.append(_corner_velocity_xy(m, d, FOOT_BODIES[f]) + np.array([belt_speed_mps, 0.0]))
            else:
                clear.append(low)
    slip = np.linalg.norm(np.array(slip), axis=1)
    return {"stance_penetration_max_m": float(max(pen)), "stance_float_max_m": float(max(flt)),
            "swing_clearance_min_m": float(min(clear)), "stance_slip_rms_mps": float(np.sqrt(np.mean(slip ** 2))),
            "stance_slip_max_mps": float(slip.max())}


def _corner_velocity_xy(m, d, body):
    """Horizontal world velocity of the lowest foot-box corner of `body`."""
    best, best_z = None, np.inf
    for g in range(m.ngeom):
        if m.geom_type[g] == mujoco.mjtGeom.mjGEOM_BOX and mujoco.mj_id2name(m, mujoco.mjtObj.mjOBJ_BODY, int(m.geom_bodyid[g])) == body:
            r, c, s = d.geom_xmat[g].reshape(3, 3), d.geom_xpos[g], m.geom_size[g]
            for sx in (-1, 1):
                for sy in (-1, 1):
                    for sz in (-1, 1):
                        p = c + r @ (np.array([sx, sy, sz]) * s)
                        if p[2] < best_z:
                            best, best_z = p, p[2]
    jacp = np.zeros((3, m.nv))
    mujoco.mj_jac(m, d, jacp, None, best, mujoco.mj_name2id(m, mujoco.mjtObj.mjOBJ_BODY, body))
    return (jacp @ d.qvel)[:2]
