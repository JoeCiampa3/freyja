"""
Thread T5: rendering. Every dossier has its eight sections in order, for every kind; every relative link in every dossier resolves; the
Mermaid neighbourhood is capped at 25 nodes and falls back to a list; references come from files only (never git history); banners and
determinism.

    python -m pytest tests/test_thread_render.py
"""
import json
import re
from pathlib import Path

import pytest
from thread_help import FIXTURES, make_root, write_record

from thread import build, fixture, render

SECTIONS = ["## Binding and values", "## Relations", "## Budgets", "## Work", "## Decisions", "## References", "## Neighbourhood"]


@pytest.fixture(scope="module")
def fx(tmp_path_factory):
    out = tmp_path_factory.mktemp("rfx") / "root"
    fixture.generate(out, 0)
    (out / "docs" / "memos").mkdir(parents=True)
    (out / "docs" / "memos" / "memo1.md").write_text("# memo\n\nThe thigh is `seg.thigh`.\nNot seg.thigh2 and not xseg.thigh.\nSee part.hip.m2, then seg.thigh.\n", encoding="utf-8")
    (out / "notebook").mkdir()
    (out / "notebook" / "n.md").write_text("seg.thigh again\n", encoding="utf-8")
    (out / "log").mkdir()
    (out / "log" / "events.log").write_text("2026 seg.thigh event\n", encoding="utf-8")
    (out / "roadmap" / "nodes").mkdir(parents=True)
    (out / "roadmap" / "nodes" / "rm.x.md").write_text("---\nid: rm.x\n---\nneeds seg.thigh\n", encoding="utf-8")
    return build.build_root(out)


def text(b, path):
    return b.outputs[path].decode()


def test_every_dossier_has_the_sections_in_order_for_every_kind(fx):
    kinds = set()
    for id, r in fx.recs.items():
        t = text(fx, f"thread/dossiers/{id}.md")
        pos = [t.index(s) for s in SECTIONS]
        assert pos == sorted(pos), id
        assert t.index("# " + id) < pos[0]
        kinds.add(r["kind"])
    assert len(kinds) == 7


def test_header_flags_proposed_and_superseded(fx):
    assert "PROPOSED" in text(fx, "thread/dossiers/part.hip.m1.md") or "PROPOSED" in text(fx, "thread/dossiers/part.hip.m2.md")
    t = text(fx, "thread/dossiers/part.hip.old.md")
    assert "SUPERSEDED by [part.hip.m1](part.hip.m1.md)" in t


def test_binding_and_values_carry_the_sheet_source(fx):
    t = text(fx, "thread/dossiers/seg.thigh.md")
    assert re.search(r"\| `thigh_right_mass` \| 9\.49 \| 'MuJoCo Reference'!B22 \|", t)
    j = text(fx, "thread/dossiers/jnt.hip.md")
    assert "`hip_fe_left`" in j and "| `hip_flexion` |" in j
    assert "Not in the snapshot" in text(fx, "thread/dossiers/jnt.lumbosacral.md")
    assert "No model or snapshot binding." in text(fx, "thread/dossiers/part.hip.m1.md")


def test_relations_budgets_work_and_decisions_sections(fx):
    t = text(fx, "thread/dossiers/seg.thigh.md")
    assert "- houses: " in t and "[part.hip.m2](part.hip.m2.md)" in t
    assert "Mass: target 9.49 kg" in t and "part.hip.m2" in t.split("## Budgets")[1].split("## Work")[0]
    assert "[work.thigh-cad](work.thigh-cad.md): current" in t
    d = text(fx, "thread/dossiers/part.hip.m1.md")
    assert "adr-0001 (accepted)" in d.split("## Decisions")[1]
    w = text(fx, "thread/dossiers/work.hip-fea.md").split("## Work")[1].split("## Decisions")[0]
    assert "**stale**" in w and "moved: `part.hip.m2#/mass`" in w


def test_budget_rows_show_the_arithmetic_of_a_bilateral_claim(fx):
    t = text(fx, "thread/dossiers/seg.pelvis.md")
    assert re.search(r"2 x [0-9.]+ kg, part\.hip\.m1 left and right = ", t)
    assert json.loads(text(fx, "thread/derived/seg.pelvis.json"))["budgets"]["mass"]["claims"][0]["arithmetic"].startswith("2 x ")


def test_the_dossier_lists_roadmap_nodes_only_and_points_at_the_live_command(fx):
    t = text(fx, "thread/dossiers/seg.thigh.md").split("## References")[1].split("## Neighbourhood")[0]
    assert "roadmap/nodes/rm.x.md:4" in t
    for prose in ("docs/memos/memo1.md", "notebook/n.md", "log/events.log"):
        assert prose not in t
    assert "python tools/fy thread refs seg.thigh" in t and "memos, notebook and log" in t
    assert "None in roadmap/nodes/." in text(fx, "thread/dossiers/seg.shank.md").split("## References")[1]


def test_roadmap_mentions_use_whole_tokens_and_are_capped_at_twenty(tmp_path):
    root = make_root(tmp_path / "r")
    d = root / "roadmap" / "nodes"
    d.mkdir(parents=True)
    for i in range(25):
        (d / f"rm.n{i:02d}.md").write_text("see seg.thigh and not seg.thigh2\n", encoding="utf-8")
    t = text(build.build_root(root), "thread/dossiers/seg.thigh.md").split("## References")[1].split("## Neighbourhood")[0]
    assert t.count("`roadmap/nodes/") == 20 and "- and 5 more" in t


def test_changing_prose_files_changes_no_generated_output(fx):
    root = fx.root
    before = dict(fx.outputs)
    files = [root / "notebook" / "n.md", root / "docs" / "memos" / "memo1.md", root / "log" / "events.log"]
    old = [f.read_text(encoding="utf-8") for f in files]
    try:
        for f in files:
            f.write_text("seg.thigh changed, jnt.hip too\n", encoding="utf-8")
        assert build.build_root(root).outputs == before
    finally:
        for f, o in zip(files, old):
            f.write_text(o, encoding="utf-8")


def test_a_changed_roadmap_node_changes_that_dossier_and_the_two_summary_files_only(fx):
    root = fx.root
    before = dict(fx.outputs)
    node = root / "roadmap" / "nodes" / "rm.x.md"
    old = node.read_text(encoding="utf-8")
    try:
        node.write_text(old.replace("needs", "still needs"), encoding="utf-8")
        after = build.build_root(root).outputs
    finally:
        node.write_text(old, encoding="utf-8")
    changed = sorted(p for p in after if after[p] != before.get(p))
    # the derived JSON does not carry references; graph.json and STATUS.md hash every input in their banner
    assert changed == ["thread/STATUS.md", "thread/dossiers/seg.thigh.md", "thread/graph.json"]


def links(t):
    return re.findall(r"\]\(([^)#]+)\)", t)


def test_every_link_in_every_dossier_and_status_resolves(fx):
    n = 0
    for path, data in fx.outputs.items():
        if not path.endswith(".md"):
            continue
        base = Path(path).parent
        for target in links(data.decode()):
            n += 1
            assert (base / target).as_posix() in fx.outputs or Path(target).as_posix() in fx.outputs, (path, target)
    assert n > 100


def test_the_neighbourhood_is_a_mermaid_graph_within_the_cap(fx):
    t = text(fx, "thread/dossiers/seg.thigh.md").split("## Neighbourhood")[1]
    assert "```mermaid" in t and "graph LR" in t and "-->|houses|" in t
    assert t.count('["') <= render.MERMAID_CAP


def _crowded(tmp_path, extra):
    root = make_root(tmp_path / "r")
    for i in range(extra):
        write_record(root, id=f"part.crowd.p{i:02d}", kind="part", housed_in="seg.pelvis", category="x", mass={"kg": 0.01, "source": "t", "reserved": True})
    return build.build_root(root)


def test_the_cap_is_25_nodes_including_the_record_and_above_it_a_list(tmp_path):
    base = _crowded(tmp_path / "a", 0)
    n0 = len(render.neighbourhood(base, "seg.pelvis")[0])
    at = _crowded(tmp_path / "b", render.MERMAID_CAP - n0)
    assert len(render.neighbourhood(at, "seg.pelvis")[0]) == render.MERMAID_CAP
    t = text(at, "thread/dossiers/seg.pelvis.md")
    assert "```mermaid" in t
    over = _crowded(tmp_path / "c", render.MERMAID_CAP - n0 + 1)
    t = text(over, "thread/dossiers/seg.pelvis.md").split("## Neighbourhood")[1]
    assert "```mermaid" not in t and f"{render.MERMAID_CAP + 1} nodes" in t and "- houses: [part.crowd.p00](part.crowd.p00.md)" in t


def test_banners_and_determinism_with_references(fx):
    again = build.build_root(fx.root).outputs
    assert again == fx.outputs
    for path, data in fx.outputs.items():
        first = data.decode().splitlines()[0]
        assert first.startswith("<!-- GENERATED by") or path.endswith(".json"), path
        assert "snapshot sha256:" in data.decode()
        assert b"\r" not in data


def test_dossiers_do_not_depend_on_git_history(fx):
    assert not (fx.root / ".git").exists()
    assert fx.outputs == build.build_root(fx.root).outputs
