"""
Thread addresses: `<source>#<JSON pointer>` (RFC 6901; an empty pointer means the whole source), canonical JSON, and the 12-hex hash of a
value. The grammar and the hashing rule are fixed by docs/briefs/ariadne/stage3a-brief.md and CONVENTIONS section 3; a change to either is
a decision for Joe.
"""
from __future__ import annotations

import hashlib
import json
import re

BANNER_KEYS = ("generated_by", "inputs")
_ADDRESS_RE = re.compile(r"^([^#\s]+)#((?:/[^\s]*)?)$")


def canonical(value) -> str:
    """Sorted keys, no whitespace, non-ASCII kept."""
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def hash_value(value) -> str:
    return hashlib.sha256(canonical(value).encode("utf-8")).hexdigest()[:12]


def parse(address: str):
    """(source, pointer); ValueError when the text is not an address."""
    m = _ADDRESS_RE.match(address) if isinstance(address, str) else None
    if m is None:
        raise ValueError(f"not an address (expected <source>#<JSON pointer>): {address!r}")
    return m.group(1), m.group(2)


def _tokens(pointer: str) -> list:
    if pointer == "":
        return []
    return [t.replace("~1", "/").replace("~0", "~") for t in pointer[1:].split("/")]


def pointer_get(doc, pointer: str):
    """(True, value) or (False, None). List indices are plain decimal (no sign, no leading zero), as RFC 6901 requires."""
    cur = doc
    for t in _tokens(pointer):
        if isinstance(cur, dict):
            if t not in cur:
                return False, None
            cur = cur[t]
        elif isinstance(cur, list):
            if not re.fullmatch(r"0|[1-9][0-9]*", t) or int(t) >= len(cur):
                return False, None
            cur = cur[int(t)]
        else:
            return False, None
    return True, cur


def pointer_set(doc, pointer: str, value):
    """Set the value at a pointer in place. The parent must exist; a dict may gain a key, a list must be indexed within range."""
    toks = _tokens(pointer)
    if not toks:
        raise ValueError("an empty pointer replaces the whole source; edit its fields instead")
    ok, parent = pointer_get(doc, pointer.rsplit("/", 1)[0])
    if not ok:
        raise ValueError(f"the parent of {pointer!r} does not exist")
    last = toks[-1]
    if isinstance(parent, dict):
        parent[last] = value
    elif isinstance(parent, list) and re.fullmatch(r"0|[1-9][0-9]*", last) and int(last) < len(parent):
        parent[int(last)] = value
    else:
        raise ValueError(f"cannot set {pointer!r}")


def overlaps(a: str, b: str) -> bool:
    """Same source and one pointer a prefix of the other, on whole pointer segments."""
    sa, pa = parse(a)
    sb, pb = parse(b)
    if sa != sb:
        return False
    ta, tb = _tokens(pa), _tokens(pb)
    n = min(len(ta), len(tb))
    return ta[:n] == tb[:n]


def strip_banner(doc):
    """The generated-file banner keys are excluded before hashing (CONVENTIONS section 3)."""
    if isinstance(doc, dict):
        return {k: v for k, v in doc.items() if k not in BANNER_KEYS}
    return doc
