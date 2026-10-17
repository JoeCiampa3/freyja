"""
Roadmap query resolution, in order: the exact id; the id with an `rm.` prefix added; a unique case-insensitive substring of an id or a
title. Otherwise up to 10 candidates sorted by id.
"""
from __future__ import annotations

import difflib

MAX_CANDIDATES = 10


def search(rm, q: str):
    """('ok', [id]) | ('ambiguous', [every matching id]) | ('none', [close ids]). Nothing here is capped except the close ids."""
    ids = sorted(rm.nodes)
    q = q.strip()
    if q in rm.nodes:
        return "ok", [q]
    if f"rm.{q}" in rm.nodes:
        return "ok", [f"rm.{q}"]
    low = q.lower()
    hits = [i for i in ids if low and (low in i.lower() or low in rm.nodes[i].title.lower())]
    if len(hits) == 1:
        return "ok", hits
    if hits:
        return "ambiguous", hits
    return "none", sorted(difflib.get_close_matches(q if q.startswith("rm.") else f"rm.{q}", ids, n=MAX_CANDIDATES, cutoff=0.6))


def resolve(rm, q: str):
    """('ok', id) | ('ambiguous', [up to MAX_CANDIDATES ids]) | ('none', [close ids])."""
    status, got = search(rm, q)
    if status == "ok":
        return "ok", got[0]
    return status, got[:MAX_CANDIDATES]
