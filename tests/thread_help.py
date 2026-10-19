"""
Helpers for the thread tests: copy the hand-written base root (a tiny model and snapshot with valid records), overlay a fixture directory on
it, write records and stamps, and load the library from tools/.
"""
import json
import shutil
import sys
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parents[1]
for _p in (str(REPO / "tools"), str(REPO / "sim" / "scripts")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

FIXTURES = Path(__file__).parent / "fixtures" / "thread"
BASE = FIXTURES / "base"


def make_root(dest, overlay=None):
    """A copy of the base root, with the files of `overlay` (a directory) copied over it."""
    dest = Path(dest)
    shutil.copytree(BASE, dest, dirs_exist_ok=True)
    if overlay is not None:
        shutil.copytree(overlay, dest, dirs_exist_ok=True)
    return dest


def write_record(root, **fields):
    """Write thread/records/<id>.yaml with the common fields defaulted."""
    fields.setdefault("schema", "thread-record/1")
    fields.setdefault("status", "proposed")
    fields.setdefault("purpose", "A test record.")
    p = Path(root) / "thread" / "records" / f"{fields['id']}.yaml"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(yaml.safe_dump(fields, sort_keys=True), encoding="utf-8", newline="\n")
    return p


def edit_record(root, id, **changes):
    p = Path(root) / "thread" / "records" / f"{id}.yaml"
    doc = yaml.safe_load(p.read_text(encoding="utf-8"))
    for k, v in changes.items():
        if v is None:
            doc.pop(k, None)
        else:
            doc[k] = v
    p.write_text(yaml.safe_dump(doc, sort_keys=True), encoding="utf-8", newline="\n")


def edit_snapshot(root, key, value):
    p = Path(root) / "params" / "snapshot.csv"
    lines = p.read_text(encoding="utf-8").splitlines()
    out = [f"{key},{value},{ln.split(',', 2)[2]}" if ln.startswith(key + ",") else ln for ln in lines]
    p.write_text("\n".join(out) + "\n", encoding="utf-8", newline="\n")


def codes(issues):
    return sorted(i.code for i in issues)
