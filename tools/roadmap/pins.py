"""
Pins: personal bookmarks to any roadmap node (docs/briefs/architecture/roadmap-brief2.md, T6). Not roadmap state: nothing derives from
them and roadmap/.pins.json is gitignored (per clone, personal). The file is a sorted JSON list of node ids, written deterministically
(two-space indent, trailing newline, LF). A file that is not that list is an error and is never overwritten. An id whose node no longer
exists stays in the file (it dangles); callers list it as dangling and the owner removes it.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

PINS_FILE = "roadmap/.pins.json"


class PinsError(ValueError):
    """roadmap/.pins.json exists but is not a JSON list of ids."""


def _path(root) -> Path:
    return Path(root) / PINS_FILE


def load(root) -> list:
    """The pinned ids, sorted. [] when there is no file."""
    p = _path(root)
    if not p.is_file():
        return []
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        raise PinsError(f"{PINS_FILE} cannot be read ({e.__class__.__name__}); fix or delete it") from e
    if not isinstance(data, list) or not all(isinstance(x, str) for x in data):
        raise PinsError(f"{PINS_FILE} is not a JSON list of node ids; fix or delete it")
    return sorted(set(data))


def _save(root, ids) -> None:
    p = _path(root)
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_name(p.name + ".tmp")
    with open(tmp, "w", encoding="utf-8", newline="\n") as f:
        f.write(json.dumps(sorted(set(ids)), indent=2) + "\n")
    os.replace(tmp, p)


def add(root, id: str) -> bool:
    """Pin `id`. True when the file changed."""
    have = load(root)
    if id in have:
        return False
    _save(root, [*have, id])
    return True


def remove(root, id: str) -> bool:
    """Unpin `id`. True when the file changed."""
    have = load(root)
    if id not in have:
        return False
    _save(root, [x for x in have if x != id])
    return True
