"""
The roadmap's controlled tag vocabulary (roadmap/tags.yaml, docs/schemas/roadmap-tags-1.schema.json; docs/briefs/architecture/roadmap-brief3.md T2).

A tag is free (no colon: never checked) or namespaced, `namespace:value`, split at the first colon. A namespaced tag must name a namespace
and a value in the vocabulary (an error naming the node and the tag: typo protection); a node carrying two values of one namespace draws a
warning, because a node belongs to one region and one phase. A missing tags.yaml means no namespaces, so any namespaced tag is an error. A
tags.yaml that cannot be read or does not match its schema is one `tags-file` error, and then namespaced tags are not checked at all (the
file is what is wrong, and an error per tag would bury it).
"""
from __future__ import annotations

import json
from pathlib import Path

import jsonschema
import yaml

from .model import Issue

TAGS_FILE = "roadmap/tags.yaml"
TAGS_SCHEMA = Path(__file__).resolve().parents[2] / "docs" / "schemas" / "roadmap-tags-1.schema.json"
_YAML_LOADER = getattr(yaml, "CSafeLoader", yaml.SafeLoader)


def load_vocabulary(root) -> tuple:
    """(vocabulary, issues): {namespace: {value: colour or None}}. Absent file: ({}, []). Unusable file: ({}, [one tags-file issue])."""
    path = Path(root) / TAGS_FILE
    if not path.is_file():
        return {}, []

    def broken(why):
        return {}, [Issue("tags-file", f"{TAGS_FILE}: {why}; the vocabulary is ignored until it is fixed", (), (TAGS_FILE,))]
    try:
        raw = yaml.load(path.read_text(encoding="utf-8"), Loader=_YAML_LOADER)
    except (OSError, UnicodeDecodeError) as e:
        return broken(f"cannot read the file ({e.__class__.__name__})")
    except yaml.YAMLError as e:
        return broken(f"not valid YAML ({str(e).splitlines()[0] if str(e) else e.__class__.__name__})")
    schema = json.loads(TAGS_SCHEMA.read_text(encoding="utf-8"))
    errs = sorted(jsonschema.Draft202012Validator(schema).iter_errors(raw), key=lambda e: [str(p) for p in e.absolute_path])
    if errs:
        e = errs[0]
        where = ".".join(str(p) for p in e.absolute_path) or "(top level)"
        return broken(f"{where}: {e.message}"[:300] + (f" (and {len(errs) - 1} more)" if len(errs) > 1 else ""))
    return {ns: dict(values) for ns, values in raw["namespaces"].items()}, []


def split(tag: str):
    """(namespace, value) of a namespaced tag, split at the first colon; None for a free tag."""
    return tuple(tag.split(":", 1)) if ":" in tag else None


def check(nodes: dict, vocabulary: dict) -> tuple:
    """(errors, warnings) for the tags of every node, superseded ones included. Call only with a usable vocabulary."""
    errors, warnings = [], []
    for i in sorted(nodes):
        n = nodes[i]
        seen = {}
        for tag in n.tags:
            parts = split(tag)
            if parts is None:
                continue
            ns, value = parts
            if ns not in vocabulary:
                known = ", ".join(sorted(vocabulary)) or "none defined"
                errors.append(Issue("tag-unknown-namespace", f"{n.path}: node {i} has tag {tag!r}, whose namespace {ns!r} is not in {TAGS_FILE} (namespaces: {known})", (i,), (n.path,)))
                continue
            if value not in vocabulary[ns]:
                errors.append(Issue("tag-unknown-value", f"{n.path}: node {i} has tag {tag!r}, but {value!r} is not a value of namespace {ns!r} in {TAGS_FILE} (values: {', '.join(vocabulary[ns])})", (i,), (n.path,)))
                continue
            seen.setdefault(ns, [])
            if value not in seen[ns]:
                seen[ns].append(value)
        for ns, values in sorted(seen.items()):
            if len(values) > 1:
                warnings.append(Issue("tag-duplicate-namespace", f"{n.path}: node {i} carries {len(values)} values of namespace {ns!r} ({', '.join(values)}); a node belongs to one", (i,), (n.path,)))
    return errors, warnings
