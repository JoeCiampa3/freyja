"""
Thread T2: bindings, inverse relations, budgets, work status, impact and the in-memory what-if, on the hand-written base root.

    python -m pytest tests/test_thread_derive.py
"""
import json

import pytest
from thread_help import edit_record, edit_snapshot, make_root, write_record

from thread import addr, build, impact, store


@pytest.fixture
def root(tmp_path):
    return make_root(tmp_path / "r")


def docs(root):
    b = build.build_root(root)
    assert b.errors == [], [(i.code, i.ids, i.message) for i in b.errors]
    return b


# ---- bindings and values

def test_a_bilateral_segment_binds_both_sides_and_reads_values_from_the_right(root):
    d = docs(root).docs["seg.thigh"]
    assert d["bound_bodies"] == ["thigh_left", "thigh_right"]
    assert d["values"] == {"thigh_right_mass": {"value": "5", "sheet_source": "'T'!A12"}}
    assert docs(root).docs["seg.pelvis"]["values"] == {"pelvis_length": {"value": "0.2", "sheet_source": "'T'!A6"},
                                                        "pelvis_mass": {"value": "10", "sheet_source": "'T'!A7"}}


def test_a_joint_binds_hinges_of_both_sides_and_derives_parent_and_child_segments(root):
    d = docs(root).docs["jnt.hip"]
    assert d["bound_hinges"] == ["hip_fe_left", "hip_fe_right"]
    assert d["parent_segments"] == ["seg.pelvis"] and d["child_segments"] == ["seg.thigh"]
    assert d["rom"] == {"hip_extension": {"value": "20", "sheet_source": "'T'!A2"}, "hip_flexion": {"value": "120", "sheet_source": "'T'!A3"}}
    k = docs(root).docs["jnt.knee"]
    assert k["parent_segments"] == ["seg.thigh"] and k["child_segments"] == ["seg.shank"]


def test_a_rom_key_the_sheet_lacks_is_listed_as_missing_not_invented(root):
    edit_record(root, "jnt.lumbosacral", rom_keys=["lumbosacral_flexion"])
    d = docs(root).docs["jnt.lumbosacral"]
    assert d["rom"] == {} and d["rom_missing"] == ["lumbosacral_flexion"]


def test_the_root_free_joint_is_not_a_joint_record(root):
    d = docs(root)
    assert not [i for i in d.warnings if i.code == "unbound-hinge"]


# ---- inverse relations

def test_inverse_relations_are_derived_from_the_owner(root):
    b = docs(root)
    assert b.docs["seg.thigh"]["houses"] == ["part.base.p1"]
    assert b.docs["seg.pelvis"]["houses"] == ["part.base.p2"]
    assert b.docs["seg.pelvis"]["reacted_by"] == ["part.base.p1"]
    assert b.docs["jnt.hip"]["acted_on_by"] == ["part.base.p1"]
    assert b.docs["seg.shank"]["crossed_by"] == ["hn.base"] and b.docs["seg.abdomen"]["crossed_by"] == []
    assert b.docs["seg.pelvis"]["consumed_by"] == []
    assert b.docs["part.base.p2"]["consumed_by"] == ["work.base"]
    assert b.docs["seg.pelvis"]["joints_as_parent"] == ["jnt.hip", "jnt.lumbosacral"]
    assert b.docs["seg.thigh"]["joints_as_child"] == ["jnt.hip"]


def test_inverse_relations_are_never_authored(root):
    assert "houses" not in (root / "thread" / "records" / "seg.thigh.yaml").read_text(encoding="utf-8")
    write_record(root, id="seg.pelvis", kind="segment", body="pelvis", houses=["part.base.p2"])
    assert any(i.code == "schema" for i in build.build_root(root).errors)


def test_interfaces_touching_a_record_and_decisions_linking_it(root):
    write_record(root, id="if.p1-thigh", kind="interface", between=["part.base.p1", "seg.thigh"], carries_cut_of="jnt.hip",
                 mechanical={"status": "open"}, electrical={"status": "open"}, thermal={"status": "defined", "notes": "ok"})
    b = docs(root)
    assert b.docs["part.base.p1"]["interfaces"] == ["if.p1-thigh"]
    assert b.docs["seg.thigh"]["interfaces"] == ["if.p1-thigh"]
    assert b.docs["jnt.hip"]["interfaces"] == ["if.p1-thigh"]  # carries the cut of this joint
    assert b.docs["part.base.p1"]["decisions"] == [{"id": "adr-0001", "status": "accepted"}]
    assert b.docs["seg.thigh"]["decisions"] == []


# ---- budgets

def test_mass_budget_per_segment_and_for_the_whole_body(root):
    b = docs(root)
    m = b.docs["seg.thigh"]["budgets"]["mass"]
    assert (m["target_kg"], m["claimed_kg"], m["remaining_kg"], m["over"]) == (5.0, 1.5, 3.5, False)
    assert m["claims"] == [{"part": "part.base.p1", "kg": 1.5, "count": 1}]
    p = b.docs["seg.pelvis"]["budgets"]["mass"]
    assert (p["target_kg"], p["claimed_kg"], p["over"]) == (10.0, 2.0, False)
    body = json.loads(b.outputs["thread/graph.json"])["budgets"]["mass"]["body"]
    assert body["target_kg"] == 30.0 and body["claimed_kg"] == 5.0 and body["over"] is False  # 2 x 1.5 on the thighs + 2.0


def test_a_bilateral_part_in_a_unilateral_segment_claims_each_side(root):
    edit_record(root, "part.base.p1", housed_in="seg.pelvis")
    p = docs(root).docs["seg.pelvis"]["budgets"]["mass"]
    assert p["claimed_kg"] == 5.0
    assert {c["part"]: c["count"] for c in p["claims"]} == {"part.base.p1": 2, "part.base.p2": 1}


def test_superseded_parts_claim_nothing_and_proposed_parts_claim(root):
    write_record(root, id="part.base.old", kind="part", housed_in="seg.pelvis", category="x", status="superseded",
                 superseded_by="part.base.p2", mass={"kg": 50, "source": "t", "reserved": False})
    b = docs(root)
    assert b.docs["seg.pelvis"]["budgets"]["mass"]["claimed_kg"] == 2.0
    assert "part.base.old" in b.docs["seg.pelvis"]["houses"]  # housing is a relation; the claim is what is budgeted


def test_over_claim_warns_budget_over_and_a_segment_without_a_target_has_no_verdict(root):
    edit_record(root, "part.base.p2", mass={"kg": 11, "source": "t", "reserved": True})
    b = docs(root)
    assert b.docs["seg.pelvis"]["budgets"]["mass"]["over"] is True
    assert [(i.code, i.ids) for i in b.warnings] == [("budget-over", ("seg.pelvis",))]
    (root / "params" / "snapshot.csv").write_text((root / "params" / "snapshot.csv").read_text(encoding="utf-8").replace("target_mass", "xtarget"),
                                                   encoding="utf-8")
    body = json.loads(docs(root).outputs["thread/graph.json"])["budgets"]["mass"]["body"]
    assert body["target_kg"] is None and body["over"] is False


# ---- work status

def stamp(root, work="work.base", **kw):
    b = build.build_root(root)
    return build.write_stamp(root, b, work, by="test", **kw)


def status(root, work="work.base"):
    b = build.build_root(root)
    assert b.errors == [], [(i.code, i.ids, i.message) for i in b.errors]
    return b.work[work]


def test_unstamped_is_normal_and_does_not_warn(root):
    w = status(root)
    assert w["status"] == "unstamped" and w["moved"] == []
    assert build.build_root(root).warnings == []


def test_stamp_makes_the_item_current_and_records_values(root):
    path = stamp(root, stamp="20261001-1000")
    assert path == root / "thread" / "stamps" / "work.base" / "20261001-1000.json"
    doc = json.loads(path.read_text(encoding="utf-8"))
    assert doc["consumes"] == [{"address": "snapshot#/pelvis_mass", "hash": addr.hash_value("10"), "value": "10"},
                               {"address": "part.base.p2#/housed_in", "hash": addr.hash_value("seg.pelvis"), "value": "seg.pelvis"}]
    assert doc["pinned"] is False and doc["by"] == "test" and doc["stamp"] == "20261001-1000"
    assert status(root)["status"] == "current"


def test_a_changed_value_makes_it_stale_with_both_values(root):
    stamp(root, stamp="20261001-1000")
    edit_snapshot(root, "pelvis_mass", 11)
    w = status(root)
    assert w["status"] == "stale"
    assert w["moved"] == [{"address": "snapshot#/pelvis_mass", "stamped": "10", "current": "11", "stamped_hash": addr.hash_value("10"),
                           "current_hash": addr.hash_value("11")}]


def test_a_pinned_baseline_turns_the_difference_into_drifted(root):
    stamp(root, stamp="20261001-1000", pinned=True)
    assert status(root)["status"] == "current"
    edit_record(root, "part.base.p2", housed_in="seg.abdomen")
    w = status(root)
    assert w["status"] == "drifted" and w["pinned"] is True
    assert [m["address"] for m in w["moved"]] == ["part.base.p2#/housed_in"]


def test_an_address_that_no_longer_resolves_is_unknown(root):
    stamp(root, stamp="20261001-1000")
    edit_snapshot(root, "pelvis_mass", 11)  # also moved, but unknown wins
    (root / "params" / "snapshot.csv").write_text(
        "\n".join(ln for ln in (root / "params" / "snapshot.csv").read_text(encoding="utf-8").splitlines() if not ln.startswith("pelvis_mass")) + "\n",
        encoding="utf-8")
    b = build.build_root(root)
    assert b.work["work.base"]["status"] == "unknown"
    assert {m["address"]: m["current"] for m in b.work["work.base"]["moved"]}["snapshot#/pelvis_mass"] is None
    assert ("address-unresolved", ("work.base",)) in [(i.code, tuple(i.ids)) for i in b.warnings]


def test_the_newest_stamp_by_name_is_the_baseline(root):
    stamp(root, stamp="20261001-1000")
    edit_snapshot(root, "pelvis_mass", 11)
    assert status(root)["status"] == "stale"
    stamp(root, stamp="20261002-0900")
    assert status(root)["status"] == "current"
    stamp(root, stamp="20260901-0900")  # older by name: not the baseline
    assert status(root)["status"] == "current"


def test_status_follows_the_stamped_addresses_not_the_current_consumes_list(root):
    stamp(root, stamp="20261001-1000")
    edit_record(root, "work.base", consumes=["snapshot#/pelvis_mass"])
    edit_record(root, "part.base.p2", housed_in="seg.abdomen")  # was stamped, no longer listed
    b = build.build_root(root)
    assert b.work["work.base"]["status"] == "stale"
    assert ("consumes-changed", ("work.base",)) in [(i.code, tuple(i.ids)) for i in b.warnings]


def test_a_large_value_is_stored_as_null_beside_its_hash(root):
    (root / "data").mkdir()
    big = {"rows": ["x" * 40] * 60}
    (root / "data" / "big.json").write_text(json.dumps(big), encoding="utf-8")
    assert len(addr.canonical(big)) > 2048
    edit_record(root, "work.base", consumes=["data/big.json#/rows", "data/big.json#/rows/0"])
    path = stamp(root, stamp="20261001-1000")
    doc = json.loads(path.read_text(encoding="utf-8"))
    assert doc["consumes"][0]["value"] is None and doc["consumes"][0]["hash"] == addr.hash_value(big["rows"])
    assert doc["consumes"][1]["value"] == "x" * 40


def test_reverified_is_never_computed(root):
    stamp(root, stamp="20261001-1000")
    edit_snapshot(root, "pelvis_mass", 11)
    assert status(root)["status"] != "reverified"


def test_the_rework_queue_lists_stale_drifted_and_unknown_with_diffs(root):
    stamp(root, stamp="20261001-1000")
    edit_snapshot(root, "pelvis_mass", 11)
    text = build.build_root(root).outputs["thread/STATUS.md"].decode()
    assert "work.base" in text and "stale" in text and "snapshot#/pelvis_mass" in text and "10" in text and "11" in text
    current = make_root(root.parent / "r2")
    assert "work.base" not in build.build_root(current).outputs["thread/STATUS.md"].decode().split("## Rework queue")[1].split("##")[0]


# ---- outputs

def test_two_builds_are_byte_identical_and_carry_the_banner(root):
    a, b = build.build_root(root).outputs, build.build_root(root).outputs
    assert a == b
    for path, data in a.items():
        assert b"\r" not in data, path
        text = data.decode()
        assert "GENERATED" in text.splitlines()[0] or path.endswith(".json"), path
        assert "snapshot sha256:" in text, path
    graph = json.loads(a["thread/graph.json"])
    assert graph["generated_by"].startswith("GENERATED by") and graph["inputs"].startswith("sha256:")


def test_the_banner_hash_of_an_untouched_output_survives_an_unrelated_edit(root):
    a = build.build_root(root).outputs
    edit_record(root, "part.base.p2", mass={"kg": 3.0, "source": "t", "reserved": True})
    b = build.build_root(root).outputs
    assert a["thread/derived/seg.shank.json"] == b["thread/derived/seg.shank.json"]
    assert a["thread/dossiers/seg.shank.md"] == b["thread/dossiers/seg.shank.md"]
    assert a["thread/derived/seg.pelvis.json"] != b["thread/derived/seg.pelvis.json"]


def test_the_set_of_outputs_is_one_derived_and_one_dossier_per_record_plus_graph_and_status(root):
    paths = sorted(build.build_root(root).outputs)
    ids = sorted(p.stem for p in (root / "thread" / "records").glob("*.yaml"))
    assert paths == sorted([f"thread/derived/{i}.json" for i in ids] + [f"thread/dossiers/{i}.md" for i in ids] + ["thread/STATUS.md", "thread/graph.json"])


def test_graph_json_carries_the_edge_type_registry_and_work_statuses(root):
    g = json.loads(build.build_root(root).outputs["thread/graph.json"])
    names = {t["name"] for t in g["edge_types"]}
    assert {"housed_in", "houses", "acts_across", "reacts_into", "between", "path", "of", "consumes"} <= names
    assert all(t["doc"] and t["origin"] in ("authored", "derived") for t in g["edge_types"])
    assert {"type": "housed_in", "from": "part.base.p1", "to": "seg.thigh"} in g["edges"]
    assert {"type": "houses", "from": "seg.thigh", "to": "part.base.p1"} in g["edges"]
    assert g["work_statuses"] == {"work.base": "unstamped"}


# ---- impact

def test_impact_lists_work_whose_addresses_overlap_by_pointer_prefix(root):
    s = store.load(root)
    assert impact.impact(s, "part.base.p2#/housed_in")["work"] == ["work.base"]
    assert impact.impact(s, "part.base.p2#")["work"] == ["work.base"]
    assert impact.impact(s, "part.base.p2#/housed_in/x")["work"] == ["work.base"]
    assert impact.impact(s, "part.base.p2#/mass")["work"] == []
    assert impact.impact(s, "snapshot#")["work"] == ["work.base"]
    assert impact.impact(s, "snapshot#/pelvis_mass/x")["work"] == ["work.base"]
    assert impact.impact(s, "snapshot#/pelvis_length")["work"] == []


def test_impact_lists_the_outputs_that_depend_on_the_source(root):
    s = store.load(root)
    out = impact.impact(s, "snapshot#/thigh_right_mass")["outputs"]
    assert "thread/derived/seg.thigh.json" in out and "thread/dossiers/seg.thigh.md" in out
    assert "thread/derived/seg.shank.json" not in out and "thread/dossiers/seg.pelvis.md" not in out
    assert "thread/graph.json" in out and "thread/STATUS.md" in out
    moved = impact.impact(s, "part.base.p1#/housed_in")["outputs"]
    assert {"thread/derived/part.base.p1.json", "thread/derived/seg.thigh.json"} <= set(moved)
    assert "thread/derived/seg.shank.json" not in moved  # impact lists what is built from the value as it stands; --edit shows the destination


def snapshot_of(root):
    return {p.relative_to(root).as_posix(): p.read_bytes() for p in sorted(root.rglob("*")) if p.is_file()}


def test_whatif_reports_the_real_edits_changes_and_writes_nothing(root, tmp_path):
    stamp(root, stamp="20261001-1000")
    before = snapshot_of(root)
    s = store.load(root)
    res = impact.whatif(s, ["part.base.p2#/housed_in=seg.abdomen"])
    assert snapshot_of(root) == before  # the root is untouched
    assert res["errors"] == []
    assert res["status_changes"] == {"work.base": {"from": "current", "to": "stale"}}
    # now make the real edit and compare
    base_out = build.build_root(root).outputs
    edit_record(root, "part.base.p2", housed_in="seg.abdomen")
    real = build.build_root(root)
    changed = sorted(p for p in real.outputs if real.outputs[p] != base_out.get(p))
    assert res["outputs_changed"] == changed
    assert real.work["work.base"]["status"] == "stale"


def test_whatif_applies_several_edits_and_values_are_yaml(root):
    s = store.load(root)
    res = impact.whatif(s, ["part.base.p2#/mass/kg=11", "snapshot#/pelvis_mass=9"])
    assert "thread/derived/seg.pelvis.json" in res["outputs_changed"]
    assert any(w["code"] == "budget-over" for w in res["warnings"])


def test_whatif_rejects_a_malformed_edit_and_an_edit_to_a_missing_source(root):
    s = store.load(root)
    with pytest.raises(ValueError):
        impact.whatif(s, ["part.base.p2#/housed_in"])  # no value
    with pytest.raises(ValueError):
        impact.whatif(s, ["part.base.nope#/housed_in=seg.pelvis"])
    with pytest.raises(ValueError):
        impact.whatif(s, ["thread/derived/seg.thigh.json#/houses=[]"])  # generated outputs are not editable


def test_whatif_reports_errors_the_edit_would_cause(root):
    s = store.load(root)
    res = impact.whatif(s, ["part.base.p2#/housed_in=seg.nowhere"])
    assert [e["code"] for e in res["errors"]] == ["ref-unresolved"]
