"""
Assertions on the text of CONVENTIONS.md that other files depend on (T5b of docs/briefs/architecture/roadmap-brief1.md).

Run from the repo root:
    python -m pytest tests/test_conventions.py
"""
import re
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parents[1]
TEXT = (REPO / "CONVENTIONS.md").read_text(encoding="utf-8")


def section(n: int) -> str:
    return re.split(rf"^## {n}\. ", TEXT, flags=re.MULTILINE)[1].split("\n## ")[0]


def test_section_3_defines_the_ariadne_and_architecture_tracks():
    terms = next(p for p in section(3).split("\n\n") if p.startswith("**Track terms.**"))
    assert "**Ariadne**" in terms and "digital thread" in terms and "sheet" in terms and "Stages 2, 3" in terms
    assert "**Architecture**" in terms and "roadmap" in terms and "repo tooling" in terms
