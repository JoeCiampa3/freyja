"""
The upper arm's authored characterization inputs (docs/briefs/ariadne/upper-arm-characterization-brief.md, T5): data/characterization/inputs/upper_arm.yaml
validates against characterization-inputs/1, every case that reaches the segment has a flag, and every value equals the number its cited clause states:
the T5 table of the checkpoint memo is the CLAUSES table below, read from the decision files at test time.

    python -m pytest tests/test_characterization_inputs.py
"""
import json
import re
from pathlib import Path

import jsonschema
import pytest
import yaml

REPO = Path(__file__).resolve().parents[1]
INPUTS = REPO / "data" / "characterization" / "inputs" / "upper_arm.yaml"
SCHEMA = json.loads((REPO / "docs" / "schemas" / "characterization-inputs-1.schema.json").read_text(encoding="utf-8"))
DOC = yaml.safe_load(INPUTS.read_text(encoding="utf-8"))
DECISIONS = {p.name[:4]: p for p in (REPO / "decisions").glob("[0-9][0-9][0-9][0-9]-*.md")}


def clause_text(record: str, clause: str) -> str:
    """The text of clause D<n> of a decision: from its label (`**D<n> ...` or `D<n>. ...` at the start of a line) inside the Decision section
    to the next top-level label. A sub-clause such as D6(f) is looked up in its whole clause D6."""
    n = re.match(r"D(\d+)", clause).group(1)
    body = DECISIONS[record[len("adr-"):]].read_text(encoding="utf-8")
    section = body.split("## Decision", 1)[1].split("\n## ", 1)[0]
    label = re.compile(r"^(?:\*\*D(\d+)[ .*]|D(\d+)\. )", re.M)
    starts = [(m.start(), m.group(1) or m.group(2)) for m in label.finditer(section)]
    for i, (pos, k) in enumerate(starts):
        if k == n:
            end = next((p for p, kk in starts[i + 1:] if kk != n), len(section))
            return section[pos:end]
    raise KeyError(f"{record} has no clause {clause} in its Decision section")


def entry(path: str):
    d = DOC
    for k in path.split("/"):
        d = d[k]
    return d


# entry -> the phrase of the cited clause that states it (quoted as the decision writes it), and the number in that phrase
CLAUSES = {
    "shell": ("default 5 mm", 5),
    "anchor_bars/elbow": ("The elbow node carries an error bar of 7 mm, mostly anteroposterior", 7),
    "anchor_bars/wrist": ("the wrist node 5 mm", 5),
    "anchor_bars/shoulder": ('Shoulder positions are quoted with the bar "unstated", never zero', "unstated"),
    "rom/mechanism_ends/flexion": ("to 157° of flexion", 157),
    "payloads/design": ("Payloads are 1.0 kg design", 1.0),
    "payloads/nominal": ("0.5 kg nominal", 0.5),
    "swing_rows/S1/amplitude": ("S1 gesture, no payload, 90° in 1.0 s", 90),
    "swing_rows/S1/duration": ("S1 gesture, no payload, 90° in 1.0 s", 1.0),
    "swing_rows/S1/payload": ("S1 gesture, no payload", 0),
    "swing_rows/S2/amplitude": ("S2 grasp transport at the design payload, 90° in 2.0 s", 90),
    "swing_rows/S2/duration": ("S2 grasp transport at the design payload, 90° in 2.0 s", 2.0),
    "swing_rows/S2/payload": ("Payloads are 1.0 kg design", 1.0),
    "swing_rows/S3/amplitude": ("Swing S3: 1.0 kg at gesture speed | 90° in 1.0 s", 90),
    "swing_rows/S3/duration": ("Swing S3: 1.0 kg at gesture speed | 90° in 1.0 s", 1.0),
    "swing_rows/S3/payload": ("Swing S3: 1.0 kg at gesture speed", 1.0),
    "bsip_spread": ("The self-weight terms carry about 3%", 3),
    "fall_contact_points/lc.fall-hand-arm/contact": ("0.515 m, the wrist, is the design case", "wrist"),
    "fall_contact_points/lc.fall-hand-arm/rating": ("rated 1.5 × 20 = 30 kN", 30),
    "fall_flags/lc.fall-hand-arm": ("lc.fall-hand-arm is structural (0008 D6f)", "structural"),
    "fall_flags/lc.fall-shoulder-lateral": ("lc.fall-shoulder-lateral is a clearance constraint", "clearance"),
}


def test_the_inputs_validate():
    assert list(jsonschema.Draft202012Validator(SCHEMA).iter_errors(json.loads(json.dumps(DOC)))) == []


def _entries(d=DOC, path=""):
    for k, v in d.items():
        p = f"{path}/{k}" if path else k
        if isinstance(v, dict) and "value" in v and "source" in v:
            yield p, v
        elif isinstance(v, dict):
            yield from _entries(v, p)


def test_every_entry_with_a_value_is_in_the_table_and_the_table_names_only_entries():
    numbered = {p for p, e in _entries() if e["value"] is not None}
    assert numbered == set(CLAUSES)


@pytest.mark.parametrize("path", sorted(CLAUSES))
def test_each_value_equals_the_number_its_clause_states(path):
    phrase, number = CLAUSES[path]
    e = entry(path)
    assert e["value"] == number, (path, e["value"], number)
    texts = [clause_text(c["record"], c["clause"]) for c in e["source"]]
    assert any(phrase in t for t in texts), f"{path}: {phrase!r} is in none of {[(c['record'], c['clause']) for c in e['source']]}"
    if number == 0:
        assert "no payload" in phrase  # the clause states zero in words
        return
    assert re.search(r"(?<![\d.])" + re.escape(f"{number:g}" if isinstance(number, (int, float)) else number) + r"(?![\d])", phrase), (path, phrase)


def test_the_loaded_arc_is_unsourced_as_its_clause_says():
    e = entry("rom/loaded_arc")
    assert e["value"] is None and e["source_needed"] is True
    assert "[source needed" in clause_text("adr-0008", "D2")


def test_every_case_reaching_the_upper_arm_has_a_flag():
    """adr-0045 D5(c): fall_cases together with fall_contacts, read from the thread's fresh build."""
    import sys
    sys.path.insert(0, str(REPO / "tools"))
    from thread import build
    core = build.build_root(REPO).core["seg.upper_arm"]
    reaching = set(core["fall_cases"]) | set(core["fall_contacts"])
    assert reaching == set(DOC["fall_flags"]) == {"lc.fall-hand-arm", "lc.fall-shoulder-lateral"}


def test_nothing_an_address_holds_is_typed():
    """The anatomical range and the mechanism's extension end are the snapshot's; no length, mass or inertia appears."""
    assert set(DOC["rom"]["mechanism_ends"]) == {"flexion"}
    units = {e["unit"] for _, e in _entries()}
    assert units <= {"mm", "deg", "kg", "s", "%", "kN", None}
    assert all(not (e["unit"] == "mm" and isinstance(e["value"], (int, float)) and e["value"] > 10) for _, e in _entries())  # no length typed
