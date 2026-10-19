"""
References for the dossiers: where a record id is mentioned in files. Files only: roadmap/nodes/, docs/memos/, notebook/ and log/. Commit
messages are left out because a generated file must not depend on git history. The whole-token rule is the roadmap's (imported, read-only).
"""
from __future__ import annotations

import re
from pathlib import Path

from roadmap.refs import MAX_LINE_CHARS, token_re

DIRS = ("roadmap/nodes", "docs/memos", "notebook", "log")


def scan(root, ids) -> dict:
    """{id: [{"path", "line", "text"}]} sorted by path and line; every id is a key."""
    root = Path(root)
    ids = sorted(ids)
    out = {i: [] for i in ids}
    if not ids:
        return out
    prefilter = re.compile("|".join(re.escape(i) for i in ids))
    rx = {i: token_re(i) for i in ids}
    for d in DIRS:
        base = root / d
        if not base.is_dir():
            continue
        for p in sorted(x for x in base.rglob("*") if x.is_file()):
            try:
                text = p.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError):
                continue
            rel = p.relative_to(root).as_posix()
            for n, line in enumerate(text.splitlines(), 1):
                if not prefilter.search(line):
                    continue
                for i in ids:
                    if rx[i].search(line):
                        out[i].append({"path": rel, "line": n, "text": line.strip()[:MAX_LINE_CHARS]})
    return out
