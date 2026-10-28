"""
Roadmap done_when evaluation. Every type is read from files already in the repo (the root directory); the library never runs a
simulation, a test suite or a check. A leaf's evaluation is pass, fail, awaiting or unknown, with a one-line reason and, for metrics, the
measured value. `awaiting` means the evidence does not exist yet but could (the file is absent and its directory exists; the check is
recorded as not run): normal for unfinished work, so it draws no warning. `unknown` means the evidence cannot be read or cannot be
expected (an unparseable record, a pointer that does not resolve, a missing parent directory, a check id nobody lists): it warns.
Neither counts as a pass.

Where a check's result is recorded: docs/STATE.md lists every check as `- <id> | <tier> | <STATUS>` under "## Checks". That file is
generated, tracked and deterministic. checks/last_run.json is gitignored and is not used.
"""
from __future__ import annotations

import json
import operator
import re
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

import jsonschema
import yaml

from .model import split_front_matter

STATE_FILE = "docs/STATE.md"
THREAD_GRAPH = "thread/graph.json"        # the `work` criterion reads this generated file and never builds the thread
OPS = {"<": operator.lt, "<=": operator.le, ">": operator.gt, ">=": operator.ge, "==": operator.eq}


@dataclass(frozen=True)
class Evaluation:
    result: str  # pass | fail | awaiting | unknown
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


def _absent(rel, p) -> Evaluation:
    """The evidence file is absent: awaiting when its parent directory exists, else unknown (nothing says where it would appear)."""
    if p.parent.is_dir():
        return Evaluation("awaiting", f"{rel} does not exist yet")
    return Evaluation("unknown", f"{rel} does not exist and its directory {PurePosixPath(rel).parent} is missing")


def _artifact(root, dw):
    p = safe_path(root, dw["path"])
    if p is None:
        return Evaluation("unknown", f"path {dw['path']!r} is not a relative path inside the root")
    if not p.is_file():
        return _absent(dw["path"], p)
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
        return _absent(dw["record"], p)
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


NOT_RUN = "not run"  # `fy state --no-run` writes "not run (--no-run)" in place of the check lines
_NOT_RUN_STATUSES = ("NOT_RUN", "NOT RUN")


def recorded_checks(root):
    """check id -> status as recorded in docs/STATE.md; NOT_RUN when the Checks section says the checks were not run; None when there
    is no usable record (no file, no Checks section, or an empty one)."""
    p = Path(root) / STATE_FILE
    if not p.is_file():
        return None
    out, in_section, not_run = {}, False, False
    for line in p.read_text(encoding="utf-8").splitlines():
        if line.startswith("## "):
            in_section = line.strip() == "## Checks"
        elif in_section:
            m = _CHECK_LINE.match(line)
            if m:
                out[m.group(1)] = m.group(3)
            elif line.strip().lower().startswith("not run"):
                not_run = True
    if out:
        return out
    return NOT_RUN if not_run else None


def _check(root, dw):
    recorded = recorded_checks(root)
    if recorded is None:
        return Evaluation("unknown", f"{STATE_FILE} has no recorded check results")
    if recorded == NOT_RUN:
        return Evaluation("awaiting", f"the checks are recorded as not run in {STATE_FILE}")
    status = recorded.get(dw["check"])
    if status is None:
        return Evaluation("unknown", f"{dw['check']} is not in the recorded results of {STATE_FILE}")
    if status in _NOT_RUN_STATUSES:
        return Evaluation("awaiting", f"{dw['check']} is recorded as not run")
    if status == "PASS":
        return Evaluation("pass", f"{dw['check']} recorded PASS")
    return Evaluation("fail", f"{dw['check']} recorded {status}")


def _metric(root, dw):
    p = safe_path(root, dw["record"])
    if p is None:
        return Evaluation("unknown", f"record {dw['record']!r} is not a relative path inside the root")
    if not p.is_file():
        return _absent(dw["record"], p)
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


def _work(root, dw):
    want = dw.get("status", "current")
    p = safe_path(root, THREAD_GRAPH)
    if p is None or not p.is_file():
        return Evaluation("unknown", f"{THREAD_GRAPH} does not exist: run `fy thread build`")
    try:
        graph = json.loads(p.read_text(encoding="utf-8"))
        statuses = graph["work_statuses"]
        if not isinstance(statuses, dict):
            raise TypeError
    except (OSError, ValueError, KeyError, TypeError):
        return Evaluation("unknown", f"{THREAD_GRAPH} cannot be read as a thread graph")
    have = statuses.get(dw["work"])
    if not isinstance(have, str):
        return Evaluation("unknown", f"{dw['work']} is not a work item in {THREAD_GRAPH}")
    if have == want:
        return Evaluation("pass", f"{dw['work']} is {have}")
    if have == "unstamped":
        return Evaluation("awaiting", f"{dw['work']} is unstamped (needs {want})")
    return Evaluation("fail", f"{dw['work']} is {have} (needs {want})")


def evaluate(node, root) -> Evaluation | None:
    """The node's done_when evaluated against root; None for a node without one."""
    dw = node.done_when
    if dw is None:
        return None
    t = dw["type"]
    if t == "manual":
        return Evaluation("pass", "signed off") if node.signed_off else Evaluation("fail", "not signed off")
    return {"artifact": _artifact, "decision": _decision, "check": _check, "metric": _metric, "work": _work}[t](root, dw)


def referenced_files(node) -> list:
    """Repo-relative files whose content the node's evaluation reads (for the staleness hash and the server's file watch)."""
    dw = node.done_when or {}
    out = []
    for key in ("path", "schema", "record"):
        if key in dw:
            out.append(dw[key])
    if dw.get("type") == "check":
        out.append(STATE_FILE)
    if dw.get("type") == "work":
        out.append(THREAD_GRAPH)
    return out
