"""
The thread's inputs read from a root directory: records, stamps, decision front matter, the snapshot and the model. Loading is plain parsing;
every judgement about the contents is build.py's. A Store can be edited in memory (`edited`), which is how the what-if works: nothing is
ever written back.

The model is read with xml.etree from sim/models/freyja.xml; this package must not import mujoco, so that it runs anywhere the roadmap does.
"""
from __future__ import annotations

import copy
import csv
import hashlib
import io
import json
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from pathlib import Path

import jsonschema
import yaml

from . import addr

RECORDS_DIR = "thread/records"
STAMPS_DIR = "thread/stamps"
DECISIONS_DIR = "decisions"
SNAPSHOT_PATH = "params/snapshot.csv"
MODEL_PATH = "sim/models/freyja.xml"
SCHEMA_DIR = Path(__file__).resolve().parents[2] / "docs" / "schemas"  # the schemas ship with the library, not with a fixture root

_YAML_LOADER = getattr(yaml, "CSafeLoader", yaml.SafeLoader)  # the C loader is several times faster; same results


@dataclass(frozen=True)
class Issue:
    level: str  # error | warning
    code: str
    message: str
    ids: tuple = ()

    def to_dict(self) -> dict:
        return {"level": self.level, "code": self.code, "message": self.message, "ids": list(self.ids)}


def error(code, message, ids=()):
    return Issue("error", code, message, tuple(ids))


def warning(code, message, ids=()):
    return Issue("warning", code, message, tuple(ids))


_validators: dict = {}


def validator(name: str):
    if name not in _validators:
        schema = json.loads((SCHEMA_DIR / name).read_text(encoding="utf-8"))
        _validators[name] = jsonschema.Draft202012Validator(schema)
    return _validators[name]


def schema_message(v, doc) -> str | None:
    """None when the document is valid, otherwise the best-matching schema error as one line."""
    err = jsonschema.exceptions.best_match(v.iter_errors(doc))
    if err is None:
        return None
    where = "/".join(str(p) for p in err.absolute_path)
    return f"{where + ': ' if where else ''}{err.message}"[:300]


def normalise(doc):
    """YAML timestamps and other non-JSON scalars become strings, so every document is plain JSON."""
    return json.loads(json.dumps(doc, default=str))


@dataclass
class Model:
    bodies: dict  # body name -> parent body name (None under the world)
    hinges: dict  # hinge name -> body name
    sha: str

    @classmethod
    def parse(cls, data: bytes) -> "Model":
        root = ET.fromstring(data)
        bodies, hinges = {}, {}

        def walk(el, parent):
            for c in el:
                if c.tag == "body":
                    name = c.get("name")
                    bodies[name] = parent
                    for j in c.findall("joint"):
                        if j.get("name") and j.get("type", "hinge") == "hinge":
                            hinges[j.get("name")] = name
                    walk(c, name)

        world = root.find("worldbody")
        if world is not None:
            walk(world, None)
        return cls(bodies, hinges, hashlib.sha256(data).hexdigest()[:12])


@dataclass
class Store:
    root: Path
    records: dict = field(default_factory=dict)  # id -> authored record (plain JSON)
    files: dict = field(default_factory=dict)  # id -> repo-relative path
    issues: list = field(default_factory=list)
    snapshot: dict = field(default_factory=dict)  # key -> (value string as written, sheet_source)
    snapshot_sha: str = ""
    model: Model | None = None
    stamps: dict = field(default_factory=dict)  # work id -> [(stamp name, document)] sorted by name; documents that fail their schema are not here
    stamp_dirs: set = field(default_factory=set)
    decisions: list = field(default_factory=list)  # [{id, status, links, path}]

    def edited(self) -> "Store":
        """A deep copy for the in-memory what-if."""
        return copy.deepcopy(self)


def load(root) -> Store:
    root = Path(root)
    s = Store(root=root)
    _load_records(s)
    _load_snapshot(s)
    _load_model(s)
    _load_stamps(s)
    _load_decisions(s)
    return s


def _load_records(s: Store):
    base = s.root / RECORDS_DIR
    if not base.is_dir():
        return
    paths = sorted((p for p in base.rglob("*.yaml") if p.is_file()), key=lambda p: (len(p.relative_to(base).parts), p.relative_to(base).as_posix()))
    for p in paths:
        rel = p.relative_to(s.root).as_posix()
        stem = p.stem
        try:
            doc = yaml.load(p.read_text(encoding="utf-8"), Loader=_YAML_LOADER)
        except (yaml.YAMLError, UnicodeDecodeError) as e:
            s.issues.append(error("schema", f"{rel}: not readable YAML: {str(e).splitlines()[0]}", (stem,)))
            continue
        if not isinstance(doc, dict):
            s.issues.append(error("schema", f"{rel}: a record is a YAML mapping", (stem,)))
            continue
        doc = normalise(doc)
        id = doc.get("id") if isinstance(doc.get("id"), str) else stem
        if id != stem:
            s.issues.append(error("filename-id", f"{rel}: the id {id!r} differs from the filename stem {stem!r}", (id,)))
        if id in s.records:
            s.issues.append(error("duplicate-id", f"{rel}: the id {id!r} is already used by {s.files[id]}", (id,)))
            continue
        s.records[id] = doc
        s.files[id] = rel


def _load_snapshot(s: Store):
    p = s.root / SNAPSHOT_PATH
    if not p.is_file():
        s.issues.append(error("input-missing", f"{SNAPSHOT_PATH} is missing (run `fy build`)", ()))
        return
    data = p.read_bytes()
    s.snapshot_sha = hashlib.sha256(data).hexdigest()[:12]
    for row in csv.DictReader(io.StringIO(data.decode("utf-8"), newline="")):
        s.snapshot[row["placeholder"]] = (row["value"], row["sheet_source"])


def _load_model(s: Store):
    p = s.root / MODEL_PATH
    if not p.is_file():
        s.issues.append(error("input-missing", f"{MODEL_PATH} is missing (run `fy build`)", ()))
        return
    try:
        s.model = Model.parse(p.read_bytes())
    except ET.ParseError as e:
        s.issues.append(error("input-missing", f"{MODEL_PATH} is not valid XML: {e}", ()))


def _load_stamps(s: Store):
    base = s.root / STAMPS_DIR
    if not base.is_dir():
        return
    v = validator("thread-stamp-1.schema.json")
    for d in sorted(x for x in base.iterdir() if x.is_dir()):
        work = d.name
        s.stamp_dirs.add(work)
        for p in sorted(d.glob("*.json")):
            rel = p.relative_to(s.root).as_posix()
            try:
                doc = json.loads(p.read_text(encoding="utf-8"))
            except (ValueError, UnicodeDecodeError) as e:
                s.issues.append(error("stamp-schema", f"{rel}: not readable JSON: {e}", (work,)))
                continue
            msg = schema_message(v, doc)
            if msg is None and doc["work"] != work:
                msg = f"work {doc['work']!r} differs from the directory {work!r}"
            if msg is None and doc["stamp"] != p.stem:
                msg = f"stamp {doc['stamp']!r} differs from the filename stem {p.stem!r}"
            if msg is not None:
                s.issues.append(error("stamp-schema", f"{rel}: {msg}", (work,)))
                continue
            s.stamps.setdefault(work, []).append((p.stem, doc))


def _load_decisions(s: Store):
    base = s.root / DECISIONS_DIR
    if not base.is_dir():
        return
    for p in sorted(base.glob("*.md")):
        text = p.read_text(encoding="utf-8")
        if not text.startswith("---"):
            continue
        parts = text.split("---", 2)
        if len(parts) < 3:
            continue
        try:
            front = yaml.load(parts[1], Loader=_YAML_LOADER)
        except yaml.YAMLError:
            continue
        if isinstance(front, dict) and isinstance(front.get("id"), str):
            links = front.get("links") or []
            s.decisions.append({"id": front["id"], "status": str(front.get("status", "")), "links": [str(x) for x in links] if isinstance(links, list) else [],
                                "path": p.relative_to(s.root).as_posix()})


def apply_edit(s: Store, address: str, value) -> None:
    """Edit a record or a snapshot value in place (on an `edited()` copy). ValueError when the source cannot be edited."""
    source, pointer = addr.parse(address)
    if source == "snapshot":
        toks = addr._tokens(pointer)
        if len(toks) != 1:
            raise ValueError("a snapshot edit names one key: snapshot#/<placeholder>=<value>")
        key = toks[0]
        if key not in s.snapshot:
            raise ValueError(f"the snapshot has no key {key!r}")
        s.snapshot[key] = (str(value), s.snapshot[key][1])
        s.snapshot_sha = addr.hash_value(s.snapshot)  # not the hash of a rebuilt file, but it moves with every edit, which is what banners need
        return
    if source in s.records:
        doc = s.records[source]
        if pointer == "":
            if not isinstance(value, dict):
                raise ValueError("an edit of a whole record needs a mapping")
            s.records[source] = normalise(value)
        else:
            addr.pointer_set(doc, pointer, normalise(value))
        return
    raise ValueError(f"cannot edit {address!r}: only thread records and snapshot values are editable (generated outputs are derived)")
