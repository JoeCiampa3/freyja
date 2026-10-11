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
