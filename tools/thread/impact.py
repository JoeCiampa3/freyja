"""
Impact of an address, and the in-memory what-if. Neither writes anything.

`impact(store, address)`: the work items whose consumed addresses (the record's list and the baseline stamp's) overlap the address (one
pointer a prefix of the other), and the generated outputs whose content depends on its source (a build records, per output, the addresses
it was built from).

`whatif(store, edits)`: apply `<address>=<YAML value>` edits to an in-memory copy of the store, rebuild, and report which outputs would
change (byte for byte), which work items would change status, and the errors and new warnings the edit would cause.
"""
from __future__ import annotations

import yaml

from . import addr
from . import store as st
from .build import Build


def impact(store: st.Store, address: str) -> dict:
    addr.parse(address)
    b = Build(store)
    work = []
    for id, r in sorted(b.recs.items()):
        if r["kind"] != "work_item":
            continue
        mine = list(r["consumes"])
        if store.stamps.get(id):
            mine += [c["address"] for c in store.stamps[id][-1][1]["consumes"]]
        if any(addr.overlaps(address, a) for a in mine):
            work.append(id)
    outputs = sorted(p for p, srcs in b.sources.items() if any(addr.overlaps(address, a) for a in srcs))
    return {"address": address, "work": work, "outputs": outputs, "errors": [i.to_dict() for i in b.errors]}


def parse_edit(text: str):
    if "=" not in text or "#" not in text.split("=", 1)[0]:
        raise ValueError(f"an edit is <address>=<YAML value>, got {text!r}")
    a, v = text.split("=", 1)
    addr.parse(a)
    try:
        value = yaml.safe_load(v)
    except yaml.YAMLError as e:
        raise ValueError(f"the value of {a} is not YAML: {e}") from None
    return a, value


def whatif(store: st.Store, edits: list) -> dict:
    parsed = [parse_edit(e) for e in edits]
    before = Build(store)
    edited = store.edited()
    for a, v in parsed:
        st.apply_edit(edited, a, v)
    after = Build(edited)
    changed = sorted(p for p in set(before.outputs) | set(after.outputs) if before.outputs.get(p) != after.outputs.get(p)) if not after.errors else []
    old = {i: w["status"] for i, w in before.work.items()}
    new = {i: w["status"] for i, w in after.work.items()}
    seen = {(i.code, i.ids, i.message) for i in before.warnings}
    return {"edits": [e for e in edits], "errors": [i.to_dict() for i in after.errors],
            "warnings": [i.to_dict() for i in after.warnings if (i.code, i.ids, i.message) not in seen],
            "outputs_changed": changed,
            "status_changes": {i: {"from": old.get(i), "to": new.get(i)} for i in sorted(set(old) | set(new)) if old.get(i) != new.get(i)}}
