"""
Stage 2 T9.2: where the trunk group's centre of mass sits relative to the hip-centre midpoint, in Freyja and in the dataset's OpenSim model,
and an in-memory copy of Freyja's model with the group's centre of mass moved. Nothing here saves a model or touches freyja.xml.

The trunk group is datasetmass.TRUNK_GROUP (abdomen, thorax, head and neck, both arms): the dataset's single `torso` body is the same set.
Offsets are in the pelvis frame at the neutral pose with x anterior and z up (OpenSim's y), metres.
"""
from __future__ import annotations

import mujoco
import numpy as np

import datasetmass

VERSION = "1"
GROUP_MASS_FIELDS = ("body_mass", "body_inertia", "body_ipos", "body_iquat")


def _ids(model, names):
    return [mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_BODY, n) for n in names]


def _neutral(model):
    d = mujoco.MjData(model)
    mujoco.mj_forward(model, d)
    return d


def hip_midpoint(model, d) -> np.ndarray:
    ids = _ids(model, ("thigh_right", "thigh_left"))
    return 0.5 * (d.xpos[ids[0]] + d.xpos[ids[1]])


def group_com(model, d, names=datasetmass.TRUNK_GROUP) -> np.ndarray:
    ids = _ids(model, names)
    m = model.body_mass[ids]
    return (m[:, None] * d.xipos[ids]).sum(axis=0) / m.sum()


def trunk_offset(model) -> np.ndarray:
    """(x anterior, y left, z up): the trunk group's centre of mass minus the hip-centre midpoint at the neutral pose."""
    d = _neutral(model)
    return group_com(model, d) - hip_midpoint(model, d)


def read_torso_offset(zf, subject) -> dict:
    """The dataset's torso centre of mass minus the midpoint of its hip centres, in its pelvis frame (x forward, y up), metres, from
    osimxml/<subject>.osim: the `back` joint's location in the pelvis, minus its location in the torso frame, plus the torso's mass centre
    (all frames unrotated at the reference pose), and the torso's mass fraction of the model."""
    import xml.etree.ElementTree as ET
    name = next(n for n in zf.namelist() if n.lower() == f"osimxml/{subject.lower()}.osim")
    root = ET.fromstring(zf.read(name))
    vec = lambda s: np.array([float(v) for v in s.split()])
    back = next(j for j in root.iter("CustomJoint") if j.get("name") == "back")
    frames = {f.findtext("socket_parent"): f for f in back.iter("PhysicalOffsetFrame")}
    in_pelvis, in_torso = vec(frames["/bodyset/pelvis"].findtext("translation")), vec(frames["/bodyset/torso"].findtext("translation"))
    for key in ("/bodyset/pelvis", "/bodyset/torso"):
        if np.abs(vec(frames[key].findtext("orientation"))).max() > 1e-9:
            raise ValueError(f"{subject}: the back joint's {key} frame is rotated; the unrotated reference-pose arithmetic does not apply")
    bodies = {b.get("name"): b for b in root.iter("Body")}
    com_torso = vec(bodies["torso"].findtext("mass_center"))
    hips = []
    for joint in root.iter("CustomJoint"):
        if joint.get("name") in ("hip_r", "hip_l"):
            for f in joint.iter("PhysicalOffsetFrame"):
                if f.findtext("socket_parent") == "/bodyset/pelvis":
                    hips.append(vec(f.findtext("translation")))
    hip_mid = np.mean(hips, axis=0)
    com_pelvis = in_pelvis - in_torso + com_torso
    total = sum(float(b.findtext("mass")) for b in bodies.values())
    return {"offset_xy": com_pelvis[:2] - hip_mid[:2], "mass_fraction": float(bodies["torso"].findtext("mass")) / total}


def with_trunk_com_shift(model, delta):
    """A copy of `model` (its masses, inertias and centres of mass included: the xml is reloaded and those arrays copied over) in which every
    body of the trunk group has its centre of mass moved by `delta` (x anterior, y left, z up, world axes at the neutral pose). The group's
    centre of mass moves by exactly delta; masses and inertias are unchanged. The input model is not touched and nothing is saved."""
    copy = mujoco.MjModel.from_xml_path(str(datasetmass._xml_path(model)))
    for f in GROUP_MASS_FIELDS:
        getattr(copy, f)[:] = getattr(model, f)
    d = _neutral(copy)
    for b in _ids(copy, datasetmass.TRUNK_GROUP):
        r = d.xmat[b].reshape(3, 3)  # body frame to world at the neutral pose
        copy.body_ipos[b] = copy.body_ipos[b] + r.T @ np.asarray(delta, float)
    mujoco.mj_setConst(copy, mujoco.MjData(copy))
    return copy


def shift_to(model, target_offset_xz) -> tuple:
    """(copy, delta): `model` with the trunk group's centre of mass moved to `target_offset_xz` (x anterior, z up) from the hip midpoint."""
    now = trunk_offset(model)
    delta = np.array([target_offset_xz[0] - now[0], 0.0, target_offset_xz[1] - now[2]])
    return with_trunk_com_shift(model, delta), delta
