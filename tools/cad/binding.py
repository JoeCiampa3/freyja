"""Bindings (`cad-binding/1`): load, validate, hash, and resolve the inherited parameters through the thread's addresses (Stage 3b)."""
from __future__ import annotations

import json
from pathlib import Path

import jsonschema
import yaml

from thread import addr

from . import names, units

REPO = Path(__file__).resolve().parents[2]
SCHEMA_PATH = REPO / "docs" / "schemas" / "cad-binding-1.schema.json"
PREFIXES = {"in": "in_", "dv": "dv_", "dr": "dr_"}


class BindingError(ValueError):
    """The binding breaks a rule; the message lists every problem found."""


def _schema() -> dict:
    return json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))


def check_names(doc: dict) -> list:
    """The rules the schema cannot say: class prefix, one name per parameter, the name rule for inherited ones, no two addresses on one name."""
    problems, seen = [], {}
    for p in doc.get("parameters", []):
        name, cls = p.get("name", ""), p.get("class")
        if cls in PREFIXES and not name.startswith(PREFIXES[cls]):
            problems.append(f"{name!r}: class {cls} needs the prefix {PREFIXES[cls]!r}")
        if name in seen:
            problems.append(f"{name!r}: appears twice")
        seen[name] = p
        if cls == "in" and p.get("address"):
            try:
                want = names.inherited_name(p["address"])
            except ValueError as e:
                problems.append(str(e))
                continue
            if name != want:
                problems.append(f"{name!r}: the name rule gives {want!r} for {p['address']!r}")
    return problems


def check(doc: dict) -> list:
    """Every problem with a binding document: schema errors first, then the name rules."""
    problems = [f"{'/'.join(str(x) for x in e.absolute_path) or '<root>'}: {e.message}" for e in jsonschema.Draft202012Validator(_schema()).iter_errors(doc)]
    return problems + check_names(doc)


def load(path) -> dict:
    path = Path(path)
    doc = yaml.safe_load(path.read_text(encoding="utf-8"))
    problems = check(doc) if isinstance(doc, dict) else ["not a mapping"]
    if isinstance(doc, dict) and doc.get("part") and path.stem != doc["part"]:
        problems.append(f"filename stem {path.stem!r} must equal the part id {doc['part']!r}")
    if problems:
        raise BindingError(f"{path.name}: " + "; ".join(problems))
    return doc


def binding_hash(doc: dict) -> str:
    return addr.hash_value(doc)


def inherited(doc: dict) -> list:
    return [p for p in doc["parameters"] if p["class"] == "in"]


def resolve_inherited(doc: dict, resolve) -> list:
    """One row per inherited parameter, sorted by name: its address, the address's hash, the value in the Fusion unit and the expression to write.
    `resolve(address)` is `(True, value)` or `(False, None)`, e.g. the thread build's resolver."""
    rows = []
    for p in sorted(inherited(doc), key=lambda p: p["name"]):
        ok, value = resolve(p["address"])
        if not ok:
            raise BindingError(f"{p['name']}: the address {p['address']} does not resolve")
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise BindingError(f"{p['name']}: the address {p['address']} holds {value!r}, not a number")
        v = units.convert(float(value), p["address_unit"], p["unit"])
        rows.append({"name": p["name"], "address": p["address"], "address_hash": addr.hash_value(value), "address_value": float(value),
                     "unit": p["unit"], "value": v, "expression": units.format_expression(v, p["unit"])})
    return rows


def consumes(doc: dict, resolve) -> list:
    """The addresses the CAD state consumed with their hashes, sorted by address (what the work item's stamp records)."""
    return sorted(({"address": r["address"], "hash": r["address_hash"]} for r in resolve_inherited(doc, resolve)), key=lambda c: c["address"])


def thread_resolver(root):
    """The thread build's address resolver for a repo root (imported, not copied)."""
    from thread import build as thread_build
    return thread_build.build_root(root).resolve
