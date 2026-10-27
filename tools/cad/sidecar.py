"""The sidecar (`cad-sidecar/1`): assembled from pulled pieces, validated against the schema, written deterministically (Stage 3b)."""
from __future__ import annotations

import json
from pathlib import Path

import jsonschema

from thread import addr

REPO = Path(__file__).resolve().parents[2]
SCHEMA_PATH = REPO / "docs" / "schemas" / "cad-sidecar-1.schema.json"
GENERATED_BY = "tools/cad pull"
PIECES = ("identity", "document", "parameters", "drift", "timeline", "mass_properties", "exports", "component", "consumes")


def problems(doc: dict) -> list:
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    return [f"{'/'.join(str(x) for x in e.absolute_path) or '<root>'}: {e.message}" for e in jsonschema.Draft202012Validator(schema).iter_errors(doc)]


def assemble(*, require_healthy: bool = False, **pieces) -> dict:
    """The sidecar of the pieces. ValueError when it does not validate, or (require_healthy) when the timeline is not healthy. `inputs` is the hash of the
    content, so the same pulled state gives the same file."""
    if require_healthy:
        t = pieces.get("timeline", {})
        if not t.get("healthy", False):
            raise ValueError("the timeline is not healthy: " + ", ".join(t.get("failed_features", [])))
    doc = {"schema": "cad-sidecar/1", "generated_by": GENERATED_BY, **{k: pieces[k] for k in PIECES if k in pieces}}
    doc["inputs"] = "sha256:" + addr.hash_value({k: v for k, v in doc.items() if k not in addr.BANNER_KEYS})
    bad = problems(doc)
    if bad:
        raise ValueError("the sidecar does not validate: " + "; ".join(bad))
    return doc


def dumps(doc: dict) -> str:
    return json.dumps(doc, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def write(path, doc: dict) -> None:
    bad = problems(doc)
    if bad:
        raise ValueError("the sidecar does not validate: " + "; ".join(bad))
    Path(path).write_text(dumps(doc), encoding="utf-8", newline="\n")
