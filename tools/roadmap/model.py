"""
Roadmap model: nodes loaded from roadmap/nodes/<id>.md under a root directory, and the issues found while loading.

A node file is YAML front matter between two `---` lines followed by free Markdown that machines ignore. Loading checks the shape of
each file (docs/schemas/roadmap-node-1.json) and that its filename stem equals its id. Structure across nodes is validate.py's job.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path

import jsonschema
import yaml

NODES_DIR = "roadmap/nodes"
NODE_SCHEMA = "docs/schemas/roadmap-node-1.json"
ID_RE = re.compile(r"^rm[.][a-z0-9-]+$")
ESTIMATE_CAP_DAYS = 3.0  # a leaf is sized to finish in hours to a few days; above this the estimate is a warning (brief: warnings)

_YAML_LOADER = getattr(yaml, "CSafeLoader", yaml.SafeLoader)  # the C loader is several times faster; same results
_SCHEMA_PATH = Path(__file__).resolve().parents[2] / NODE_SCHEMA  # the schema ships with the library, not with a fixture root


@dataclass(frozen=True)
class Issue:
    code: str
    message: str
    ids: tuple = ()
    paths: tuple = ()

    def to_dict(self) -> dict:
        return {"code": self.code, "message": self.message, "ids": list(self.ids), "paths": list(self.paths)}


@dataclass
class Node:
    id: str
    title: str
    parent: str | None
    path: str  # repo-relative, forward slashes
    blocked_by: list = field(default_factory=list)
    stub: bool = False
    estimate_days: float | None = None
    tags: list = field(default_factory=list)
    done_when: dict | None = None
    active: bool = False
    signed_off: bool = False
    superseded_by: str | None = None
    body: str = ""

    @property
    def superseded(self) -> bool:
        return self.superseded_by is not None


def _schema_validator():
    schema = json.loads(_SCHEMA_PATH.read_text(encoding="utf-8"))
    return jsonschema.Draft202012Validator(schema)


def split_front_matter(text: str):
    """(front matter text, body) or None when the file does not open with a --- block that is closed by a second --- line."""
    lines = text.lstrip("﻿").replace("\r\n", "\n").split("\n")
    if not lines or lines[0].rstrip() != "---":
        return None
    for i in range(1, len(lines)):
        if lines[i].rstrip() == "---":
            return "\n".join(lines[1:i]), "\n".join(lines[i + 1:])
    return None


def _describe(err) -> str:
    where = ".".join(str(p) for p in err.absolute_path) or "(top level)"
    return f"{where}: {err.message}"[:300]


def load_nodes(root):
    """Load every roadmap/nodes/*.md under root. Returns (nodes, known_ids, issues).

    nodes: id -> Node, for files that parsed, matched the schema and whose stem equals the id. known_ids: those ids plus the ids (or
    stems) of files that did not, so that a reference to a broken node is not also reported as unresolved. issues: schema, filename-id
    and id-format errors."""
    root = Path(root)
    directory = root / NODES_DIR
    validator = _schema_validator()
    nodes, known, issues = {}, set(), []
    files = sorted(directory.glob("*.md")) if directory.is_dir() else []
    for f in files:
        rel = f"{NODES_DIR}/{f.name}"
        stem = f.stem
        known.add(stem)
        try:
            text = f.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as e:
            issues.append(Issue("schema", f"{rel}: cannot read the file ({e.__class__.__name__})", (stem,), (rel,)))
            continue
        parts = split_front_matter(text)
        if parts is None:
            issues.append(Issue("schema", f"{rel}: no YAML front matter (the file must open with a --- block closed by a second ---); node {stem}", (stem,), (rel,)))
            continue
        try:
            raw = yaml.load(parts[0], Loader=_YAML_LOADER)
        except yaml.YAMLError as e:
            issues.append(Issue("schema", f"{rel}: front matter is not valid YAML ({str(e).splitlines()[0] if str(e) else e.__class__.__name__}); node {stem}", (stem,), (rel,)))
            continue
        if not isinstance(raw, dict):
            issues.append(Issue("schema", f"{rel}: front matter is not a mapping; node {stem}", (stem,), (rel,)))
            continue
        rid = raw.get("id") if isinstance(raw.get("id"), str) else stem
        known.add(rid)
        errs = sorted(validator.iter_errors(raw), key=lambda e: [str(p) for p in e.absolute_path])
        if errs:
            for e in errs:
                if list(e.absolute_path) == ["id"] and e.validator == "pattern":
                    issues.append(Issue("id-format", f"{rel}: id {raw.get('id')!r} does not match rm.<lowercase letters, digits, hyphens>", (rid,), (rel,)))
                else:
                    issues.append(Issue("schema", f"{rel}: node {rid}: {_describe(e)}", (rid,), (rel,)))
            continue
        if raw["id"] != stem:
            issues.append(Issue("filename-id", f"{rel}: filename stem {stem!r} differs from id {raw['id']!r}; node {rid}", (rid,), (rel,)))
            continue
        nodes[rid] = Node(
            id=rid, title=raw["title"], parent=raw["parent"], path=rel, blocked_by=list(raw.get("blocked_by", [])),
            stub=bool(raw.get("stub", False)), estimate_days=raw.get("estimate_days"), tags=list(raw.get("tags", [])),
            done_when=raw.get("done_when"), active=bool(raw.get("active", False)), signed_off=bool(raw.get("signed_off", False)),
            superseded_by=raw.get("superseded_by"), body=parts[1].lstrip("\n"))
    return nodes, known, issues
