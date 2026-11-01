"""
Thread sources T2: evidence on a load case. Resolution, admissibility and sourcing, read from the cited source and never typed in the record;
`zone_in` and `fall_cases`; and the `unsourced-consumption` warning. The error classes are in tests/test_thread_validate.py.

    python -m pytest tests/test_thread_evidence.py
"""
from pathlib import Path

import pytest
from thread_help import edit_record, make_root, write_record

from thread import build, edges, evidence

ACCEPTED = "---\nid: adr-0901\nstatus: {status}\ndate: 2026-01-01\nlinks: []\n---\n## Decision\n\n**D1 One.** Text. **D10 Ten.**\n\n## D3 As a heading\n\nBody.\n"
TABLE = "| # | Region | Status |\n|---|---|---|\n| X1 | Hip | Verified |\n| X2 | Hand | Unverified (abstract) |\n| X3 | Head | Verified (figure only) |\n| X4 | Foot | Verified\\[12\\] |\n"


def root_with(tmp_path, status="accepted"):
    root = make_root(tmp_path / "r")
    d = root / "decisions" / "0901-x.md"
    d.parent.mkdir(exist_ok=True)
    d.write_text(ACCEPTED.format(status=status), encoding="utf-8")
    f = root / "data" / "falls" / "sources.md"
    f.parent.mkdir(parents=True)
    f.write_text("Prose | with a pipe.\n\n" + TABLE, encoding="utf-8")
    return root


def case(root, id="lc.x", flag=True, ev=None, **f):
    fields = dict(id=id, kind="load_case", source={"scenario": "fall_impact"}, independent_source_required=flag, **f)
    if ev is not None:
        fields["evidence"] = ev
    write_record(root, **fields)


def adr(clause="D1", record="adr-0901"):
    return {"kind": "decision", "record": record, "clause": clause}


def row(id="X1", file="data/falls/sources.md"):
    return {"kind": "literature", "file": file, "row": id}


def graded(root, id="lc.x"):
    b = build.build_root(root)
    assert b.errors == [], [(i.code, i.message) for i in b.errors]
    return b.docs[id]


# ---- the Markdown readers ----------------------------------------------------------------


def test_cells_split_on_unescaped_pipes_only():
    assert evidence.cells(r"| a \| b | c |") == [r"a \| b", "c"]


def test_only_a_table_headed_hash_with_a_status_column_qualifies():
    text = ("| Region | Status |\n|---|---|\n| X9 | Verified |\n\n| # | Region |\n|---|---|\n| X8 | Hip |\n\n" + TABLE + "\n| # | Status |\nnot a separator\n| X7 | Verified |\n")
    assert [r["id"] for r in evidence.qualifying_rows(text)] == ["X1", "X2", "X3", "X4"]


def test_rows_are_read_across_every_qualifying_table():
    assert [r["id"] for r in evidence.qualifying_rows(TABLE + "\nprose\n\n| # | Status |\n|---|---|\n| Y1 | Verified |\n")] == ["X1", "X2", "X3", "X4", "Y1"]


@pytest.mark.parametrize("label, found", [("D1", True), ("D10", True), ("D3", True), ("D2", False), ("D30", False)])
def test_a_clause_label_is_a_bold_run_or_a_heading(label, found):
    assert evidence.has_clause("**D1 One.** Text. **D10 Ten.**\n\n## D3 As a heading\n", label) is found


@pytest.mark.parametrize("text", ["**D1.** x", "**D1 x", "**D1(a) x"])
def test_a_bold_label_ends_at_a_space_a_stop_or_a_parenthesis(text):
    assert evidence.has_clause(text, "D1")


def test_d1_does_not_match_d10():
    assert not evidence.has_clause("**D10 Ten.**\n\n# D10 Ten\n", "D1")


def test_a_heading_needs_its_space_and_a_line_start():
    assert not evidence.has_clause("##D3\n\ntext # D3\n", "D3")


def test_the_admitted_test_schema_list_is_empty():
    assert evidence.ADMITTED_TEST_SCHEMAS == ()


# ---- grading ------------------------------------------------------------------------------


@pytest.mark.parametrize("ev, want", [
    ([], "unsourced"), (None, "unsourced"), ([adr()], "sourced"), ([adr("D3")], "sourced"), ([adr("D1(b)")], "sourced"),
    ([row("X1")], "sourced"), ([row("X3")], "sourced"), ([row("X4")], "sourced"), ([row("X2")], "unsourced"), ([row("X2"), adr()], "sourced"),
])
def test_sourcing_of_a_flagged_case(tmp_path, ev, want):
    root = root_with(tmp_path)
    case(root, ev=ev)
    assert graded(root)["sourcing"] == want


@pytest.mark.parametrize("ev", [None, [row("X1")], [row("X2")]])
def test_an_unflagged_case_is_not_required_and_its_evidence_is_still_shown(tmp_path, ev):
    root = root_with(tmp_path)
    case(root, flag=False, ev=ev)
    d = graded(root)
    assert d["sourcing"] == "not_required" and len(d["evidence"]) == len(ev or [])


@pytest.mark.parametrize("status", ["proposed", '"superseded-by: adr-0902"'])
def test_a_decision_that_is_not_accepted_is_not_admissible(tmp_path, status):
    root = root_with(tmp_path, status)
    case(root, ev=[adr()])
    d = graded(root)
    assert d["sourcing"] == "unsourced" and d["evidence"][0]["resolved"] is True and d["evidence"][0]["admissible"] is False
    assert "adr-0901" in d["evidence"][0]["reason"] and "accepted" in d["evidence"][0]["reason"]


def test_a_test_record_resolves_and_is_never_admissible_yet(tmp_path):
    root = root_with(tmp_path)
    (root / "bench").mkdir()
    (root / "bench" / "drop.json").write_text('{"schema": "run-summary/1"}', encoding="utf-8")
    case(root, ev=[{"kind": "test", "path": "bench/drop.json"}])
    d = graded(root)
    assert d["sourcing"] == "unsourced" and d["evidence"][0]["resolved"] is True and d["evidence"][0]["admissible"] is False


def test_adding_a_schema_to_the_list_is_what_admits_a_test_record(tmp_path, monkeypatch):
    root = root_with(tmp_path)
    (root / "bench").mkdir()
    (root / "bench" / "drop.json").write_text('{"schema": "thread-stamp/1"}', encoding="utf-8")
    case(root, ev=[{"kind": "test", "path": "bench/drop.json"}])
    monkeypatch.setattr(evidence, "ADMITTED_TEST_SCHEMAS", ("thread-graph-1.schema.json",))
    assert graded(root)["sourcing"] == "unsourced"  # the file does not validate against the admitted schema


def test_each_entry_in_the_derived_document_has_its_three_fields_and_keeps_its_note(tmp_path):
    root = root_with(tmp_path)
    case(root, ev=[{**row("X2"), "note": "cross-check"}])
    [e] = graded(root)["evidence"]
    assert e == {**row("X2"), "note": "cross-check", "resolved": True, "admissible": False, "reason": e["reason"]}
    assert "Unverified" in e["reason"] and "\n" not in e["reason"]


@pytest.mark.parametrize("path", ["../outside.md", "/abs.md", "data\\falls\\sources.md", "data/falls/sources.txt"])
def test_a_literature_path_that_is_not_a_repo_relative_md_file_does_not_resolve(tmp_path, path):
    root = root_with(tmp_path)
    (root / "data" / "falls" / "sources.txt").write_text(TABLE, encoding="utf-8")
    (root.parent / "outside.md").write_text(TABLE, encoding="utf-8")
    case(root, ev=[row("X1", path)])
    assert [i.code for i in build.build_root(root).errors] == ["evidence-unresolved"]


@pytest.mark.parametrize("name, text", [("bad.json", "{not json"), ("bad.yaml", "a: [1"), ("bad.txt", "{}")])
def test_a_test_path_that_does_not_parse_does_not_resolve(tmp_path, name, text):
    root = root_with(tmp_path)
    (root / "bench").mkdir()
    (root / "bench" / name).write_text(text, encoding="utf-8")
    case(root, ev=[{"kind": "test", "path": f"bench/{name}"}])
    assert [i.code for i in build.build_root(root).errors] == ["evidence-unresolved"]


# ---- what a case's banner depends on ------------------------------------------------------


def banner(b, id="lc.x"):
    return b.input_hashes[f"thread/derived/{id}.json"]


def test_a_decisions_status_moves_the_cases_banner_and_its_sourcing(tmp_path):
    root = root_with(tmp_path)
    case(root, ev=[adr()])
    before = build.build_root(root)
    p = root / "decisions" / "0901-x.md"
    p.write_text(p.read_text(encoding="utf-8").replace("status: accepted", "status: proposed"), encoding="utf-8")
    after = build.build_root(root)
    assert banner(before) != banner(after) and after.docs["lc.x"]["sourcing"] == "unsourced"


def test_a_rows_cells_move_the_cases_banner_and_an_uncited_row_does_not(tmp_path):
    root = root_with(tmp_path)
    case(root, ev=[row("X1")])
    p = root / "data" / "falls" / "sources.md"
    first = build.build_root(root)
    p.write_text(p.read_text(encoding="utf-8").replace("| X3 | Head |", "| X3 | Skull |"), encoding="utf-8")
    assert banner(build.build_root(root)) == banner(first)
    p.write_text(p.read_text(encoding="utf-8").replace("| X1 | Hip |", "| X1 | Pelvis |"), encoding="utf-8")
    assert banner(build.build_root(root)) != banner(first)
    p.write_text(p.read_text(encoding="utf-8").replace("| X1 | Pelvis | Verified |", "| X1 | Pelvis | Unverified |"), encoding="utf-8")
    assert build.build_root(root).docs["lc.x"]["sourcing"] == "unsourced"


def test_impact_of_a_cited_file_finds_the_cases_outputs(tmp_path):
    from thread import impact, store
    root = root_with(tmp_path)
    case(root, ev=[row("X1"), adr()])
    outs = impact.impact(store.load(root), "data/falls/sources.md#")["outputs"]
    assert "thread/derived/lc.x.json" in outs and "thread/dossiers/lc.x.md" in outs


# ---- zone_in ------------------------------------------------------------------------------


def energy(root, id="lc.fall", zone_in="seg.pelvis"):
    write_record(root, id=id, kind="load_case", zone_in=zone_in, independent_source_required=True,
                 source={"zone": "hip", "direction": "lateral, hip first", "energy_j": 540, "energy_basis": "E_max"})


def test_zone_in_derives_fall_cases_on_the_segment_and_only_there(tmp_path):
    root = root_with(tmp_path)
    energy(root)
    b = build.build_root(root)
    assert b.errors == [] and b.docs["seg.pelvis"]["fall_cases"] == ["lc.fall"] and b.docs["seg.thigh"]["fall_cases"] == []


def test_both_edges_are_in_the_registry_and_the_graph(tmp_path):
    root = root_with(tmp_path)
    energy(root)
    g = build.build_root(root).graph_final
    assert edges.BY_NAME["zone_in"].from_kinds == ("load_case",) and edges.BY_NAME["zone_in"].to_kinds == ("segment",) and edges.BY_NAME["zone_in"].origin == "authored"
    assert edges.BY_NAME["fall_cases"].from_kinds == ("segment",) and edges.BY_NAME["fall_cases"].to_kinds == ("load_case",) and edges.BY_NAME["fall_cases"].origin == "derived"
    assert {"type": "zone_in", "from": "lc.fall", "to": "seg.pelvis"} in g["edges"] and {"type": "fall_cases", "from": "seg.pelvis", "to": "lc.fall"} in g["edges"]


def test_a_fall_cases_energy_is_consumable_as_an_address(tmp_path):
    root = root_with(tmp_path)
    energy(root)
    assert build.build_root(root).resolve("lc.fall#/source/energy_j") == (True, 540)


# ---- unsourced-consumption ----------------------------------------------------------------


def work(root, id="work.w", status="proposed", consumes=("lc.x#/source",)):
    write_record(root, id=id, kind="work_item", status=status, of="seg.pelvis", mode="assisted", consumes=list(consumes))


def warnings(b):
    return [i for i in b.warnings if i.code == "unsourced-consumption"]


@pytest.mark.parametrize("status", ["proposed", "active"])
def test_a_live_consumer_of_an_unsourced_case_warns_naming_item_status_and_case(tmp_path, status):
    root = root_with(tmp_path)
    case(root)
    work(root, status=status)
    [w] = warnings(build.build_root(root))
    assert w.ids == ("work.w", "lc.x") and "work.w" in w.message and status in w.message and "lc.x" in w.message


def test_a_superseded_consumer_does_not_warn(tmp_path):
    root = root_with(tmp_path)
    case(root)
    write_record(root, id="work.new", kind="work_item", of="seg.pelvis", mode="assisted", consumes=[])
    write_record(root, id="work.w", kind="work_item", status="superseded", superseded_by="work.new", of="seg.pelvis", mode="assisted", consumes=["lc.x#/source"])
    assert warnings(build.build_root(root)) == []


def test_the_warning_names_the_baseline_stamp_and_every_unsourced_case_and_no_other(tmp_path):
    root = root_with(tmp_path)
    case(root, "lc.a")
    case(root, "lc.b")
    case(root, "lc.ok", ev=[adr()])
    work(root, consumes=("lc.a#/source", "lc.b#/source", "lc.ok#/source"))
    build.write_stamp(root, build.build_root(root), "work.w", stamp="20261001-1000", by="t")
    [w] = warnings(build.build_root(root))
    assert "20261001-1000" in w.message and "lc.a" in w.message and "lc.b" in w.message and "lc.ok" not in w.message and w.ids == ("work.w", "lc.a", "lc.b")


def test_an_address_into_the_derived_file_counts_as_consuming_the_case(tmp_path):
    root = root_with(tmp_path)
    case(root)
    work(root, consumes=("thread/derived/lc.x.json#/sourcing",))
    assert [w.ids for w in warnings(build.build_root(root))] == [("work.w", "lc.x")]


@pytest.mark.parametrize("ev, flag", [([adr()], True), (None, False)])
def test_a_consumer_of_a_sourced_or_unflagged_case_draws_nothing(tmp_path, ev, flag):
    root = root_with(tmp_path)
    case(root, flag=flag, ev=ev)
    work(root)
    assert warnings(build.build_root(root)) == []


def test_sourcing_does_not_touch_the_work_status(tmp_path):
    root = root_with(tmp_path)
    case(root, ev=[adr()])
    work(root)
    build.write_stamp(root, build.build_root(root), "work.w", stamp="20261001-1000", by="t")
    edit_record(root, "lc.x", evidence=[])
    b = build.build_root(root)
    assert b.work["work.w"]["status"] == "current" and len(warnings(b)) == 1


def test_the_real_cases_are_unflagged_and_not_required():
    b = build.build_root(Path(__file__).resolve().parents[1])
    cases = [d for d in b.docs.values() if d["kind"] == "load_case"]
    assert cases and {d["sourcing"] for d in cases} == {"not_required"} and warnings(b) == []
