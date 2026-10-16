"""
Roadmap references: where a node id is mentioned. An id counts as mentioned only as a whole token, bounded on both sides by characters
outside [a-z0-9_.-]; a full stop that ends a sentence (not followed by another id character) does not extend the token. File references
come from log/, docs/memos/ and notebook/ (file and line); commit references from `git log --fixed-strings --grep` (short hash and subject),
and only when the root is itself a git repository.
"""
from __future__ import annotations

import re
import subprocess
from dataclasses import dataclass
from pathlib import Path

SEARCH_DIRS = ("log", "docs/memos", "notebook")
MAX_LINE_CHARS = 200


@dataclass(frozen=True)
class FileRef:
    path: str
    line: int
    text: str

    def to_dict(self) -> dict:
        return {"path": self.path, "line": self.line, "text": self.text}


def token_re(id: str):
    return re.compile(r"(?<![a-z0-9_.-])" + re.escape(id) + r"(?![a-z0-9_-])(?!\.[a-z0-9_-])")


def file_references(root, id: str) -> list:
    rx = token_re(id)
    root = Path(root)
    out = []
    for d in SEARCH_DIRS:
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
                if rx.search(line):
                    out.append(FileRef(rel, n, line.strip()[:MAX_LINE_CHARS]))
    return sorted(out, key=lambda r: (r.path, r.line))


def commit_references(root, id: str) -> list:
    """[(short hash, subject)] newest first; [] when root is not a git repository or git is unavailable."""
    root = Path(root)
    if not (root / ".git").exists():
        return []
    try:
        res = subprocess.run(["git", "log", "--fixed-strings", f"--grep={id}", "--format=%h%x1f%s%x1f%B%x1e"], cwd=root, capture_output=True,
                             text=True, encoding="utf-8", check=True)
    except (OSError, subprocess.CalledProcessError):
        return []
    rx = token_re(id)
    out = []
    for rec in res.stdout.split("\x1e"):
        parts = rec.strip("\n").split("\x1f")
        if len(parts) == 3 and rx.search(parts[1] + "\n" + parts[2]):
            out.append((parts[0].strip(), parts[1]))
    return out


def references(root, id: str, git: bool = True) -> dict:
    return {"files": [r.to_dict() for r in file_references(root, id)], "commits": [{"hash": h, "subject": s} for h, s in (commit_references(root, id) if git else [])]}
