"""
Stage 3b T5: the placeholder's binding and thread records agree with each other and with the snapshot. Nothing here needs Fusion.

    python -m pytest tests/test_cad_records.py
"""
import sys
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "tools"))

from cad import binding as cb  # noqa: E402
from thread import addr  # noqa: E402

PART = "part.arm.upper_member"


def record(id):
    return yaml.safe_load((REPO / "thread" / "records" / f"{id}.yaml").read_text(encoding="utf-8"))


def test_every_binding_loads_and_is_named_by_its_part():
    files = sorted((REPO / "cad" / "bindings").glob("*.yaml"))
    assert files
    for f in files:
        doc = cb.load(f)
        assert doc["document"]["id"].startswith("urn:"), f.name      # a local path must never enter a tracked file


def test_the_placeholder_records_are_proposed_and_say_what_the_part_is():
    part, work = record(PART), record("work.upper-arm-cad")
    assert part["status"] == "proposed" and work["status"] == "proposed"
    assert "bridge test article" in part["purpose"] and "not a design" in part["purpose"]
    assert part["housed_in"] == "seg.upper_arm" and part["sides"] == ["left", "right"] and part["category"] == "structure"
    assert set(part["mass"]) == {"address", "source"} and part["mass"]["address"] == f"cad/sidecars/{PART}.json#/mass_properties/mass_kg"


def test_the_work_item_consumes_what_the_binding_inherits():
    b = cb.load(REPO / "cad" / "bindings" / f"{PART}.yaml")
    work = record("work.upper-arm-cad")
    assert work["of"] == PART and work["mode"] == "assisted" and work["output"] == f"cad/sidecars/{PART}.json"
    assert sorted(work["consumes"]) == sorted(p["address"] for p in cb.inherited(b))


def test_the_inherited_parameter_is_named_by_the_rule_and_resolves_in_the_snapshot():
    b = cb.load(REPO / "cad" / "bindings" / f"{PART}.yaml")
    (p,) = cb.inherited(b)
    assert p["name"] == "in_upper_arm_right_length" and p["address_unit"] == "m" and p["unit"] == "mm"
    rows = {}
    for line in (REPO / "params" / "snapshot.csv").read_text(encoding="utf-8").splitlines()[1:]:
        k, v, _ = line.split(",", 2)
        rows[k] = float(v)
    assert "upper_arm_right_length" in rows
    assert cb.resolve_inherited(b, lambda a: addr.pointer_get(rows, addr.parse(a)[1]))[0]["value"] == rows["upper_arm_right_length"] * 1000
