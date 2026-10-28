"""
Stage 3b T3, without Fusion: Fusion's physical properties (recorded from the scratch fixture) become the sidecar's mass properties and meet the closed forms of
gate G2: mass within 0.1%, centre of mass within 0.01 mm, principal moments within 0.5%, after conversion from cm, rad and kg cm^2 to mm, degrees and kg mm^2.
The sector's recorded products pin the sign convention of Fusion's inertia (matrix entries, not integrals).

    python -m pytest tests/test_cad_massprops.py
"""
import json
import math
import sys
from pathlib import Path

import numpy as np
import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "tools"))

from cad import frames, massprops, units  # noqa: E402

FIX = Path(__file__).resolve().parent / "fixtures" / "cad"
TUBE = json.loads((FIX / "physical_tube.json").read_text(encoding="utf-8"))
SECTOR = json.loads((FIX / "physical_sector.json").read_text(encoding="utf-8"))

RHO = 2.7e-6           # kg/mm^3: 6061 aluminium, 2700 kg/m^3 (the library material Fusion reports)
OD, WALL, L = 30.0, 2.0, 300.0
MASS_REL, COM_MM, PRINCIPAL_REL = 1e-3, 0.01, 5e-3      # gate G2


def closed_form():
    ro, ri = OD / 2, OD / 2 - WALL
    m = RHO * math.pi * (ro**2 - ri**2) * L
    iz = m * (ro**2 + ri**2) / 2
    it = m * (3 * (ro**2 + ri**2) + L**2) / 12
    return m, it, iz


def test_the_tube_meets_the_closed_form_gate():
    m, it, iz = closed_form()
    mp = massprops.mass_properties(TUBE)
    assert mp["mass_kg"] == pytest.approx(m, rel=MASS_REL)
    assert np.allclose(mp["com_mm"], (0.0, 0.0, -L / 2), atol=COM_MM)
    got = np.sort(frames.principal_moments(frames.to_matrix(mp["inertia_kgmm2"])))
    assert got == pytest.approx(np.sort([it, it, iz]), rel=PRINCIPAL_REL)
    assert mp["material"] == {"name": "Aluminum 6061", "density_kg_m3": pytest.approx(2700.0, rel=1e-9)}
    assert mp["accuracy"] == "veryhigh"


def test_the_tensor_is_in_the_model_frame_with_the_axis_along_up():
    m, it, iz = closed_form()
    I = frames.to_matrix(massprops.mass_properties(TUBE)["inertia_kgmm2"])
    assert I[2, 2] == pytest.approx(iz, rel=PRINCIPAL_REL)           # the tube's axis is the model's z
    assert I[0, 0] == pytest.approx(it, rel=PRINCIPAL_REL) and I[1, 1] == pytest.approx(it, rel=PRINCIPAL_REL)
    assert np.allclose(I - np.diag(np.diag(I)), 0, atol=1e-6 * it)


def test_fusion_reports_inertia_about_the_origin_and_the_conversion_moves_it_to_the_com():
    # Fusion's ixx about the world origin is the transverse inertia plus m * (L / 2)^2, in kg cm^2
    m, it, iz = closed_form()
    ixx_origin_kgmm2 = it + m * (L / 2) ** 2
    assert units.fusion_inertia_to_kgmm2(TUBE["inertia_origin_kgcm2"]["ixx"]) == pytest.approx(ixx_origin_kgmm2, rel=PRINCIPAL_REL)


def test_a_wrong_unit_factor_would_fail_the_gate(monkeypatch):
    m, it, iz = closed_form()
    monkeypatch.setattr(units, "KGMM2_PER_KGCM2", 10.0)
    mp = massprops.mass_properties(TUBE)
    got = np.sort(frames.principal_moments(frames.to_matrix(mp["inertia_kgmm2"])))
    assert not np.allclose(got, np.sort([it, it, iz]), rtol=PRINCIPAL_REL)
    monkeypatch.undo()
    monkeypatch.setattr(units, "MM_PER_CM", 1.0)
    assert not np.allclose(massprops.mass_properties(TUBE)["com_mm"], (0.0, 0.0, -L / 2), atol=COM_MM)


def test_the_sector_pins_fusions_sign_for_the_products_of_inertia():
    # r in [40, 46] mm, y in [-5, 5] mm, revolved 30 degrees from +x towards +z: both coordinates of its centre of mass are positive, so the integral of x z dm
    # is positive; Fusion's xz is negative, so Fusion returns the matrix entry (minus the integral).
    r1, r2, h, alpha = 40.0, 46.0, 5.0, math.radians(30)
    integral_xz = RHO * (2 * h) * (r2**4 - r1**4) / 4 * math.sin(alpha) ** 2 / 2          # kg mm^2
    com = SECTOR["com_cm"]
    assert com[0] > 0 and com[2] > 0
    xz = units.fusion_inertia_to_kgmm2(SECTOR["inertia_origin_kgcm2"]["ixz"])
    assert xz == pytest.approx(-integral_xz, rel=1e-6)


def test_more_than_one_material_is_refused():
    raw = dict(TUBE, materials=["Aluminum 6061", "Steel"])
    with pytest.raises(ValueError, match="2 materials"):
        massprops.mass_properties(raw)
