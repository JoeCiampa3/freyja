"""
References: where a record id is mentioned in files. Two uses, one whole-token rule (the roadmap's, imported read-only), files only (commit
messages are left out because a generated file must not depend on git history).

- `scan`: what the build reads for the dossiers, roadmap/nodes/ only. Prose files change too often to be inputs of a generated file.
- `live`: what `fy thread refs <id>` reads, docs/memos/, notebook/ and log/, uncapped, newest file first. Never part of a build.
"""
from __future__ import annotations

import re
from pathlib import Path

from roadmap.refs import MAX_LINE_CHARS, token_re

BUILD_DIRS = ("roadmap/nodes",)
LIVE_DIRS = ("docs/memos", "notebook", "log")


def scan(root, ids, dirs=BUILD_DIRS) -> dict:
    """{id: [{"path", "line", "text"}]} sorted by path and line; every id is a key."""
    root = Path(root)
    ids = sorted(ids)
    out = {i: [] for i in ids}
    if not ids:
        return out
    prefilter = re.compile("|".join(re.escape(i) for i in ids))
    rx = {i: token_re(i) for i in ids}
    for d in dirs:
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


def live(root, id: str) -> list:
    """Mentions of `id` in LIVE_DIRS: [{"path", "line", "text"}], files newest first (modification time, then path), lines in order."""
    root = Path(root)
    files = [p for d in LIVE_DIRS if (root / d).is_dir() for p in (root / d).rglob("*") if p.is_file()]
    files.sort(key=lambda p: (-p.stat().st_mtime_ns, p.relative_to(root).as_posix()))
    rx = token_re(id)
    out = []
    for p in files:
        try:
            text = p.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        rel = p.relative_to(root).as_posix()
        out += [{"path": rel, "line": n, "text": line.strip()[:MAX_LINE_CHARS]} for n, line in enumerate(text.splitlines(), 1) if rx.search(line)]
    return out
