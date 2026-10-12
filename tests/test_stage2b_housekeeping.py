"""
Stage 2b T5: wording and housekeeping that is a fact about files: the trunk-mode wording has one home and the generators use it,
`pose.com_x_rel_ankle_m` is described as a design choice with its value unchanged, `.gitattributes` fixes line endings, and
CLAUDE.md names the current brief.

Run from the repo root:
    python -m pytest tests/test_stage2b_housekeeping.py
"""
import inspect
import re
import sys
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "sim" / "scripts"))

import gait  # noqa: E402
import runs_report as rp  # noqa: E402


def test_the_trunk_wording_says_what_each_mode_models_and_has_one_home():
    w = gait.TRUNK_WORDING
    assert "`rigid` is a locked spine" in w
    assert "`counter_rotate` is an actuated lumbosacral roll and yaw cancelling the pelvis's roll and yaw by feed-forward" in w
    assert "`first_harmonic` is a human-like reference point from the trunk IMU" in w and "never a record mode" in w
    assert "no mode is the v1 headline" in w
    assert rp.TRUNK_WORDING == w  # runs_report is MuJoCo-free and mirrors it; the equality is the test


def test_the_generators_use_the_wording_where_the_modes_are_first_explained():
    assert "TRUNK_WORDING" in inspect.getsource(gait.render_md)
    assert "TRUNK_WORDING" in inspect.getsource(rp.gait_section)


def test_the_generators_do_not_attribute_b_to_mass_distribution_her_foot_or_the_controller_project():
    """Stage 2b Decisions: B's failure stands as a finding with its cause unattributed. The generators carry no sentence that explains it."""
    for fn in (gait.render_md, rp.gait_section):
        text = inspect.getsource(fn).lower()
        for bad in ("because of freyja's mass", "due to her foot", "the controller project's fault", "her mass distribution explains", "the foot explains"):
            assert bad not in text


def test_the_com_offset_default_is_unchanged_and_described_as_a_design_choice():
    for name in ("hold_pose", "stand_static"):
        path = REPO / "sim" / "scenarios" / f"{name}.yaml"
        text = path.read_text(encoding="utf-8")
        assert yaml.safe_load(text)["pose"] == {"com_x_rel_ankle_m": 0.0}
        head = " ".join(l.lstrip("# ") for l in text.splitlines() if l.startswith("#"))  # comment words, wrapped lines joined
        assert "design choice" in head and "41 mm" in head and "not a measurement" in head, name
        assert "uncited" in head or "no cited" in head, name


def test_gitattributes_fixes_line_endings_to_lf():
    lines = [l.strip() for l in (REPO / ".gitattributes").read_text(encoding="utf-8").splitlines() if l.strip() and not l.startswith("#")]
    assert "* text=auto eol=lf" in lines


def test_claude_md_names_the_current_brief_and_it_exists():
    m = re.search(r"Current brief:\s*`([^`]+)`", (REPO / "CLAUDE.md").read_text(encoding="utf-8"))
    assert m and m.group(1) == "docs/briefs/stage2b-brief.md" and (REPO / m.group(1)).is_file()
