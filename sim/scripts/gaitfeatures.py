"""
Gait-feature checks on joint angles in the MODEL convention (flexion, adduction and dorsiflexion positive). They validate the
sign mapping in sim/scenarios/gait/camargo_mapping.yaml: flip the sign of one joint and its feature must fail. Every
threshold is a physiological range for adult walking at 1.4 to 1.6 m/s, written before looking at the dataset's numbers.

Input: a dict of arrays shaped (strides, 101) over the right-heel-strike-to-right-heel-strike phase, for the RIGHT limb:
hip_fe, knee, ankle, hip_aa (degrees), plus toe_off_phase shaped (strides,) (fraction of the stride).
"""
from __future__ import annotations

import numpy as np

VERSION = "1"
KNEE_HS_MAX_DEG = 25.0            # knee near full extension at heel strike: 0 to 20 deg in healthy gait (Perry & Burnfield 2010)
KNEE_SWING_PEAK_DEG = (55.0, 75.0)  # peak swing flexion (the brief's range)
HIP_EXT_WINDOW = (0.35, None)     # peak hip extension occurs in late stance: from 35% to toe-off + HIP_EXT_AFTER_TO
HIP_EXT_AFTER_TO = 0.10           # fraction of the stride
HIP_RANGE_MIN_DEG = 20.0          # peak flexion minus peak extension over the stride, at least this
ANKLE_PF_TOE_OFF_MAX_DEG = 0.0    # plantarflexion at toe-off: the angle there is below neutral
ANKLE_PF_BELOW_PEAK_DEG = 15.0    # and well below the stance dorsiflexion peak


def _at_phase(x, phase):
    """x (S, 101) sampled at phase `phase` (S,) by linear interpolation."""
    grid = np.linspace(0.0, 1.0, x.shape[1])
    return np.array([np.interp(p, grid, row) for p, row in zip(phase, x)])


def features(a: dict) -> dict:
    to = np.asarray(a["toe_off_phase"], float)
    n = a["knee"].shape[1]
    ph = np.linspace(0.0, 1.0, n)
    out = {}
    out["knee_flexion_heel_strike_deg"] = float(a["knee"][:, 0].mean())
    out["knee_swing_peak_deg"] = float(a["knee"].max(axis=1).mean())
    hip = a["hip_fe"]
    lo = HIP_EXT_WINDOW[0]
    mins = []
    for row, t in zip(hip, to):
        w = (ph >= lo) & (ph <= t + HIP_EXT_AFTER_TO)
        mins.append(ph[w][np.argmin(row[w])] if w.any() else np.nan)
        # the minimum over the whole stride must be the one inside the window
        if row[w].min() > row.min() + 1e-9:
            mins[-1] = np.nan
    out["hip_extension_in_late_stance_fraction"] = float(np.mean(~np.isnan(mins)))
    out["hip_range_deg"] = float((hip.max(axis=1) - hip.min(axis=1)).mean())
    out["ankle_toe_off_deg"] = float(_at_phase(a["ankle"], to).mean())
    out["ankle_toe_off_below_peak_deg"] = float((a["ankle"].max(axis=1) - _at_phase(a["ankle"], to)).mean())
    stance = np.array([row[ph <= t].mean() for row, t in zip(a["hip_aa"], to)])
    swing = np.array([row[ph > t].mean() for row, t in zip(a["hip_aa"], to)])
    out["hip_adduction_stance_minus_swing_deg"] = float((stance - swing).mean())
    return out


def check_all(a: dict) -> list:
    """Names of the features that fail; an empty list means the sign mapping is consistent with normal gait."""
    f = features(a)
    failed = []
    if not f["knee_flexion_heel_strike_deg"] < KNEE_HS_MAX_DEG:
        failed.append("knee_extended_heel_strike")
    if not KNEE_SWING_PEAK_DEG[0] <= f["knee_swing_peak_deg"] <= KNEE_SWING_PEAK_DEG[1]:
        failed.append("knee_swing_peak")
    if not (f["hip_extension_in_late_stance_fraction"] > 0.9 and f["hip_range_deg"] >= HIP_RANGE_MIN_DEG):
        failed.append("hip_extension_late_stance")
    if not (f["ankle_toe_off_deg"] < ANKLE_PF_TOE_OFF_MAX_DEG and f["ankle_toe_off_below_peak_deg"] > ANKLE_PF_BELOW_PEAK_DEG):
        failed.append("ankle_plantarflexed_toe_off")
    if not f["hip_adduction_stance_minus_swing_deg"] > 0.0:
        failed.append("hip_adduction_stance")
    return failed
