"""
Stage 2 T3c.5: in-memory copies of Freyja's model with the dataset model's segment masses and centres of mass substituted, to see how
much of B's CoP error is mass distribution. Nothing here saves a model or touches freyja.xml.

Mapping (the dataset's OpenSim gait2392 segments to Freyja's):
  pelvis            <- pelvis                        mass fraction, and the centre of mass above the hip-centre midpoint
  thigh_right/left  <- femur_r/l                     mass fraction, centre of mass down the bone (scaled by the leg-length ratio)
  shank_right/left  <- tibia_r/l                     mass fraction, centre of mass down the bone
  foot_right/left   <- talus + calcn + toes          mass fraction only (the centre of mass needs the subtalar and mtp joint frames)
  abdomen, thorax, head_and_neck, upper_arm, forearm, hand (both sides) <- torso   the dataset's torso carries the trunk, head and arms,
                                                   so the group total takes its mass fraction and Freyja's split inside the group is kept
Masses become fraction x Freyja's total mass, so the total is unchanged; inertias scale with mass for the same geometry.
"""
from __future__ import annotations

import mujoco
import numpy as np

VERSION = "1"
LEG = {"thigh": "femur", "shank": "tibia"}
TRUNK_GROUP = ["abdomen", "thorax", "head_and_neck", "upper_arm_right", "forearm_right", "hand_right", "upper_arm_left", "forearm_left", "hand_left"]


def read_body_table(zf, subject) -> dict:
    """{body: (mass kg, (x, y, z) centre of mass in the body frame)} from the subject's osim file."""
    import xml.etree.ElementTree as ET
    name = next(n for n in zf.namelist() if n.lower() == f"osimxml/{subject.lower()}.osim")
    root = ET.fromstring(zf.read(name))
    return {b.get("name"): (float(b.findtext("mass")), tuple(float(v) for v in b.findtext("mass_center").split())) for b in root.iter("Body")}


def with_dataset_masses(model, table, length_ratio, hip_in_pelvis):
    """A new MjModel (loaded from the model's own xml) with masses, inertias and centres of mass substituted. `table` is what
    read_body_table returns; `hip_in_pelvis` the hip centre (x forward, y up) in the dataset pelvis frame."""
    copy = mujoco.MjModel.from_xml_path(str(_xml_path(model)))
    total_f = float(copy.body_mass.sum())
    total_d = sum(m for m, _ in table.values())
    frac = lambda names: sum(table[n][0] for n in names) / total_d
    bid = lambda n: mujoco.mj_name2id(copy, mujoco.mjtObj.mjOBJ_BODY, n)

    def set_mass(name, new_mass):
        b = bid(name)
        scale = new_mass / copy.body_mass[b]
        copy.body_mass[b] = new_mass
        copy.body_inertia[b] *= scale

    set_mass("pelvis", total_f * frac(["pelvis"]))
    hip_mid = _hip_mid_offset(copy)
    # the dataset's pelvis centre of mass: level with the hip centres' x, `rise` above them
    rise = (0.0 - hip_in_pelvis[1]) * length_ratio
    copy.body_ipos[bid("pelvis")] = hip_mid + np.array([0.0, 0.0, rise])
    for side, suf in (("right", "r"), ("left", "l")):
        for seg, bone in LEG.items():
            set_mass(f"{seg}_{side}", total_f * frac([f"{bone}_{suf}"]))
            x, y, z = table[f"{bone}_{suf}"][1]
            copy.body_ipos[bid(f"{seg}_{side}")] = length_ratio * np.array([x, -z, y])  # OpenSim (fwd, up, right) -> model (fwd, left, up)
        foot_total = total_f * frac([f"talus_{suf}", f"calcn_{suf}", f"toes_{suf}"])  # the dataset's foot includes its toes: the model's foot body and toe body share it
        parts = [n for n in (f"foot_{side}", f"toe_{side}") if bid(n) >= 0]
        share = foot_total / sum(float(copy.body_mass[bid(n)]) for n in parts)  # both scale by one factor, so the split between them stays the sheet's
        for n in parts:
            set_mass(n, float(copy.body_mass[bid(n)]) * share)
    current = sum(float(copy.body_mass[bid(n)]) for n in TRUNK_GROUP)
    for n in TRUNK_GROUP:
        set_mass(n, copy.body_mass[bid(n)] * total_f * frac(["torso"]) / current)
    mujoco.mj_setConst(copy, mujoco.MjData(copy))
    return copy


def _hip_mid_offset(model):
    d = mujoco.MjData(model)
    mujoco.mj_forward(model, d)
    ids = [mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_BODY, n) for n in ("thigh_right", "thigh_left")]
    root = int(model.jnt_bodyid[0])
    return 0.5 * (d.xpos[ids[0]] + d.xpos[ids[1]]) - d.xpos[root]


def _xml_path(model):
    from pathlib import Path
    return Path(__file__).resolve().parents[1] / "models" / "freyja.xml"
