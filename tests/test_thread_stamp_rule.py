"""
Thread sources T3: the refusal in `build.write_stamp`, what `fy thread stamp` and `fy thread why` print, the dossier's Evidence section and the
Unsourced load cases section of STATUS.md. The CAD path is in tests/test_cad_ops.py; the whole table is tests/test_thread_sources.py.

    python -m pytest tests/test_thread_stamp_rule.py
"""
import json
import re

import pytest
from test_thread_evidence import adr, case, root_with, row, work
from thread_help import write_record

from thread import build, cli


def snapshot(root):
    return {p.relative_to(root).as_posix(): p.read_bytes() for p in sorted(root.rglob("*")) if p.is_file()}


def run(root, *args):
    lines = []
    code = cli.main([*args, "--root", str(root)], say=lines.append)
    return code, "\n".join(lines)


def dossier(root, id):
    return build.build_root(root).outputs[f"thread/dossiers/{id}.md"].decode()


def status(root):
    return build.build_root(root).outputs["thread/STATUS.md"].decode()


def test_active_work_on_an_unsourced_case_is_refused_and_nothing_is_written(tmp_path):
    root = root_with(tmp_path)
    case(root)
    work(root, status="active")
    before = snapshot(root)
    with pytest.raises(ValueError) as e:
        build.write_stamp(root, build.build_root(root), "work.w", by="t")
    assert "work.w" in str(e.value) and "lc.x" in str(e.value) and "no evidence" in str(e.value)
    assert snapshot(root) == before


def test_the_refusal_gives_each_entry_with_why_it_does_not_count(tmp_path):
    root = root_with(tmp_path, "proposed")
    case(root, ev=[row("X2"), adr()])
    work(root, status="active")
    with pytest.raises(ValueError) as e:
        build.write_stamp(root, build.build_root(root), "work.w", by="t")
    text = str(e.value)
    assert "Status Unverified" in text and "adr-0901 is proposed, not accepted" in text and "no evidence" not in text


def test_the_refusal_names_every_unsourced_case_and_no_other(tmp_path):
    root = root_with(tmp_path)
    case(root, "lc.a")
    case(root, "lc.b", ev=[row("X2")])
    case(root, "lc.good", ev=[adr()])
    work(root, status="active", consumes=("lc.a#/source", "lc.b#/source", "lc.good#/source"))
    with pytest.raises(ValueError) as e:
        build.write_stamp(root, build.build_root(root), "work.w", by="t")
    assert "lc.a" in str(e.value) and "lc.b" in str(e.value) and "lc.good" not in str(e.value)


@pytest.mark.parametrize("status_", ["proposed"])
def test_proposed_work_is_stamped_and_the_cli_prints_the_warning(tmp_path, status_):
    root = root_with(tmp_path)
    case(root)
    work(root, status=status_)
    code, out = run(root, "stamp", "work.w", "--by", "t")
    assert code == 0 and "stamped work.w" in out and "unsourced-consumption" in out and "lc.x" in out
    stamp = next((root / "thread" / "stamps" / "work.w").glob("*.json")).stem
    assert stamp in out  # the warning is from the build after the stamp, so it names the new baseline


def test_the_cli_refuses_with_exit_1_and_prints_the_reason(tmp_path):
    root = root_with(tmp_path)
    case(root)
    work(root, status="active")
    code, out = run(root, "stamp", "work.w", "--by", "t")
    assert code == 1 and "refused" in out and "lc.x" in out and not (root / "thread" / "stamps" / "work.w").exists()


def test_a_stamp_with_no_unsourced_case_prints_no_warning(tmp_path):
    root = root_with(tmp_path)
    case(root, ev=[adr()])
    work(root, status="active")
    code, out = run(root, "stamp", "work.w", "--by", "t")
    assert code == 0 and "unsourced" not in out


def test_the_stamp_warning_names_only_the_stamped_item(tmp_path):
    root = root_with(tmp_path)
    case(root)
    work(root, "work.w")
    work(root, "work.other")
    assert "work.other" not in run(root, "stamp", "work.w", "--by", "t")[1]


def test_why_adds_one_line_per_unsourced_case(tmp_path):
    root = root_with(tmp_path)
    case(root, "lc.a")
    case(root, "lc.b", ev=[row("X2")])
    work(root, consumes=("lc.a#/source", "lc.b#/source"))
    code, out = run(root, "why", "work.w")
    lines = [ln for ln in out.split("\n") if "unsourced" in ln]
    assert code == 0 and len(lines) == 2 and "lc.a" in lines[0] and "no evidence" in lines[0] and "lc.b" in lines[1] and "Status Unverified" in lines[1]
    assert json.loads(run(root, "why", "work.w", "--json")[1])["unsourced"] == ["lc.a", "lc.b"]


def test_why_is_silent_on_sourcing_when_nothing_is_unsourced(tmp_path):
    root = root_with(tmp_path)
    case(root, ev=[adr()])
    work(root)
    assert "unsourced" not in run(root, "why", "work.w")[1]


def test_the_dossier_has_an_evidence_section_after_relations_on_a_load_case_only(tmp_path):
    root = root_with(tmp_path)
    case(root, ev=[{**adr("D1(b)"), "note": "the bound"}, row("X2")])
    t = dossier(root, "lc.x")
    assert t.index("## Relations") < t.index("## Evidence") < t.index("## Budgets")
    section = t.split("## Evidence")[1].split("## Budgets")[0]
    assert "Sourcing: **sourced**" in section
    assert "[adr-0901 D1(b)](../../decisions/0901-x.md)" in section and "admissible" in section and "the bound" in section
    assert "[X2](../../data/falls/sources.md)" in section and "not admissible" in section
    assert "- evidence:" not in t and "- sourcing:" not in t
    assert "## Evidence" not in dossier(root, "seg.pelvis")


def test_every_evidence_link_resolves(tmp_path):
    root = root_with(tmp_path)
    (root / "bench").mkdir()
    (root / "bench" / "drop.json").write_text("{}", encoding="utf-8")
    case(root, ev=[adr(), row("X1"), {"kind": "test", "path": "bench/drop.json"}])
    t = dossier(root, "lc.x").split("## Evidence")[1].split("## Budgets")[0]
    targets = re.findall(r"\]\(([^)]+)\)", t)
    assert len(targets) == 3
    for target in targets:
        assert ((root / "thread" / "dossiers") / target).resolve().is_file(), target


def test_a_case_with_no_evidence_says_so(tmp_path):
    root = root_with(tmp_path)
    case(root)
    section = dossier(root, "lc.x").split("## Evidence")[1].split("## Budgets")[0]
    assert "Sourcing: **unsourced**" in section and "No evidence attached." in section


def test_the_segment_dossier_lists_its_fall_cases(tmp_path):
    root = root_with(tmp_path)
    write_record(root, id="lc.fall", kind="load_case", zone_in="seg.pelvis", independent_source_required=True,
                 source={"zone": "hip", "direction": "lateral", "energy_j": 540, "energy_basis": "E_max"})
    assert "- fall_cases: [lc.fall](lc.fall.md)" in dossier(root, "seg.pelvis")
    assert "- zone_in: [seg.pelvis](seg.pelvis.md)" in dossier(root, "lc.fall")


def test_status_lists_unsourced_cases_with_consumers_after_budgets(tmp_path):
    root = root_with(tmp_path)
    case(root)
    case(root, "lc.ok", ev=[adr()])
    work(root, status="active")
    t = status(root)
    assert t.index("## Budgets") < t.index("## Unsourced load cases") < t.index("## Proposed records")
    section = t.split("## Unsourced load cases")[1].split("## Proposed records")[0]
    assert "lc.x" in section and "work.w (active, unstamped)" in section and "lc.ok" not in section


def test_status_says_none_when_nothing_is_unsourced_and_when_a_case_has_no_consumer(tmp_path):
    root = root_with(tmp_path)
    assert "None." in status(root).split("## Unsourced load cases")[1].split("## Proposed records")[0]
    case(root)
    section = status(root).split("## Unsourced load cases")[1].split("## Proposed records")[0]
    assert "lc.x" in section and "no consumers" in section
