"""
The proposed structural records: one segment record per pre_processor segment and one joint record per anatomical joint, with every model
hinge bound to exactly one joint. This is the T0 proposal of the Stage 3a brief, awaiting Joe's answers at Checkpoint A. Until T7 writes
the real records from it, the fixture generator uses it so that its structural records cover every body and hinge of the real model.

Purposes say what the segment or joint is anatomically and nothing about design. Bilateral segments and joints are one record with
`sides: [left, right]`; the side suffix of the model names (`thigh_right`, `hip_fe_right`) is derived from the one binding.
"""
from __future__ import annotations

# segment name (pre_processor's) -> (model body without side suffix, purpose)
SEGMENTS = {
    "head_neck": ("head_and_neck", "The head and the cervical spine above the thorax."),
    "thorax": ("thorax", "The rib cage and thoracic spine."),
    "abdomen": ("abdomen", "The lumbar spine and abdominal wall between the pelvis and the thorax."),
    "pelvis": ("pelvis", "The pelvic girdle, which carries the hip joints."),
    "upper_arm": ("upper_arm", "The upper arm, from the shoulder to the elbow."),
    "forearm": ("forearm", "The forearm, from the elbow to the wrist."),
    "hand": ("hand", "The hand, distal to the wrist."),
    "thigh": ("thigh", "The thigh, from the hip to the knee."),
    "shank": ("shank", "The lower leg, from the knee to the ankle."),
    "foot": ("foot", "The foot, distal to the ankle."),
}

# joint name -> (model hinges without side suffix, ROM keys of the snapshot, purpose)
JOINTS = {
    "hip": (["hip_fe", "hip_aa", "hip_ier"],
            ["hip_flexion", "hip_extension", "hip_abduction", "hip_adduction", "hip_external_rotation", "hip_internal_rotation"],
            "The hip, a ball-and-socket joint between the pelvis and the thigh, modelled as three hinges."),
    "knee": (["knee"], ["knee_flexion", "knee_extension"], "The knee, a hinge between the thigh and the shank."),
    "ankle": (["ankle_pdflex", "ankle_ie"], ["ankle_dorsiflexion", "ankle_plantarflexion", "ankle_inversion", "ankle_eversion"],
              "The ankle, between the shank and the foot, modelled as plantar-dorsiflexion and inversion-eversion hinges."),
    "lumbosacral": (["lsj_fe", "lsj_lat", "lsj_ax"],
                    ["lumbosacral_flexion", "lumbosacral_extension", "lumbosacral_lateral_bending", "lumbosacral_axial_rotation"],
                    "The lumbosacral joint between the pelvis and the lumbar spine, modelled as three hinges."),
    "thoracic": (["tj_fe", "tj_lat", "tj_ax"], [], "The joint between the abdomen and the thorax, modelled as three hinges (the model calls it the thoracic joint)."),
    "cervical": (["cj_fe", "cj_lat", "cj_ax"], [], "The cervical joint between the thorax and the head and neck, modelled as three hinges."),
    "shoulder": (["shoulder_fe", "shoulder_aa", "shoulder_ier"],
                 ["shoulder_flexion", "shoulder_extension", "shoulder_abduction", "shoulder_adduction", "shoulder_external_rotation",
                  "shoulder_internal_rotation"],
                 "The shoulder, between the thorax and the upper arm, modelled as three hinges."),
    "elbow": (["elbow"], ["elbow_flexion", "elbow_extension"], "The elbow, a hinge between the upper arm and the forearm."),
    "wrist": (["wrist"], ["wrist_flexion", "wrist_extension"], "The wrist, between the forearm and the hand, modelled as one hinge."),
}


def segment_record(name: str, bilateral: bool, status: str = "active") -> dict:
    body, purpose = SEGMENTS[name]
    rec = {"schema": "thread-record/1", "id": f"seg.{name}", "kind": "segment", "status": status, "purpose": purpose, "body": body}
    if bilateral:
        rec["sides"] = ["left", "right"]
    return rec


def joint_record(name: str, bilateral: bool, status: str = "active") -> dict:
    hinges, rom, purpose = JOINTS[name]
    rec = {"schema": "thread-record/1", "id": f"jnt.{name}", "kind": "joint", "status": status, "purpose": purpose, "hinges": list(hinges), "rom_keys": list(rom)}
    if bilateral:
        rec["sides"] = ["left", "right"]
    return rec


def joint_is_bilateral(name: str, model_hinges) -> bool:
    """A joint is bilateral when the model has its first hinge once per side. The library then checks this against pre_processor.BILATERAL
    through the child segment, so a wrong answer here is an error there, not a silent one."""
    return f"{JOINTS[name][0][0]}_right" in model_hinges
