"""
Roadmap brief 3 T2: the controlled tag vocabulary (roadmap/tags.yaml). Namespaced tags `namespace:value` are checked against it; free tags
(no colon) pass unchecked. An unknown namespace or value is an error naming the node and the tag, a node with two values of one namespace is
a warning, and a missing tags.yaml means no namespaces are defined. The initial vocabulary Joe asked for, its colours (checked against the
constants in analysis/tag_palette.py), the state file's copy of it and the fixture generator's use of it.

Run from the repo root:
    python -m pytest tests/test_roadmap_tags.py
"""
import json
import re
import sys
from pathlib import Path

import jsonschema
import pytest
import yaml
from rmhelp import REPO, leaf, make

import roadmap
from roadmap import fixture, render, tags

sys.path.insert(0, str(REPO / "analysis"))
import tag_palette as pal  # noqa: E402

INVALID = REPO / "tests" / "fixtures" / "roadmap" / "invalid"
REGION = ["head", "neck", "torso", "spine", "pelvis", "arm-l", "arm-r", "hand-l", "hand-r", "leg-l", "leg-r", "foot-l", "foot-r", "whole-body"]
PHASE = ["spec", "sim", "design", "fab", "bench", "integrate"]
VOCAB = {"namespaces": {"region": {"head": "#0072b2", "arm-l": None, "arm-r": "#d55e00"}, "phase": {"spec": "#009e73", "sim": None}}}


def with_vocab(root, vocab=VOCAB):
    (Path(root) / "roadmap").mkdir(parents=True, exist_ok=True)
    (Path(root) / "roadmap" / "tags.yaml").write_text(yaml.safe_dump(vocab, sort_keys=False), encoding="utf-8", newline="\n")
    return root


def tagged(root, nodes_tags, vocab=VOCAB):
    """A root holding rm.root and one leaf per entry of nodes_tags {id: [tags]}, with a vocabulary (None: no tags.yaml)."""
    nodes = {"rm.root": {"title": "Top"}, **{i: leaf("rm.root", tags=t) for i, t in nodes_tags.items()}}
    root = make(root, nodes)
    return with_vocab(root, vocab) if vocab is not None else root


def codes(items):
    return [(x.code, x.ids) for x in items]


# ---- the vocabulary file in this repo

def real():
    return yaml.safe_load((REPO / "roadmap" / "tags.yaml").read_text(encoding="utf-8"))["namespaces"]


def test_the_initial_vocabulary_has_exactly_the_two_namespaces_and_values_the_brief_names():
    v = real()
    assert sorted(v) == ["phase", "region"]
    assert list(v["region"]) == REGION and list(v["phase"]) == PHASE


def test_every_initial_value_has_a_colour_that_works_on_both_themes_and_is_distinct_under_colour_blindness():
    v = real()
    for ns in ("region", "phase"):
        cols = [v[ns][k] for k in v[ns]]
        assert all(isinstance(c, str) and re.fullmatch(r"#[0-9a-f]{6}", c) for c in cols), (ns, cols)
        assert len(set(cols)) == len(cols)
        worst = min(pal.min_contrast(c) for c in cols)
        assert worst >= pal.CONTRAST_MIN, (ns, worst)  # 3:1 on all four backgrounds, so one hex serves light and dark
        sep = pal.min_separation([*cols, pal.NEUTRAL])
        assert sep >= pal.DELTA_E_MIN[ns], (ns, sep)  # normal vision, protanopia, deuteranopia, tritanopia, and against the "no tag" grey


def test_the_palette_arithmetic_matches_known_values():
    """Independent anchors: WCAG contrast of black on white is 21; the CIELAB L of white is 100 and of black 0; a deuteranope cannot tell
    these two apart as well as a normal viewer does."""
    assert abs(pal.contrast("#000000", "#ffffff") - 21) < 1e-9
    assert abs(pal.lab("#ffffff")[0] - 100) < 0.01 and abs(pal.lab("#000000")[0]) < 0.01
    assert pal.delta_e("#d55e00", "#009e73", "deutan") < pal.delta_e("#d55e00", "#009e73", "normal")


def test_the_palette_search_is_deterministic_and_meets_its_contrast_constraint():
    a = pal.search(4, pool=300, rounds=1)
    assert a == pal.search(4, pool=300, rounds=1) and all(pal.min_contrast(c) >= pal.CONTRAST_MIN for c in a)


def test_the_vocabulary_is_registered_in_conventions_as_authored():
    text = (REPO / "CONVENTIONS.md").read_text(encoding="utf-8")
    assert "roadmap/tags.yaml" in text


# ---- validation

def test_a_known_namespaced_tag_and_free_tags_pass(tmp_path):
    rm = roadmap.compute(tagged(tmp_path / "r", {"rm.a": ["region:head", "phase:spec", "actuation", "plain"]}))
    assert rm.errors == [] and rm.warnings == []


def test_free_tags_pass_unchecked_even_without_a_vocabulary(tmp_path):
    rm = roadmap.compute(tagged(tmp_path / "r", {"rm.a": ["arm", "CAD", "v1", "x-y_z"]}, vocab=None))
    assert rm.errors == [] and rm.warnings == []


@pytest.mark.parametrize("tag,code", [
    ("regoin:head", "tag-unknown-namespace"),
    ("region:armm", "tag-unknown-value"),
    ("phase:spec ", "tag-unknown-value"),  # trailing space: the typo that the vocabulary exists to catch
    ("Region:head", "tag-unknown-namespace"),
    ("region:Head", "tag-unknown-value"),
    ("region:", "tag-unknown-value"),
    (":head", "tag-unknown-namespace"),
    ("region:head:left", "tag-unknown-value"),
    ("a:b:c", "tag-unknown-namespace"),
])
def test_a_namespaced_tag_outside_the_vocabulary_is_an_error_naming_the_node_and_the_tag(tmp_path, tag, code):
    rm = roadmap.compute(tagged(tmp_path / "r", {"rm.a": [tag], "rm.b": ["region:head"]}))
    assert codes(rm.errors) == [(code, ("rm.a",))], [e.message for e in rm.errors]
    e = rm.errors[0]
    assert "rm.a" in e.message and repr(tag) in e.message and "roadmap/nodes/rm.a.md" in e.message and e.paths == ("roadmap/nodes/rm.a.md",)


def test_the_message_for_an_unknown_value_lists_the_values_the_namespace_allows(tmp_path):
    rm = roadmap.compute(tagged(tmp_path / "r", {"rm.a": ["region:armm"]}))
    assert "arm-l" in rm.errors[0].message and "arm-r" in rm.errors[0].message and "head" in rm.errors[0].message


def test_a_missing_tags_file_means_no_namespaces_and_any_namespaced_tag_is_an_error(tmp_path):
    rm = roadmap.compute(tagged(tmp_path / "r", {"rm.a": ["region:head", "phase:spec"], "rm.b": ["plain"]}, vocab=None))
    assert codes(rm.errors) == [("tag-unknown-namespace", ("rm.a",)), ("tag-unknown-namespace", ("rm.a",))]
    assert rm.vocabulary == {}


def test_two_values_of_one_namespace_on_a_node_are_a_warning_not_an_error(tmp_path):
    rm = roadmap.compute(tagged(tmp_path / "r", {"rm.a": ["region:head", "region:arm-l", "phase:spec"], "rm.b": ["region:head", "region:head"]}))
    assert rm.errors == []
    assert codes(rm.warnings) == [("tag-duplicate-namespace", ("rm.a",))]  # the same value twice is not two values
    w = rm.warnings[0]
    assert "region" in w.message and "arm-l" in w.message and "head" in w.message and "roadmap/nodes/rm.a.md" in w.message


def test_a_superseded_node_is_checked_too(tmp_path):
    root = tagged(tmp_path / "r", {"rm.a": []})
    from rmhelp import write_node
    write_node(root, "rm.old", title="Old", parent="rm.root", superseded_by="rm.a", tags=["regoin:head"])
    assert codes(roadmap.compute(root).errors) == [("tag-unknown-namespace", ("rm.old",))]


def test_every_bad_tag_on_a_node_is_reported(tmp_path):
    rm = roadmap.compute(tagged(tmp_path / "r", {"rm.a": ["regoin:head", "region:armm", "phase:nope"]}))
    assert sorted(e.code for e in rm.errors) == ["tag-unknown-namespace", "tag-unknown-value", "tag-unknown-value"]


# ---- the file itself

@pytest.mark.parametrize("text", [
    "namespaces: [region]\n",
    "namespaces:\n  region:\n    head: blue\n",
    "namespaces:\n  Region:\n    head: null\n",
    "namespaces:\n  region:\n    Head: null\n",
    "namespaces:\n  region: {}\n",
    "namespaces:\n  region:\n    head: \"#12345\"\n",
    "extra: 1\nnamespaces:\n  region:\n    head: null\n",
    "just text\n",
    "namespaces: [unclosed\n",
    "",
])
def test_a_broken_tags_file_is_one_error_that_names_the_file_and_hides_no_other_problem(tmp_path, text):
    root = tagged(tmp_path / "r", {"rm.a": ["region:head"]}, vocab=None)
    (root / "roadmap" / "tags.yaml").write_text(text, encoding="utf-8", newline="\n")
    rm = roadmap.compute(root)
    assert codes(rm.errors) == [("tags-file", ())], [e.message for e in rm.errors]  # and no cascade of one error per namespaced tag
    assert "roadmap/tags.yaml" in rm.errors[0].message and rm.errors[0].paths == ("roadmap/tags.yaml",)
    assert rm.vocabulary == {}


def test_the_tags_schema_accepts_the_real_file_and_a_null_colour():
    schema = json.loads((REPO / "docs" / "schemas" / "roadmap-tags-1.schema.json").read_text(encoding="utf-8"))
    jsonschema.Draft202012Validator.check_schema(schema)
    v = jsonschema.Draft202012Validator(schema)
    assert list(v.iter_errors(yaml.safe_load((REPO / "roadmap" / "tags.yaml").read_text(encoding="utf-8")))) == []
    assert list(v.iter_errors(VOCAB)) == []


def test_load_vocabulary_returns_namespace_to_value_to_colour(tmp_path):
    vocab, issues = tags.load_vocabulary(with_vocab(tmp_path / "r"))
    assert issues == [] and vocab == {"region": {"head": "#0072b2", "arm-l": None, "arm-r": "#d55e00"}, "phase": {"spec": "#009e73", "sim": None}}
    assert tags.load_vocabulary(tmp_path / "none") == ({}, [])


# the three hand-authored invalid fixtures (tag-unknown-namespace, tag-unknown-value, tags-file-broken) are listed in tests/test_roadmap_validate.py


# ---- the state file

def test_state_carries_the_vocabulary_and_lists_the_file_among_its_inputs(tmp_path):
    root = tagged(tmp_path / "r", {"rm.a": ["region:head"]})
    st = render.state_dict(roadmap.compute(root))
    assert st["tag_vocabulary"] == {ns: [{"value": v, "colour": c} for v, c in vals.items()] for ns, vals in VOCAB["namespaces"].items()} and "roadmap/tags.yaml" in st["inputs"]
    schema = json.loads((REPO / "docs" / "schemas" / "roadmap-state-3.schema.json").read_text(encoding="utf-8"))
    assert list(jsonschema.Draft202012Validator(schema).iter_errors(st)) == []
    assert render.state_dict(roadmap.compute(make(tmp_path / "e", {"rm.root": {"title": "T"}})))["tag_vocabulary"] == {}


def test_changing_the_vocabulary_changes_the_inputs_hash_and_so_the_banner(tmp_path):
    root = tagged(tmp_path / "r", {"rm.a": []})
    h1 = render.inputs_hash(root, roadmap.compute(root))
    with_vocab(root, {"namespaces": {"region": {"head": None}}})
    assert render.inputs_hash(root, roadmap.compute(root)) != h1


# ---- the fixture generator

@pytest.mark.parametrize("seed", [0, 3, 7])
def test_the_fixture_tags_nodes_from_the_vocabulary_without_warnings_it_did_not_intend(tmp_path, seed):
    root = tmp_path / "f"
    fixture.generate(300, root, seed=seed)
    rm = roadmap.compute(root)
    assert rm.errors == [] and not any(w.code == "tag-duplicate-namespace" for w in rm.warnings)
    assert rm.vocabulary == real()  # the fixture ships the real vocabulary, so a fixture shows the real colours
    live = [n for n in rm.nodes.values() if not n.superseded]
    for ns in ("region", "phase"):
        have = [n for n in live if any(t.startswith(ns + ":") for t in n.tags)]
        none = [n for n in live if not any(t.startswith(ns + ":") for t in n.tags)]
        values = {t.split(":", 1)[1] for n in have for t in n.tags if t.startswith(ns + ":")}
        assert 0.3 * len(live) < len(have) < 0.9 * len(live), (ns, len(have))  # some nodes carry none, so the grey fallback is exercised
        assert none and len(values) >= (10 if ns == "region" else 5), (ns, sorted(values))
    assert all(len([t for t in n.tags if t.startswith("region:")]) <= 1 and len([t for t in n.tags if t.startswith("phase:")]) <= 1 for n in live)


def test_the_state_lists_each_namespaces_values_in_the_order_of_the_file_even_though_the_file_is_written_with_sorted_keys(tmp_path):
    """The legend shows them in this order (head before foot), and state.json has sorted keys, so the values are a list rather than an object."""
    root = render.build(tagged(tmp_path / "r", {"rm.a": []})) and tmp_path / "r"
    st = json.loads((root / "roadmap" / "state.json").read_text(encoding="utf-8"))
    assert [e["value"] for e in st["tag_vocabulary"]["region"]] == ["head", "arm-l", "arm-r"]  # not sorted: arm-l would come first
    real_state = render.state_dict(roadmap.compute(REPO))
    assert [e["value"] for e in real_state["tag_vocabulary"]["region"]] == REGION and [e["value"] for e in real_state["tag_vocabulary"]["phase"]] == PHASE
