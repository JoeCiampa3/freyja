"""
Readers for what a load case's `evidence` cites: the clause labels of a decision record and the rows of a literature table. Pure text
functions; resolving an entry, grading it and deriving a case's sourcing are build.py's. The rules are CONVENTIONS section 3 (Thread terms).

Citations are checked by resolution and graded by the cited source's own status, never by a grade typed into the load case.
"""
from __future__ import annotations

import re

# The schemas a test record may validate against to count as evidence. Empty: no test-record format exists yet, and admitting any JSON would let
# a simulation run record count as a test. Adding a schema here is Joe's decision (the thread sources brief).
ADMITTED_TEST_SCHEMAS = ()
VERIFIED = "Verified"  # an admissible row's Status cell starts with this; "Unverified (abstract)" and the like do not

_PIPE = re.compile(r"(?<!\\)\|")


def cells(line: str) -> list:
    """The cells of a Markdown table row, split on unescaped `|` only."""
    parts = [c.strip() for c in _PIPE.split(line.strip())]
    return parts[1:-1] if parts[-1] == "" else parts[1:]


def _is_separator(line: str) -> bool:
    text = line.strip()
    return text.startswith("|") and "-" in text and set(text) <= set("|:- ")


def qualifying_rows(text: str) -> list:
    """[{id, status, cells}] across the qualifying tables of a Markdown file, in file order: a table whose header's first cell is `#` and which
    has a `Status` column. Nothing else in the file is read."""
    lines = text.split("\n")
    rows, i = [], 0
    while i < len(lines):
        if lines[i].lstrip().startswith("|") and i + 1 < len(lines) and _is_separator(lines[i + 1]):
            head = cells(lines[i])
            j = i + 2
            while j < len(lines) and lines[j].lstrip().startswith("|"):
                if head[:1] == ["#"] and "Status" in head:
                    r = cells(lines[j])
                    k = head.index("Status")
                    rows.append({"id": r[0] if r else "", "status": r[k] if k < len(r) else "", "cells": r})
                j += 1
            i = j
        else:
            i += 1
    return rows


def clause_label(clause: str) -> str:
    """`D1(b)` -> `D1`. The parenthesised letter is not checked against the record."""
    return clause.split("(", 1)[0]


def has_clause(body: str, label: str) -> bool:
    """True when a decision's body carries the label as a bold run (`**D<n>` then a space, a full stop or an opening parenthesis, so `D1` does
    not match `**D10`) or as a heading (`#`s, a space, `D<n>`)."""
    return bool(re.search(rf"\*\*{label}(?=[ .(])", body) or re.search(rf"(?m)^#+ {label}(?![0-9])", body))
