"""The user parameters of a bound document against its binding (Stage 3b): the checks of `fy cad validate` and the sidecar's parameter rows."""
from __future__ import annotations

from . import units

PREFIXES = ("in_", "dv_", "dr_")


def check_document(binding: dict, raw: list) -> list:
    """Problems between the document's user parameters (`raw`: dicts with name, expression and the evaluated value) and the binding: an unprefixed parameter,
    a parameter not in the binding, one missing from the document, one listed twice."""
    problems, seen = [], set()
    declared = {p["name"]: p for p in binding["parameters"]}
    for r in raw:
        name = r["name"]
        if name in seen:
            problems.append(f"{name}: appears twice in the document")
        seen.add(name)
        if not name.startswith(PREFIXES):
            problems.append(f"{name}: user parameter without a class prefix ({', '.join(PREFIXES)})")
        elif name not in declared:
            problems.append(f"{name}: in the document but not in the binding")
    for name in declared:
        if name not in seen:
            problems.append(f"{name}: in the binding but missing from the document")
    return problems


def sidecar_parameters(binding: dict, raw: list, resolved: list) -> list:
    """The sidecar's parameter rows, sorted by name: Fusion's internal value in the binding's unit, and for inherited ones the address and its hash."""
    declared = {p["name"]: p for p in binding["parameters"]}
    by_addr = {r["name"]: r for r in resolved}
    rows = []
    for r in sorted(raw, key=lambda r: r["name"]):
        p = declared[r["name"]]
        row = {"name": r["name"], "class": p["class"], "expression": r["expression"],
               "value": units.fusion_value_to_unit(r["value"], p["unit"]), "unit": p["unit"]}
        if p["class"] == "in":
            row["address"] = p["address"]
            row["address_hash"] = by_addr[r["name"]]["address_hash"]
        rows.append(row)
    return rows
