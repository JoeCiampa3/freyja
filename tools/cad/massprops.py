"""Fusion's physical properties as the sidecar's mass properties (Stage 3b): Fusion's units (cm, kg cm^2, kg/cm^3) to the repo's, the inertia moved from the world
origin to the centre of mass, and everything rotated into the owner's model body frame."""
from __future__ import annotations

import numpy as np

from . import frames, units


def mass_properties(raw: dict, side: str = "right") -> dict:
    """`raw` is the Fusion-side `physical_properties` result. Returns the `mass_properties` object of the sidecar."""
    mass = float(raw["mass_kg"])
    com_isb = [units.fusion_length_to_mm(c) for c in raw["com_cm"]]
    origin = {k: units.fusion_inertia_to_kgmm2(v) for k, v in raw["inertia_origin_kgcm2"].items()}
    about_com = frames.from_matrix(frames.shift_inertia_to_com(frames.to_matrix(origin), mass, com_isb))
    com_model, inertia_model = frames.mass_to_model(com_isb, about_com, side)
    materials = raw["materials"]
    if len(materials) != 1:
        raise ValueError(f"the mass properties span {len(materials)} materials ({materials}); one material per part is expected")
    return {"material": {"name": materials[0], "density_kg_m3": units.fusion_density_to_kg_m3(raw["density_kg_cm3"])},
            "mass_kg": mass, "com_mm": [float(x) for x in np.asarray(com_model)], "inertia_kgmm2": inertia_model, "accuracy": raw["accuracy"]}
