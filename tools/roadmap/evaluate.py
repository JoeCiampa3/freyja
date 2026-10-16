"""
Roadmap done_when evaluation. Every type is read from files already in the repo (the root directory); the library never runs a
simulation, a test suite or a check. A leaf's evaluation is pass, fail or unknown (a record that is missing or unreadable where a
record is the evidence), with a one-line reason and, for metrics, the measured value.

Where a check's result is recorded: docs/STATE.md lists every check as `- <id> | <tier> | <STATUS>` under "## Checks". That file is
generated, tracked and deterministic. checks/last_run.json is gitignored and is not used.
"""
from __future__ import annotations

import json
import operator
import re
from dataclasses import dataclass
from pathlib import Path

import jsonschema
import yaml

from .model import split_front_matter

STATE_FILE = "docs/STATE.md"
OPS = {"<": operator.lt, "<=": operator.le, ">": operator.gt, ">=": operator.ge, "==": operator.eq}


@dataclass(frozen=True)
class Evaluation:
    result: str  # pass | fail | unknown
    reason: str
    measured: float | None = None

    def to_dict(self) -> dict:
        return {"result": self.result, "reason": self.reason, "measured": self.measured}


def safe_path(root, rel):
    """root/rel when rel is a plain relative path that stays inside root, else None."""
    if not isinstance(rel, str) or not rel or "\\" in rel or rel.startswith("/") or re.match(r"^[A-Za-z]:", rel):
        return None
    if ".." in rel.split("/"):
        return None
    root = Path(root).resolve()
    p = (root / rel).resolve()
    try:
        p.relative_to(root)
    except ValueError:
        return None
    return Path(root) / rel


def resolve_pointer(doc, pointer: str):
    """RFC 6901. Raises KeyError when the pointer does not resolve."""
    if pointer == "":
        return doc
    if not pointer.startswith("/"):
        raise KeyError(pointer)
    cur = doc
    for raw in pointer[1:].split("/"):
        tok = raw.replace("~1", "/").replace("~0", "~")
        if isinstance(cur, dict):
            if tok not in cur:
                raise KeyError(pointer)
            cur = cur[tok]
        elif isinstance(cur, list):
            if not re.fullmatch(r"0|[1-9][0-9]*", tok) or int(tok) >= len(cur):
                raise KeyError(pointer)
            cur = cur[int(tok)]
        else:
            raise KeyError(pointer)
    return cur


def _load_structured(path: Path):
    text = path.read_text(encoding="utf-8")
    if path.suffix in (".yaml", ".yml"):
        return yaml.safe_load(text)
    return json.loads(text)


def _artifact(root, dw):
    p = safe_path(root, dw["path"])
    if p is None:
        return Evaluation("unknown", f"path {dw['path']!r} is not a relative path inside the root")
    if not p.is_file():
        return Evaluation("fail", f"{dw['path']} does not exist")
    if p.stat().st_size == 0:
        return Evaluation("fail", f"{dw['path']} is empty")
    if "schema" not in dw:
        return Evaluation("pass", f"{dw['path']} exists and is not empty")
    sp = safe_path(root, dw["schema"])
    if sp is None or not sp.is_file():
        return Evaluation("unknown", f"schema {dw['schema']} is not available")
    try:
        schema = json.loads(sp.read_text(encoding="utf-8"))
        validator = jsonschema.Draft202012Validator(schema)
    except (OSError, ValueError, jsonschema.SchemaError) as e:
        return Evaluation("unknown", f"schema {dw['schema']} is unusable ({e.__class__.__name__})")
    try:
        doc = _load_structured(p)
    except (OSError, ValueError, yaml.YAMLError) as e:
        return Evaluation("unknown", f"{dw['path']} cannot be parsed ({e.__class__.__name__})")
    errs = sorted(validator.iter_errors(doc), key=lambda e: [str(x) for x in e.absolute_path])
    if errs:
        where = "/".join(str(x) for x in errs[0].absolute_path) or "(top level)"
        return Evaluation("fail", f"{dw['path']} violates {dw['schema']} at {where}: {errs[0].message[:120]}")
    return Evaluation("pass", f"{dw['path']} validates against {dw['schema']}")


def _decision(root, dw):
    p = safe_path(root, dw["record"])
    if p is None:
        return Evaluation("unknown", f"record {dw['record']!r} is not a relative path inside the root")
    if not p.is_file():
        return Evaluation("fail", f"{dw['record']} does not exist")
    try:
        parts = split_front_matter(p.read_text(encoding="utf-8"))
        front = yaml.safe_load(parts[0]) if parts else None
    except (OSError, UnicodeDecodeError, yaml.YAMLError):
        front = None
    if not isinstance(front, dict) or "status" not in front:
        return Evaluation("unknown", f"{dw['record']} has no front matter status")
    status = str(front["status"])
    if status == "accepted":
        return Evaluation("pass", f"{dw['record']} is accepted")
    return Evaluation("fail", f"{dw['record']} has status {status}")


_CHECK_LINE = re.compile(r"^- (check\.[^ |]+) \| ([a-z]+) \| ([A-Z_]+)\s*$")


def recorded_checks(root) -> dict | None:
    """check id -> status as recorded in docs/STATE.md, or None when there is no usable record."""
    p = Path(root) / STATE_FILE
    if not p.is_file():
        return None
    out, in_section = {}, False
    for line in p.read_text(encoding="utf-8").splitlines():
        if line.startswith("## "):
            in_section = line.strip() == "## Checks"
        elif in_section:
            m = _CHECK_LINE.match(line)
            if m:
                out[m.group(1)] = m.group(3)
    return out or None


def _check(root, dw):
    recorded = recorded_checks(root)
    if recorded is None:
        return Evaluation("unknown", f"{STATE_FILE} has no recorded check results")
    status = recorded.get(dw["check"])
    if status is None:
        return Evaluation("unknown", f"{dw['check']} is not in the recorded results of {STATE_FILE}")
    if status == "PASS":
        return Evaluation("pass", f"{dw['check']} recorded PASS")
    return Evaluation("fail", f"{dw['check']} recorded {status}")


def _metric(root, dw):
    p = safe_path(root, dw["record"])
    if p is None or not p.is_file():
        return Evaluation("unknown", f"record {dw['record']} is not available")
    try:
        doc = _load_structured(p)
    except (OSError, ValueError, yaml.YAMLError) as e:
        return Evaluation("unknown", f"{dw['record']} cannot be parsed ({e.__class__.__name__})")
    try:
        value = resolve_pointer(doc, dw["pointer"])
    except KeyError:
        return Evaluation("unknown", f"pointer {dw['pointer']} does not resolve in {dw['record']}")
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return Evaluation("unknown", f"{dw['record']} {dw['pointer']} is not a number")
    holds = OPS[dw["op"]](value, dw["value"])
    units = f" {dw['units']}" if dw.get("units") else ""
    text = f"{dw['pointer']} = {value:g}{units} (needs {dw['op']} {dw['value']:g})"
    return Evaluation("pass" if holds else "fail", text, float(value))


def evaluate(node, root) -> Evaluation | None:
    """The node's done_when evaluated against root; None for a node without one."""
    dw = node.done_when
    if dw is None:
        return None
    t = dw["type"]
    if t == "manual":
        return Evaluation("pass", "signed off") if node.signed_off else Evaluation("fail", "not signed off")
    return {"artifact": _artifact, "decision": _decision, "check": _check, "metric": _metric}[t](root, dw)


def referenced_files(node) -> list:
    """Repo-relative files whose content the node's evaluation reads (for the staleness hash and the server's file watch)."""
    dw = node.done_when or {}
    out = []
    for key in ("path", "schema", "record"):
        if key in dw:
            out.append(dw[key])
    if dw.get("type") == "check":
        out.append(STATE_FILE)
    return out
