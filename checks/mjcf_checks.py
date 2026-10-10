"""
The MJCF checks (check.mjcf.*). Each reads a checklib.Context: the compiled model at the neutral
pose and the snapshot. Every tolerance is a named constant with its unit and its reason.
"""
from __future__ import annotations

import math
from pathlib import Path

import numpy as np

import checklib as cl
from checklib import ADVISORY, FAIL, GATE, PASS, SKIP, Result, check

POLARITY_FILE = Path(__file__).resolve().parent / "joint_polarity.yaml"

# ---- tolerances ------------------------------------------------------------------------------
# mass_closure
MASS_CLOSURE_REL = 1e-9  # relative. The snapshot carries 12 significant digits and MuJoCo sums in float64.
MASS_TARGET_REL = 0.0015  # relative (0.15%). The model is 64.935 kg against the 65 kg target (0.1%): the
#                           difference is rounding in Dumas' published segment mass fractions (docs/memos/memo1b.md).
# mirror
MIRROR_REL = 1e-9  # relative. Left values are the right values with a sign flip, so they match to float rounding.
MIRROR_ABS = 1e-12  # absolute floor, in the unit of the quantity, for values that are essentially zero.
# joint_signs
PROBE_MIN_DISPLACEMENT_M = 1e-3  # m. A probe that moves less than 1 mm cannot show a sign (it sits on the axis).
# floor_contact
FLOOR_TOL_M = 1e-3  # m. Lowest collision point within 1 mm of z = 0.
# stature_chain
STATURE_TOL_M = 0.020  # m. The sheet's own integrity panel records a definitional offset of -14.684 mm between
#                        the summed chain (pelvis + abdomen + thorax + head/neck length) and the target stature.
# com
COM_PCT_STATURE = 55.88  # % of stature, Virmavirta and Isolehto reaction-board study
COM_PCT_HALF_BAND = 0.52  # % of stature, the study's reported spread
COM_LATERAL_TOL_M = 1e-3  # m. Dumas segment CoM y values are small but non-zero, so a whole-body offset of
#                           a fraction of a millimetre is expected; several millimetres would mean a build error.


def _close(a, b):
    return np.isclose(a, b, rtol=MIRROR_REL, atol=MIRROR_ABS)


def _mj():
    import mujoco
    return mujoco


# ================================================================================ mass_closure

@check("check.mjcf.mass_closure", GATE, also=["check.mjcf.mass_closure.target"])
def mass_closure(ctx):
    """Model mass equals the sum of the snapshot segment masses (gate); within 0.15% of the target (advisory)."""
    model_mass = float(sum(ctx.model.body_mass[1:]))
    segments = {k: v for k, v in ctx.snapshot.items() if k.endswith("_mass") and k != "target_mass"}
    total = sum(segments.values())
    rel = abs(model_mass - total) / total
    closure = Result("check.mjcf.mass_closure", GATE, PASS if rel <= MASS_CLOSURE_REL else FAIL,
                     f"model {model_mass:.9g} kg, snapshot segments {total:.9g} kg, relative difference {rel:.2e} "
                     f"(limit {MASS_CLOSURE_REL:g})",
                     {"model_mass_kg": model_mass, "snapshot_mass_kg": total, "relative_difference": rel,
                      "segments": len(segments)})
    target = ctx.snapshot.get("target_mass")
    if target is None:
        advisory = Result("check.mjcf.mass_closure.target", ADVISORY, SKIP, "no target_mass in the snapshot (the 'targets' range is absent)")
    else:
        err = abs(model_mass - target) / target
        advisory = Result("check.mjcf.mass_closure.target", ADVISORY, PASS if err <= MASS_TARGET_REL else FAIL,
                          f"model {model_mass:.6g} kg against target {target:g} kg: {err * 100:.3f}% (limit {MASS_TARGET_REL * 100:g}%)",
                          {"model_mass_kg": model_mass, "target_mass_kg": target, "relative_error": err})
    return [closure, advisory]


# ================================================================================ mirror

def _full_inertia(model, i):
    """3x3 inertia tensor in the body frame from MuJoCo's principal moments and orientation."""
    mj = _mj()
    r = np.zeros(9)
    mj.mju_quat2Mat(r, model.body_iquat[i])
    r = r.reshape(3, 3)
    return r @ np.diag(model.body_inertia[i]) @ r.T


def _bilateral_names(names):
    return [(n, n[:-len("_right")] + "_left") for n in names if n.endswith("_right") and n[:-len("_right")] + "_left" in names]


@check("check.mjcf.mirror", GATE)
def mirror(ctx):
    """Every right/left pair is a mirror image about the sagittal plane (MuJoCo y)."""
    mj, m = _mj(), ctx.model
    problems, worst = [], 0.0

    def expect(label, got, want):
        nonlocal worst
        worst = max(worst, float(np.max(np.abs(np.asarray(got) - np.asarray(want)))))
        if not np.all(_close(got, want)):
            problems.append(f"{label}: {np.round(got, 9).tolist()} vs {np.round(want, 9).tolist()}")

    bodies = {mj.mj_id2name(m, mj.mjtObj.mjOBJ_BODY, i): i for i in range(1, m.nbody)}
    for r_name, l_name in _bilateral_names(bodies):
        r, l = bodies[r_name], bodies[l_name]
        expect(f"{l_name} mass", m.body_mass[l], m.body_mass[r])
        expect(f"{l_name} principal inertia", np.sort(m.body_inertia[l]), np.sort(m.body_inertia[r]))
        flip_pos = np.array([1, -1, 1])
        expect(f"{l_name} position (y negates)", m.body_pos[l], m.body_pos[r] * flip_pos)
        expect(f"{l_name} CoM (y negates)", m.body_ipos[l], m.body_ipos[r] * flip_pos)
        ir, il = _full_inertia(m, r), _full_inertia(m, l)
        expect(f"{l_name} Ixx Iyy Izz", np.diag(il), np.diag(ir))
        expect(f"{l_name} Ixz (equal)", il[0, 2], ir[0, 2])
        expect(f"{l_name} Ixy Iyz (negate)", [il[0, 1], il[1, 2]], [-ir[0, 1], -ir[1, 2]])

    joints = {mj.mj_id2name(m, mj.mjtObj.mjOBJ_JOINT, i): i for i in range(m.njnt)}
    pairs = _bilateral_names([n for n in joints if n])
    for r_name, l_name in pairs:
        r, l = joints[r_name], joints[l_name]
        expect(f"{l_name} axis (x and z negate)", m.jnt_axis[l], m.jnt_axis[r] * np.array([-1, 1, -1]))
        expect(f"{l_name} range", m.jnt_range[l], m.jnt_range[r])
        expect(f"{l_name} anchor (y negates)", m.jnt_pos[l], m.jnt_pos[r] * np.array([1, -1, 1]))
        if m.jnt_limited[l] != m.jnt_limited[r]:
            problems.append(f"{l_name}: limited flag differs from {r_name}")
    n_bodies = len(_bilateral_names(bodies))
    if n_bodies == 0:
        problems.append("no right/left body pairs found")
    shown = "; ".join(problems[:8]) + (f"; ... and {len(problems) - 8} more" if len(problems) > 8 else "")
    return Result("check.mjcf.mirror", GATE, FAIL if problems else PASS,
                  shown or f"{n_bodies} body pairs and {len(pairs)} joint pairs mirror exactly (largest difference {worst:.1e})",
                  {"pairs": n_bodies, "joint_pairs": len(pairs), "largest_difference": worst})


# ================================================================================ joint_signs

def load_polarity(path=None):
    import yaml
    return yaml.safe_load(Path(path or POLARITY_FILE).read_text(encoding="utf-8"))


@check("check.mjcf.joint_signs", GATE)
def joint_signs(ctx, polarity=None):
    """Each hinge at +0.1 rad moves its probe point in the anatomically expected direction."""
    mj, m = _mj(), ctx.model
    spec = load_polarity(polarity)
    draft = str(spec.get("status", "DRAFT")).upper() == "DRAFT"
    tier = ADVISORY if draft else GATE
    note = " (polarity file is DRAFT: advisory until approved)" if draft else ""
    angle = float(spec.get("angle_rad", 0.1))
    rows = spec["joints"]
    axes = {"x": 0, "y": 1, "z": 2}
    problems, checked = [], 0

    hinges = {}
    for i in range(m.njnt):
        if m.jnt_type[i] == mj.mjtJoint.mjJNT_HINGE:
            hinges[mj.mj_id2name(m, mj.mjtObj.mjOBJ_JOINT, i)] = i
    for name in sorted(hinges.keys() - rows.keys()):
        problems.append(f"{name}: no row in joint_polarity.yaml")
    for name in sorted(rows.keys() - hinges.keys()):
        problems.append(f"{name}: row names a joint that is not a hinge in the model")

    for name in sorted(hinges.keys() & rows.keys()):
        row, jid = rows[name], hinges[name]
        body = int(m.jnt_bodyid[jid])
        probe = np.array(row["probe"], dtype=float)

        def probe_world(delta):
            d = mj.MjData(m)
            d.qpos[:] = m.qpos0
            d.qpos[m.jnt_qposadr[jid]] += delta
            mj.mj_kinematics(m, d)
            return d.xpos[body] + d.xmat[body].reshape(3, 3) @ probe

        move = (probe_world(angle) - probe_world(0.0))[axes[row["axis"]]]
        checked += 1
        want = int(row["sign"])
        if abs(move) < PROBE_MIN_DISPLACEMENT_M:
            problems.append(f"{name}: probe moved {move * 1000:+.2f} mm along {row['axis']}, too little to show a sign")
        elif np.sign(move) != want:
            problems.append(f"{name}: +{angle:g} rad moved the probe {move * 1000:+.1f} mm along world {row['axis']}, "
                            f"expected {'+' if want > 0 else '-'} ({row['positive']})")
    return Result("check.mjcf.joint_signs", tier, FAIL if problems else PASS,
                  ("; ".join(problems) + note) if problems else f"{checked} hinges have the expected sign{note}",
                  {"checked": checked, "failures": len(problems), "polarity_status": spec.get("status")})


# ================================================================================ floor_contact

def _lowest_z(model, data, g):
    """Lowest world z of one geom, from the support function of its shape."""
    mj = _mj()
    c, r = data.geom_xpos[g], data.geom_xmat[g].reshape(3, 3)
    s, t = model.geom_size[g], model.geom_type[g]
    up = r[2]  # world z components of the geom's local axes
    if t == mj.mjtGeom.mjGEOM_SPHERE:
        return c[2] - s[0]
    if t == mj.mjtGeom.mjGEOM_CAPSULE:
        return c[2] - abs(up[2]) * s[1] - s[0]
    if t == mj.mjtGeom.mjGEOM_CYLINDER:
        return c[2] - abs(up[2]) * s[1] - s[0] * math.sqrt(max(0.0, 1 - up[2] ** 2))
    if t == mj.mjtGeom.mjGEOM_BOX:
        return c[2] - float(np.sum(np.abs(up) * s))
    if t == mj.mjtGeom.mjGEOM_ELLIPSOID:
        return c[2] - float(np.linalg.norm(up * s))
    return c[2] - model.geom_rbound[g]  # anything else: its bounding sphere (conservative)


@check("check.mjcf.floor_contact", ADVISORY)
def floor_contact(ctx):
    """The lowest collision-geom point at neutral is on the floor plane (z = 0)."""
    mj, m = _mj(), ctx.model
    lows = {}
    for g in range(m.ngeom):
        if m.geom_type[g] == mj.mjtGeom.mjGEOM_PLANE or not (m.geom_contype[g] or m.geom_conaffinity[g]):
            continue
        body = mj.mj_id2name(m, mj.mjtObj.mjOBJ_BODY, m.geom_bodyid[g])
        lows[f"{body}[{g}]"] = float(_lowest_z(m, ctx.data, g))
    which = min(lows, key=lows.get)
    low = lows[which]
    return Result("check.mjcf.floor_contact", ADVISORY, PASS if abs(low) <= FLOOR_TOL_M else FAIL,
                  f"lowest collision point is {low * 1000:+.3f} mm from the floor plane, on {which} (limit {FLOOR_TOL_M * 1000:g} mm)",
                  {"lowest_point_m": low, "geom": which})


# ================================================================================ stature_chain

@check("check.mjcf.stature_chain", ADVISORY)
def stature_chain(ctx):
    """site_vertex height at neutral against the target stature."""
    target = ctx.snapshot.get("target_stature")
    if target is None:
        return Result("check.mjcf.stature_chain", ADVISORY, SKIP, "no target_stature in the snapshot (the 'targets' range is absent)")
    mj, m = _mj(), ctx.model
    if mj.mj_name2id(m, mj.mjtObj.mjOBJ_SITE, "site_vertex") < 0:
        return Result("check.mjcf.stature_chain", ADVISORY, FAIL, "the model has no site_vertex")
    height = float(ctx.data.site_xpos[m.site("site_vertex").id][2])
    off = height - target
    return Result("check.mjcf.stature_chain", ADVISORY, PASS if abs(off) <= STATURE_TOL_M else FAIL,
                  f"vertex at {height * 1000:.1f} mm against stature {target * 1000:.1f} mm: {off * 1000:+.1f} mm "
                  f"(limit {STATURE_TOL_M * 1000:g} mm; the sheet records a definitional -14.684 mm)",
                  {"vertex_height_m": height, "target_stature_m": target, "offset_mm": off * 1000})


# ================================================================================ com

def whole_body_com(model, data):
    """Whole-body centre of mass (MuJoCo world frame, metres): subtree CoM of the world body."""
    return np.array(data.subtree_com[0])


def com_report(ctx):
    """The numbers mass_check.py prints, from the context instead of hard-coded targets."""
    com = whole_body_com(ctx.model, ctx.data)
    mass = float(sum(ctx.model.body_mass[1:]))
    target_mass, stature = ctx.snapshot.get("target_mass"), ctx.snapshot.get("target_stature")
    return {"mass_kg": mass, "target_mass_kg": target_mass,
            "mass_error_pct": None if target_mass is None else abs(target_mass - mass) / target_mass * 100,
            "com_m": com.tolist(), "target_stature_m": stature,
            "pct_stature": None if stature is None else com[2] / stature * 100}


@check("check.mjcf.com", ADVISORY, also=["check.mjcf.com_pct_stature", "check.mjcf.com_lateral"])
def com(ctx):
    """Whole-body CoM height as a percentage of stature, and its lateral offset."""
    rep = com_report(ctx)
    x, y, z = rep["com_m"]
    if rep["pct_stature"] is None:
        pct = Result("check.mjcf.com_pct_stature", ADVISORY, SKIP, "no target_stature in the snapshot (the 'targets' range is absent)")
    else:
        p = rep["pct_stature"]
        lo, hi = COM_PCT_STATURE - COM_PCT_HALF_BAND, COM_PCT_STATURE + COM_PCT_HALF_BAND
        pct = Result("check.mjcf.com_pct_stature", ADVISORY, PASS if lo <= p <= hi else FAIL,
                     f"CoM at {p:.2f}% of stature, band {COM_PCT_STATURE:g} +/- {COM_PCT_HALF_BAND:g}% ({lo:.2f} to {hi:.2f}); "
                     f"{'inside' if lo <= p <= hi else f'{(lo - p) if p < lo else (p - hi):.2f}% outside'}",
                     {"pct_stature": p, "com_height_m": z})
    if pct.measured is None:
        pct.measured = {"com_height_m": z}
    lateral = Result("check.mjcf.com_lateral", ADVISORY, PASS if abs(y) < COM_LATERAL_TOL_M else FAIL,
                     f"lateral CoM {y * 1000:+.3f} mm (limit {COM_LATERAL_TOL_M * 1000:g} mm); anterior {x * 1000:+.2f} mm",
                     {"lateral_m": y, "anterior_m": x})
    return [pct, lateral]
