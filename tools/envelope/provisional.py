"""PROVISIONAL landmarks from a crude geometric heuristic, so Phase B can be developed before Joe's picks exist.

Not anatomy: heights are fixed fractions of stature and the points are extremal vertices of a slab. Every output
carries `provisional: true` and no result built on it is a result of the trial.
"""
from __future__ import annotations

import numpy as np

from . import landmarks, meshio

ASIS_HEIGHT = 0.545      # ASIS height / stature, typical adult female ~0.53-0.56 (heuristic only)
PSIS_HEIGHT = 0.575      # PSIS sits a little above the ASIS (heuristic only)
KNEE_HEIGHT = 0.285      # femoral epicondyle height / stature (heuristic only)
TRUNK_HALF_WIDTH_MM = 200.0   # keeps the arms out of the pelvis slab


def provisional_landmarks(vertices_dm_mh) -> dict:
    s = meshio.to_sheet_mm(vertices_dm_mh)          # x anterior, y left, z up (mm)
    z0, H = s[:, 2].min(), np.ptp(s[:, 2])

    def band(frac, half=10.0):
        return np.abs(s[:, 2] - (z0 + frac * H)) < half

    pelvis = band(ASIS_HEIGHT) & (np.abs(s[:, 1]) < TRUNK_HALF_WIDTH_MM)
    ids = {}
    for name, sign in (("ASIS_R", -1), ("ASIS_L", 1)):
        m = np.flatnonzero(pelvis & (sign * s[:, 1] > 40))
        ids[name] = int(m[np.argmax(s[m, 0] + 0.5 * np.abs(s[m, 1]))])
    m = np.flatnonzero(band(PSIS_HEIGHT) & (np.abs(s[:, 1]) < 15))
    ids["SACRAL_MID"] = int(m[np.argmin(s[m, 0])])
    knee = np.flatnonzero(band(KNEE_HEIGHT, 6.0) & (s[:, 1] < -20) & (s[:, 1] > -TRUNK_HALF_WIDTH_MM))
    ids["EPI_MED_R"] = int(knee[np.argmax(s[knee, 1])])
    ids["EPI_LAT_R"] = int(knee[np.argmin(s[knee, 1])])
    return {"schema": landmarks.SCHEMA, "topology": landmarks.TOPOLOGY, "provisional": True,
            "landmarks": {n: {"vertex": ids[n]} for n in landmarks.REQUIRED}}
