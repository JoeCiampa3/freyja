"""The envelope component entry of a CAD part (Stage 3b; docs/envelope-component-contract.md): a box around the mesh in the owner's model body frame."""
from __future__ import annotations

from thread import addr

from . import mesh


def parameter_inputs(consumes: list) -> str:
    """The 12 hex hash of what the CAD state consumed: addresses and their hashes, sorted by address."""
    return addr.hash_value(sorted(({"address": c["address"], "hash": c["hash"]} for c in consumes), key=lambda c: c["address"]))


def component_entry(binding: dict, *, segment: str, vertices_model, mesh_hash: str, mass_kg: float, consumes: list, mesh_path: str) -> dict:
    """The registry entry. `segment` is the oracle's name of the owner (`upper_arm_R`); the box encloses the mesh, already in the model frame."""
    lo, hi = mesh.bounds(vertices_model)
    half = [float(x) for x in (hi - lo) / 2]
    offset = [float(x) for x in (hi + lo) / 2]
    return {"id": binding["part"], "revision": binding["revision"], "name": binding["part"], "status": "designed", "owner": segment,
            "primitive": {"type": "box", "half": half, "offset": offset}, "mesh": mesh_path, "clearance_mm": float(binding.get("clearance_mm", 0.0)),
            "mass_kg": float(mass_kg), "sha256": mesh_hash, "parameter_inputs": parameter_inputs(consumes)}
