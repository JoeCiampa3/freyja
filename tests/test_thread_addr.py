"""
Thread T2: addresses. Canonical JSON and the 12-hex hash, JSON pointers, the grammar, prefix overlap, and resolution for each source kind
(snapshot, a thread record, a req. id, a tracked JSON or YAML file, a generated thread output) including the empty pointer and the
banner-key exclusion.

    python -m pytest tests/test_thread_addr.py
"""
import hashlib
import json

import pytest
import yaml
from thread_help import make_root, edit_record  # noqa: F401  (also puts tools/ on sys.path)

from thread import addr, build


def test_canonical_json_is_sorted_compact_and_keeps_non_ascii():
    assert addr.canonical({"b": 1, "a": [1, "é"]}) == '{"a":[1,"é"],"b":1}'


def test_hash_is_twelve_hex_of_the_canonical_json():
    v = {"b": 1, "a": "x"}
    assert addr.hash_value(v) == hashlib.sha256(b'{"a":"x","b":1}').hexdigest()[:12]
    assert len(addr.hash_value(None)) == 12 and addr.hash_value("10") != addr.hash_value(10)


@pytest.mark.parametrize("text, source, pointer", [
    ("snapshot#/upper_arm_right_mass", "snapshot", "/upper_arm_right_mass"),
    ("part.hip.m2#/housed_in", "part.hip.m2", "/housed_in"),
    ("thread/derived/seg.thigh.json#/houses", "thread/derived/seg.thigh.json", "/houses"),
    ("seg.thigh#", "seg.thigh", ""),
])
def test_parse(text, source, pointer):
    assert addr.parse(text) == (source, pointer)


@pytest.mark.parametrize("bad", ["snapshot", "#/x", "a b#/x", "snapshot#x", ""])
def test_parse_rejects_a_malformed_address(bad):
    with pytest.raises(ValueError):
        addr.parse(bad)


def test_pointer_get_follows_rfc6901_escapes_and_list_indices():
    doc = {"a/b": {"c~d": [10, {"e": 5}]}, "": 1}
    assert addr.pointer_get(doc, "") == (True, doc)
    assert addr.pointer_get(doc, "/a~1b/c~0d/1/e") == (True, 5)
    assert addr.pointer_get(doc, "/a~1b/c~0d/0") == (True, 10)
    assert addr.pointer_get(doc, "/") == (True, 1)
    for bad in ("/nope", "/a~1b/c~0d/2", "/a~1b/c~0d/x", "/a~1b/c~0d/01", "/a~1b/c~0d/-"):
        assert addr.pointer_get(doc, bad)[0] is False


@pytest.mark.parametrize("a, b, expected", [
    ("snapshot#/x", "snapshot#/x", True),
    ("snapshot#", "snapshot#/x", True),
    ("snapshot#/x/y", "snapshot#/x", True),
    ("snapshot#/x", "snapshot#/xy", False),
    ("snapshot#/x", "part.a.b#/x", False),
    ("part.a.b#/mass", "part.a.b#/mass/kg", True),
])
def test_overlap_is_prefix_on_whole_pointer_segments(a, b, expected):
    assert addr.overlaps(a, b) is expected and addr.overlaps(b, a) is expected


def test_strip_banner_removes_only_the_top_level_banner_keys():
    assert addr.strip_banner({"generated_by": "x", "inputs": "y", "k": {"inputs": 1}}) == {"k": {"inputs": 1}}
    assert addr.strip_banner([1]) == [1]


# ---- resolution against a root

@pytest.fixture
def built(tmp_path):
    root = make_root(tmp_path / "r")
    (root / "requirements").mkdir()
    (root / "requirements" / "req.knee.rom.yaml").write_text(yaml.safe_dump({"id": "req.knee.rom", "value": 140, "unit": "deg"}), encoding="utf-8")
    (root / "data").mkdir()
    (root / "data" / "t.json").write_text(json.dumps({"generated_by": "x", "inputs": "y", "a": {"b": [1, 2]}}), encoding="utf-8")
    (root / "data" / "t.yaml").write_text("k: [1, 2]\nwhen: 2026-01-02\n", encoding="utf-8")
    return build.build_root(root)


def test_snapshot_values_are_the_strings_as_written(built):
    assert built.resolve("snapshot#/pelvis_mass") == (True, "10")
    assert built.resolve("snapshot#/pelvis_length") == (True, "0.2")
    ok, whole = built.resolve("snapshot#")
    assert ok and whole["pelvis_mass"] == "10" and len(whole) == 12
    assert built.resolve("snapshot#/nope")[0] is False


def test_record_addresses_resolve_into_the_authored_record(built):
    assert built.resolve("part.base.p1#/housed_in") == (True, "seg.thigh")
    assert built.resolve("part.base.p1#/mass/kg") == (True, 1.5)
    ok, whole = built.resolve("part.base.p1#")
    assert ok and whole["category"] == "actuator"
    assert built.resolve("part.base.nope#/housed_in")[0] is False
    assert built.resolve("part.base.p1#/nope")[0] is False


def test_req_addresses_resolve_into_requirements(built):
    assert built.resolve("req.knee.rom#/value") == (True, 140)
    assert built.resolve("req.knee.missing#/value")[0] is False


def test_tracked_files_resolve_and_banner_keys_are_excluded(built):
    assert built.resolve("data/t.json#/a/b/1") == (True, 2)
    assert built.resolve("data/t.json#/generated_by")[0] is False
    ok, whole = built.resolve("data/t.json#")
    assert ok and set(whole) == {"a"}
    assert built.resolve("data/t.yaml#/k/0") == (True, 1)
    assert built.resolve("data/t.yaml#/when") == (True, "2026-01-02")
    assert built.resolve("data/missing.json#/a")[0] is False
    assert built.resolve("../outside.json#/a")[0] is False


def test_thread_outputs_resolve_against_the_in_memory_build_not_the_disk(built, tmp_path):
    root = built.root
    stale = root / "thread" / "derived"
    stale.mkdir(parents=True)
    (stale / "seg.thigh.json").write_text(json.dumps({"houses": ["on-disk-only"]}), encoding="utf-8")
    ok, houses = built.resolve("thread/derived/seg.thigh.json#/houses")
    assert ok and houses == ["part.base.p1"]
    assert built.resolve("thread/derived/seg.thigh.json#/generated_by")[0] is False  # banner keys are excluded
    ok, graph_nodes = built.resolve("thread/graph.json#/nodes/0/id")
    assert ok and graph_nodes.startswith(("hn.", "jnt.", "part.", "seg.", "work."))


def test_the_hash_of_an_address_follows_the_value(built):
    h = built.address_hash("snapshot#/pelvis_mass")
    assert h == addr.hash_value("10")
    assert built.address_hash("snapshot#/nope") is None
