"""
The one place the Fusion unit factors appear (CONVENTIONS section 3, CAD terms). Fusion stores lengths in cm, angles in rad and inertia in kg cm^2
whatever the document's units; the repo works in mm, degrees and kg mm^2. Nothing else in the repo carries these factors.

Units of a parameter (`mm`, `deg`, `unitless`) are the Fusion-side units of its expression. `convert` takes a value from the unit of its address (the
snapshot holds metres and radians) to that unit.
"""
from __future__ import annotations

import math
from decimal import Decimal

MM_PER_CM = 10.0                # Fusion length (cm) to mm
CM_PER_MM = 0.1
KGMM2_PER_KGCM2 = 100.0         # (10 mm / cm)^2: Fusion inertia (kg cm^2) to kg mm^2
KG_M3_PER_KG_CM3 = 1.0e6        # (100 cm / m)^3: Fusion density (kg/cm^3) to kg/m^3
DEG_PER_RAD = 180.0 / math.pi
RAD_PER_DEG = math.pi / 180.0

UNITS = ("mm", "deg", "unitless")
_TO_MM = {"m": 1000.0, "mm": 1.0}
_TO_DEG = {"rad": DEG_PER_RAD, "deg": 1.0}
SIG_DIGITS = 12                 # expression digits: a relative error of 5e-13, inside the 1e-9 gate of the round trip


def mm_to_fusion_length(mm: float) -> float:
    return mm * CM_PER_MM


def fusion_length_to_mm(cm: float) -> float:
    return cm * MM_PER_CM


def deg_to_fusion_angle(deg: float) -> float:
    return deg * RAD_PER_DEG


def fusion_angle_to_deg(rad: float) -> float:
    return rad * DEG_PER_RAD


def fusion_inertia_to_kgmm2(kgcm2: float) -> float:
    return kgcm2 * KGMM2_PER_KGCM2


def kgmm2_to_fusion_inertia(kgmm2: float) -> float:
    return kgmm2 / KGMM2_PER_KGCM2


def fusion_density_to_kg_m3(kg_cm3: float) -> float:
    return kg_cm3 * KG_M3_PER_KG_CM3


def fusion_value_to_unit(value: float, unit: str) -> float:
    """A parameter's evaluated value as Fusion holds it (cm, rad or unitless) in `unit`."""
    if unit == "mm":
        return fusion_length_to_mm(value)
    if unit == "deg":
        return fusion_angle_to_deg(value)
    if unit == "unitless":
        return float(value)
    raise ValueError(f"unknown unit {unit!r} (expected one of {UNITS})")


def unit_to_fusion_value(value: float, unit: str) -> float:
    """The inverse of `fusion_value_to_unit`."""
    if unit == "mm":
        return mm_to_fusion_length(value)
    if unit == "deg":
        return deg_to_fusion_angle(value)
    if unit == "unitless":
        return float(value)
    raise ValueError(f"unknown unit {unit!r} (expected one of {UNITS})")


def convert(value: float, from_unit: str, to_unit: str) -> float:
    """A value at an address (unit `from_unit`: m, mm, rad, deg or unitless) in a parameter unit (`to_unit`: mm, deg or unitless)."""
    if to_unit == "mm" and from_unit in _TO_MM:
        return value * _TO_MM[from_unit]
    if to_unit == "deg" and from_unit in _TO_DEG:
        return value * _TO_DEG[from_unit]
    if to_unit == "unitless" and from_unit == "unitless":
        return float(value)
    raise ValueError(f"cannot convert {from_unit!r} to {to_unit!r}")


def format_expression(value: float, unit: str) -> str:
    """The expression the bridge writes: a number with an explicit unit (`312.4 mm`, `62 deg`), a bare number for unitless. Plain decimal, never an
    exponent, so Fusion's expression parser reads it the same way everywhere."""
    if unit not in UNITS:
        raise ValueError(f"unknown unit {unit!r} (expected one of {UNITS})")
    if not math.isfinite(value):
        raise ValueError(f"cannot write {value!r} as an expression")
    text = format(value, f".{SIG_DIGITS}g")
    if "e" in text or "E" in text:
        text = format(Decimal(text), "f")
    if text in ("-0", ""):
        text = "0"
    return text if unit == "unitless" else f"{text} {unit}"
