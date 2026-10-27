"""Drift: an inherited parameter whose value in Fusion differs from its address's current value (Stage 3b, gate G4)."""
from __future__ import annotations

import math

REL_TOL = 1e-9      # relative: the round-trip tolerance of gate G2; a pushed value that reads back within it is not drift
ABS_TOL = 1e-12     # mm, deg or unitless: only matters when the address value is zero


class DriftError(ValueError):
    """An inherited parameter is not in the document at all (a validate problem, never a clean result)."""


def compare(expected: list, actual: dict) -> list:
    """`expected`: rows from binding.resolve_inherited; `actual`: {name: value in the binding unit} read from Fusion. Returns the rows that differ."""
    out = []
    for row in expected:
        if row["name"] not in actual:
            raise DriftError(f"{row['name']} is not in the document")
        got = actual[row["name"]]
        if not math.isclose(got, row["value"], rel_tol=REL_TOL, abs_tol=ABS_TOL):
            out.append({"name": row["name"], "address": row["address"], "fusion_value": got, "address_value": row["value"]})
    return out
