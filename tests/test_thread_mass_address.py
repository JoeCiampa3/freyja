"""
Stage 3b T5: the second form of a part's mass, `{address, source}`. The claim reads the address at build (a CAD sidecar's mass_kg), so the budget never holds
a typed copy; an address that does not resolve is the `address-unresolved` warning, not an error.

    python -m pytest tests/test_thread_mass_address.py
"""
import json

from thread_help import codes, make_root, write_record

from thread import build

ADDRESS = "cad/sidecars/part.base.cad.json#/mass_properties/mass_kg"


def root_with_cad_part(tmp_path, sidecar_kg=None, **extra):
    root = make_root(tmp_path / "r")
    write_record(root, id="part.base.cad", kind="part", housed_in="seg.thigh", category="structure", sides=["left", "right"],
                 mass={"address": ADDRESS, "source": "CAD sidecar"}, **extra)
    if sidecar_kg is not None:
        p = root / "cad" / "sidecars" / "part.base.cad.json"
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps({"schema": "cad-sidecar/1", "generated_by": "x", "inputs": "y", "mass_properties": {"mass_kg": sidecar_kg}}), encoding="utf-8")
    return root


def claim(b, seg="seg.thigh", part="part.base.cad"):
    return next(c for c in b.budgets["segments"][seg]["claims"] if c["part"] == part)


def test_an_address_that_does_not_resolve_is_a_warning_and_claims_nothing(tmp_path):
    b = build.build_root(root_with_cad_part(tmp_path))
    assert b.errors == []
    assert [(i.code, tuple(i.ids)) for i in b.warnings] == [("address-unresolved", ("part.base.cad",))]
    c = claim(b)
    assert c["kg"] == 0.0 and c["total_kg"] == 0.0 and ADDRESS in c["arithmetic"] and "unresolved" in c["arithmetic"]


def test_the_claim_is_the_value_at_the_address_with_its_arithmetic(tmp_path):
    b = build.build_root(root_with_cad_part(tmp_path, sidecar_kg=0.25))
    assert b.errors == [] and "address-unresolved" not in codes(b.warnings)
    c = claim(b)
    assert c["kg"] == 0.25 and c["total_kg"] == 0.25
    assert c["arithmetic"].startswith("1 x 0.25 kg, part.base.cad right") and ADDRESS in c["arithmetic"]


def test_the_budget_follows_the_sidecar_and_never_a_typed_copy(tmp_path):
    root = root_with_cad_part(tmp_path, sidecar_kg=0.25)
    before = build.build_root(root).budgets["segments"]["seg.thigh"]["claimed_kg"]
    (root / "cad" / "sidecars" / "part.base.cad.json").write_text(
        json.dumps({"schema": "cad-sidecar/1", "generated_by": "x", "inputs": "y", "mass_properties": {"mass_kg": 0.75}}), encoding="utf-8")
    after = build.build_root(root).budgets["segments"]["seg.thigh"]["claimed_kg"]
    assert round(after - before, 6) == 0.5


def test_a_non_numeric_value_at_the_address_is_unresolved_for_the_budget(tmp_path):
    root = root_with_cad_part(tmp_path, sidecar_kg="heavy")
    b = build.build_root(root)
    assert claim(b)["total_kg"] == 0.0 and "address-unresolved" in codes(b.warnings)


def test_the_typed_form_is_unchanged(tmp_path):
    b = build.build_root(make_root(tmp_path / "r"))
    assert all("address" not in c for c in b.budgets["segments"]["seg.thigh"]["claims"])


def test_impact_of_the_sidecar_mass_reaches_the_segment_dossier_sources(tmp_path):
    b = build.build_root(root_with_cad_part(tmp_path, sidecar_kg=0.25))
    assert any(ADDRESS in srcs for srcs in b.sources.values())
