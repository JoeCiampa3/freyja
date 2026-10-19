"""
Thread query resolution, in order: the exact id; the query with one kind prefix added (`seg.`, `jnt.`, `part.`, `if.`, `lc.`, `hn.`, `work.`),
when exactly one record has it; a unique case-insensitive substring of an id. Otherwise the candidates (ambiguous, up to 10) or the close ids
(none). The roadmap's rules (tools/roadmap/query.py) with the kind prefixes in place of `rm.`.
"""
from __future__ import annotations

import difflib

from .edges import PREFIX_KIND

MAX_CANDIDATES = 10


def resolve(b, q: str):
    """('ok', id) | ('ambiguous', [matching ids, sorted, at most 10]) | ('none', [close ids])."""
    ids = sorted(b.recs)
    q = q.strip()
    if q in b.recs:
        return "ok", q
    prefixed = [f"{p}.{q}" for p in sorted(PREFIX_KIND) if f"{p}.{q}" in b.recs]
    if len(prefixed) == 1:
        return "ok", prefixed[0]
    low = q.lower()
    hits = [i for i in ids if low and low in i.lower()]
    if len(hits) == 1:
        return "ok", hits[0]
    if hits:
        return "ambiguous", hits[:MAX_CANDIDATES]
    return "none", sorted(difflib.get_close_matches(q, ids, n=MAX_CANDIDATES, cutoff=0.6))
