"""STEP normalisation: the FILE_NAME header carries a timestamp, so the repo hashes the file with that timestamp blanked and LF line endings (Stage 3b)."""
from __future__ import annotations

import hashlib
import re

_FILE_NAME = re.compile(rb"(FILE_NAME\s*\(\s*'(?:[^']|'')*'\s*,\s*')((?:[^']|'')*)(')")


def normalise(data: bytes) -> bytes:
    data = data.replace(b"\r\n", b"\n").replace(b"\r", b"\n")
    out, n = _FILE_NAME.subn(rb"\1\3", data, count=1)
    if n != 1:
        raise ValueError("not a STEP file with a FILE_NAME header")
    return out


def step_hash(data: bytes) -> str:
    return hashlib.sha256(normalise(data)).hexdigest()
