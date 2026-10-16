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
    """The text of numbered section n (`## n. Title`), up to the next numbered heading; a record template's own `## Context` headings do not end it."""
    return re.search(rf"^## {n}\. .*?(?=^## \d+\. |\Z)", TEXT, re.MULTILINE | re.DOTALL).group(0)


def test_section_3_defines_the_ariadne_and_architecture_tracks():
    terms = next(p for p in section(3).split("\n\n") if p.startswith("**Track terms.**"))
    assert "**Ariadne**" in terms and "digital thread" in terms and "sheet" in terms and "Stages 2, 3" in terms
    assert "**Architecture**" in terms and "roadmap" in terms and "repo tooling" in terms


def test_section_2_describes_tests_as_pytest_modules_as_section_7_does():
    """T5b(f): the old row called tests/ bench-run records; section 7 says the suites live there and pytest.ini collects it."""
    rows = {m.group(1): m.group(0) for m in re.finditer(r"^\| (`[^|]+`) \|.*$", section(2), re.MULTILINE)}
    tests_row = next(r for k, r in rows.items() if k == "`tests/`")
    assert "pytest" in tests_row and "fixtures" in tests_row and "bench" not in tests_row
    assert "tests/" in section(7) and "pytest.ini" in section(7)
    fea_row = next(r for k, r in rows.items() if k == "`fea/`")
    assert "tests/" not in fea_row
