"""
Stage 3b T6, without Fusion: every `fy cad` command against a recorded fake of the Fusion-side module. The fake keeps the document's parameters, applies
`set_expressions` (and fails it on demand), and answers the read verbs with recorded or synthetic data; its STL is a box in the ISB frame and its STEP
header carries a different timestamp on every export. The thread is the tiny base root of the thread tests, so the real resolver, work statuses and
stamps are exercised.

    python -m pytest tests/test_cad_ops.py
"""
import copy
import hashlib
import json
import re
import sys
from pathlib import Path

import numpy as np
import pytest
import yaml
from thread_help import make_root, write_record

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "tools"))

from cad import binding as cb  # noqa: E402
from cad import cli, mesh, ops, sidecar  # noqa: E402
from envelope import registry  # noqa: E402

FIX = Path(__file__).resolve().parent / "fixtures" / "cad"
TUBE = json.loads((FIX / "physical_tube.json").read_text(encoding="utf-8"))
PART = "part.base.cad"
DOC = "Fake Doc"
URN = "urn:adsk.wipprod:dm.lineage:fake"


class FakeFusion:
    """The Fusion-side module's verbs over an in-memory document. Lengths are cm like Fusion's."""

    def __init__(self):
        self.name, self.id, self.version = DOC, URN, 3
        self.params = {"in_pelvis_length": ("150 mm", 15.0), "dv_a": ("12 mm", 1.2), "dr_b": ("dv_a * 2", 2.4)}
        self.healthy = True
        self.break_on = None             # an expression that "breaks regeneration"
        self.calls = []
        self.step_counter = 0
        self.local_id = False
        self.dirty = False               # unsaved changes in the document
        self.saves = []                  # the description of every save
        self.save_fails = False
        self.lag = 0                     # doc_info calls before a saved version number shows (Fusion's takes about a second)
        self._pending = None

    def __call__(self, verb, **args):
        self.calls.append((verb, args))
        if args.get("expect_name") not in (None, self.name):
            raise RuntimeError(f"the active document is {self.name!r}, not {args['expect_name']!r}; nothing was done")
        return getattr(self, verb)(**{k: v for k, v in args.items() if k != "expect_name"})

    def doc_info(self):
        if self._pending is not None:
            if self.lag <= 0:
                self.version, self._pending = self._pending, None
            self.lag -= 1
        return {"name": self.name, "id": "C:/Users/someone/cache/x.f3d" if self.local_id else self.id, "version": self.version, "saved": True, "modified": self.dirty,
                "fusion_version": "fake", "length_units": "mm", "parametric": True, "timeline_items": 2}

    def read_params(self):
        return {"parameters": [{"name": n, "expression": e, "value": v, "unit": "mm", "comment": ""} for n, (e, v) in sorted(self.params.items())]}

    def timeline_health(self):
        return {"healthy": self.healthy, "failed_features": [] if self.healthy else ["Extrude1"], "items": []}

    def set_expressions(self, expressions, allowed_prefixes=("in_",), rollback_on_failure=True):
        before = dict(self.params)
        for name, expr in expressions.items():
            if expr == self.break_on:
                self.params = before
                return {"ok": False, "refused": [], "errors": [], "applied": [], "rolled_back": True, "failed_features": ["Extrude1"], "failure_messages": ["boom"],
                        "rollback": {"equal": True, "differing": [], "errors": [], "health": {"healthy": True}}, "health": {"healthy": True, "failed_features": [], "items": []}}
            if self.params[name][0] != expr:
                self.dirty = True
            self.params[name] = (expr, float(expr.split()[0]) / 10)
        return {"ok": True, "refused": [], "errors": [], "applied": sorted(expressions), "rolled_back": False, "failed_features": [], "failure_messages": [],
                "health": {"healthy": True, "failed_features": [], "items": []}}

    def save_document(self, description):
        if self.save_fails:
            return {"saved": False, "version": self.version, "modified": self.dirty}
        self.saves.append(description)
        self._pending = self.version + 1
        if self.lag <= 0:
            self.version, self._pending = self._pending, None
        self.dirty = False
        return {"saved": True, "version": self.version, "modified": False}

    def physical_properties(self, accuracy="veryhigh", body=None):
        return dict(TUBE, accuracy=accuracy)

    def max_curvature_radius(self, body=None):
        return {"max_radius_cm": 1.5, "freeform_faces": 0}

    def export_stl(self, path, surface_deviation_cm, normal_deviation_deg, body=None):
        lo, hi = np.array([-15.0, -300.0, -15.0]), np.array([15.0, 0.0, 15.0])      # the ISB frame: the tube hangs along -y
        v = np.array([[x, y, z] for x in (lo[0], hi[0]) for y in (lo[1], hi[1]) for z in (lo[2], hi[2])], float)
        f = np.array([[0, 2, 1], [1, 2, 3], [4, 5, 6], [5, 7, 6], [0, 1, 4], [1, 5, 4], [2, 6, 3], [3, 6, 7], [0, 4, 2], [2, 4, 6], [1, 3, 5], [3, 7, 5]])
        perm = np.random.default_rng(self.step_counter + 7).permutation(len(v))      # a different vertex order on every export
        mesh.write_canonical_stl(path, v[perm], np.argsort(perm)[f])
        self.stl_args = (surface_deviation_cm, normal_deviation_deg)
        return {"path": path}

    def export_step(self, path):
        self.step_counter += 1
        Path(path).write_bytes((f"ISO-10303-21;\r\nHEADER;\r\nFILE_NAME('x.step','2026-10-27T10:00:{self.step_counter:02d}-05:00',('Joe'),('A'),'F','F','');\r\nENDSEC;\r\n"
                                "DATA;\r\n#1=CARTESIAN_POINT('',(0.,0.,0.));\r\nENDSEC;\r\nEND-ISO-10303-21;\r\n").encode())
        return {"path": path}


@pytest.fixture
def env(tmp_path):
    root = make_root(tmp_path / "r")
    b = {"schema": "cad-binding/1", "part": PART, "revision": "t1", "document": {"name": DOC, "id": URN}, "side": "right", "chord_tolerance_mm": 0.05, "clearance_mm": 1.5,
         "parameters": [{"name": "in_pelvis_length", "class": "in", "address": "snapshot#/pelvis_length", "address_unit": "m", "unit": "mm"},
                        {"name": "dv_a", "class": "dv", "unit": "mm"}, {"name": "dr_b", "class": "dr", "unit": "mm"}]}
    (root / "cad" / "bindings").mkdir(parents=True)
    (root / "cad" / "bindings" / f"{PART}.yaml").write_text(yaml.safe_dump(b), encoding="utf-8")
    write_record(root, id=PART, kind="part", housed_in="seg.thigh", category="structure", sides=["left", "right"],
                 mass={"address": f"cad/sidecars/{PART}.json#/mass_properties/mass_kg", "source": "CAD sidecar"})
    write_record(root, id="work.base-cad", kind="work_item", of=PART, mode="assisted", output=f"cad/sidecars/{PART}.json", consumes=["snapshot#/pelvis_length"])
    fake = FakeFusion()
    lines = []
    ctx = ops.Context(root, cb.thread_resolver(root), fake, lines.append)
    return root, fake, ctx, lines


def edit_pelvis_length(root, value):
    p = root / "params" / "snapshot.csv"
    text = p.read_text(encoding="utf-8")
    p.write_text(re.sub(r"^pelvis_length,[^,]*,", f"pelvis_length,{value},", text, flags=re.M), encoding="utf-8", newline="\n")


# ---- validate --------------------------------------------------------------------------------------------------------------------------

def test_validate_passes_for_a_matching_document(env):
    root, fake, ctx, _ = env
    assert ops.validate(ctx, PART) == []


def test_validate_refuses_a_local_path_id_a_stray_parameter_a_missing_one_and_a_foreign_document(env):
    root, fake, ctx, _ = env
    fake.local_id = True
    assert any("not a urn" in p for p in ops.validate(ctx, PART))
    fake.local_id = False
    fake.params["stray"] = ("1 mm", 0.1)
    assert any("stray" in p and "prefix" in p for p in ops.validate(ctx, PART))
    del fake.params["stray"], fake.params["dv_a"]
    assert any("dv_a" in p and "missing" in p for p in ops.validate(ctx, PART))
    fake.name = "Somebody Else"
    with pytest.raises(RuntimeError, match="nothing was done"):
        ops.validate(ctx, PART)


def test_validate_reports_an_address_that_does_not_resolve(env):
    root, fake, ctx, _ = env
    snap = root / "params" / "snapshot.csv"
    kept = [ln for ln in snap.read_text(encoding="utf-8").splitlines() if not ln.startswith("pelvis_length,")]
    snap.write_text(chr(10).join(kept) + chr(10), encoding="utf-8", newline=chr(10))
    ctx2 = ops.Context(root, cb.thread_resolver(root), fake, ctx.say)
    assert any("does not resolve" in x for x in ops.validate(ctx2, PART))


# ---- push, drift -----------------------------------------------------------------------------------------------------------------------

def test_push_sets_the_inherited_parameter_by_expression_with_a_unit_and_leaves_the_others(env):
    root, fake, ctx, _ = env
    r = ops.push(ctx, PART)
    assert r["ok"] and fake.params["in_pelvis_length"][0] == "200 mm" and fake.params["dv_a"][0] == "12 mm"
    sent = [a for v, a in fake.calls if v == "set_expressions"][-1]
    assert sent["expressions"] == {"in_pelvis_length": "200 mm"} and sent["allowed_prefixes"] == ["in_"] and sent["rollback_on_failure"] is True


def test_drift_is_found_after_a_hand_edit_and_cleared_by_push(env):
    root, fake, ctx, _ = env
    assert [d["name"] for d in ops.drift_of(ctx, PART)] == ["in_pelvis_length"]       # 150 mm in Fusion, 200 mm at the address
    ops.push(ctx, PART)
    assert ops.drift_of(ctx, PART) == []
    fake.params["in_pelvis_length"] = ("210 mm", 21.0)
    assert ops.drift_of(ctx, PART)[0]["fusion_value"] == pytest.approx(210.0)


def test_a_failed_push_reports_the_failure_and_the_command_exits_1(env):
    root, fake, ctx, lines = env
    fake.break_on = "200 mm"
    assert cli.main(["push", PART, "--root", str(root)], context=ctx, say=lines.append) == 1
    assert fake.params["in_pelvis_length"][0] == "150 mm"
    assert any("push failed" in x and "Extrude1" in x and "rolled back True" in x for x in lines)


def test_drift_command_exit_codes(env):
    root, fake, ctx, lines = env
    assert cli.main(["drift", PART, "--root", str(root)], context=ctx, say=lines.append) == 1
    ops.push(ctx, PART)
    assert cli.main(["drift", PART, "--root", str(root)], context=ctx, say=lines.append) == 0


# ---- pull ------------------------------------------------------------------------------------------------------------------------------

def pulled(env):
    root, fake, ctx, _ = env
    ops.push(ctx, PART)
    return ops.pull(ctx, PART), root, fake, ctx


def test_pull_writes_a_valid_sidecar_with_every_section(env):
    doc, root, fake, ctx = pulled(env)
    assert sidecar.problems(doc) == []
    assert json.loads((root / "cad" / "sidecars" / f"{PART}.json").read_text(encoding="utf-8")) == doc
    assert doc["identity"] == {"part": PART, "revision": "t1", "side": "right", "binding_sha256": cb.binding_hash(cb.load(root / "cad" / "bindings" / f"{PART}.yaml"))}
    assert doc["document"] == {"name": DOC, "id": URN, "version": 4, "unsaved_changes": False}      # the push saved version 4
    assert [p["name"] for p in doc["parameters"]] == ["dr_b", "dv_a", "in_pelvis_length"]
    assert next(p for p in doc["parameters"] if p["name"] == "in_pelvis_length")["value"] == pytest.approx(200.0)
    assert doc["drift"] == [] and doc["timeline"] == {"healthy": True, "failed_features": []}
    assert doc["mass_properties"]["mass_kg"] == pytest.approx(TUBE["mass_kg"]) and doc["mass_properties"]["com_mm"][2] == pytest.approx(-150.0)
    assert doc["consumes"] == [{"address": "snapshot#/pelvis_length", "hash": next(p for p in doc["parameters"] if p["name"] == "in_pelvis_length")["address_hash"]}]


def test_the_stl_is_in_the_model_frame_and_the_component_is_a_box_around_it(env):
    doc, root, fake, ctx = pulled(env)
    v, f = registry.read_stl(root / "cad" / "exports" / f"{PART}.stl")
    assert np.allclose(v.min(0), (-15, -15, -300)) and np.allclose(v.max(0), (15, 15, 0))      # ISB (x, -300, z) became model (x, z-ish, -300)
    assert doc["exports"]["stl"]["sha256"] == mesh.hash_stl_file(root / "cad" / "exports" / f"{PART}.stl") and doc["exports"]["stl"]["triangles"] == 12
    c = doc["component"]
    assert c["primitive"] == {"type": "box", "half": [15.0, 15.0, 150.0], "offset": [0.0, 0.0, -150.0]} and c["clearance_mm"] == 1.5
    assert c["owner"] == "thigh_R" and c["id"] == PART and c["sha256"] == doc["exports"]["stl"]["sha256"]


def test_the_chord_tolerance_becomes_a_normal_deviation_and_the_bound_is_recorded(env):
    doc, root, fake, ctx = pulled(env)
    stl = doc["exports"]["stl"]
    assert stl["chord_tolerance_mm"] == 0.05 and stl["normal_deviation_deg"] == pytest.approx(9.3590, abs=1e-3)
    assert stl["chord_bound_mm"] == pytest.approx(15.0 * (1 - np.cos(np.radians(stl["normal_deviation_deg"]) / 2)), rel=1e-9) and stl["chord_bound_mm"] <= 0.05 + 1e-9
    assert stl["chord_guarantee"] is True
    assert fake.stl_args == (pytest.approx(0.005), pytest.approx(stl["normal_deviation_deg"]))


def test_a_freeform_face_clears_the_chord_guarantee(env, monkeypatch):
    root, fake, ctx, _ = env
    monkeypatch.setattr(fake, "max_curvature_radius", lambda body=None: {"max_radius_cm": 1.5, "freeform_faces": 4})
    ops.push(ctx, PART)
    assert ops.pull(ctx, PART)["exports"]["stl"]["chord_guarantee"] is False


def test_no_analytic_arc_means_the_default_deviation_and_a_zero_bound(env, monkeypatch):
    root, fake, ctx, _ = env
    monkeypatch.setattr(fake, "max_curvature_radius", lambda body=None: {"max_radius_cm": None, "freeform_faces": 0})
    ops.push(ctx, PART)
    stl = ops.pull(ctx, PART)["exports"]["stl"]
    assert stl["normal_deviation_deg"] == mesh.MAX_NORMAL_DEG and stl["chord_bound_mm"] == 0.0 and stl["chord_guarantee"] is True


def test_two_pulls_with_no_change_give_byte_identical_sidecar_stl_and_step_hash_g5(env):
    doc, root, fake, ctx = pulled(env)
    first = {n: (root / "cad" / n).read_bytes() for n in (f"sidecars/{PART}.json", f"exports/{PART}.stl")}
    step_hash = doc["exports"]["step"]["sha256"]
    comp1 = (root / "data" / "envelope" / "components" / "cad" / "thigh_R.yaml").read_bytes()
    doc2 = ops.pull(ctx, PART)
    assert {n: (root / "cad" / n).read_bytes() for n in first} == first
    assert doc2["exports"]["step"]["sha256"] == step_hash and fake.step_counter == 2        # the STEP differs by timestamp and still hashes the same
    assert (root / "data" / "envelope" / "components" / "cad" / "thigh_R.yaml").read_bytes() == comp1


def test_the_sidecar_and_exports_carry_no_timestamp_or_absolute_path(env):
    doc, root, fake, ctx = pulled(env)
    text = (root / "cad" / "sidecars" / f"{PART}.json").read_text(encoding="utf-8")
    assert not re.search(r"\d{4}-\d{2}-\d{2}T|[A-Za-z]:[/\\]|/Users/", text)
    assert "\r" not in text


def test_the_generated_component_registry_is_banner_sorted_and_loads(env):
    doc, root, fake, ctx = pulled(env)
    p = root / "data" / "envelope" / "components" / "cad" / "thigh_R.yaml"
    text = p.read_text(encoding="utf-8")
    assert text.startswith("# GENERATED by tools/cad pull") and "Do not edit" in text and "\r" not in text
    entry = yaml.safe_load(text)["components"][0]
    assert entry["id"] == PART and entry["revision"] == "t1" and entry["sha256"] == doc["component"]["sha256"] and entry["parameter_inputs"] == doc["component"]["parameter_inputs"]
    assert (p.parent / entry["mesh"]).resolve() == (root / "cad" / "exports" / f"{PART}.stl").resolve()


def test_pull_refuses_an_unhealthy_timeline_and_writes_nothing(env):
    root, fake, ctx, _ = env
    fake.healthy = False
    with pytest.raises(ops.Refused, match="Extrude1"):
        ops.pull(ctx, PART)
    assert not (root / "cad" / "sidecars").exists() and not (root / "cad" / "exports").exists()


def test_pull_refuses_a_local_path_id_and_a_parameter_problem(env):
    root, fake, ctx, _ = env
    fake.local_id = True
    with pytest.raises(ops.Refused, match="not a urn"):
        ops.pull(ctx, PART)
    fake.local_id = False
    fake.params["stray"] = ("1 mm", 0.1)
    with pytest.raises(ops.Refused, match="stray"):
        ops.pull(ctx, PART)


def test_a_pull_with_drift_records_it(env):
    root, fake, ctx, _ = env           # no push: Fusion holds 150 mm, the address says 200 mm
    doc = ops.pull(ctx, PART)
    assert [d["name"] for d in doc["drift"]] == ["in_pelvis_length"]


def test_the_segment_comes_from_the_part_record_or_the_option(env):
    root, fake, ctx, _ = env
    assert ops.segment_of(root, PART) == "thigh_R"
    (root / "thread" / "records" / f"{PART}.yaml").unlink()
    with pytest.raises(ops.Refused, match="no thread record"):
        ops.pull(ctx, PART)
    ops.push(ctx, PART)
    assert ops.pull(ctx, PART, segment="shank_R")["component"]["owner"] == "shank_R"


# ---- the thread: mass address, stamp, status -------------------------------------------------------------------------------------------

def test_the_budget_reads_the_pulled_mass_through_the_address_g5(env):
    from thread import build
    doc, root, fake, ctx = pulled(env)
    b = build.build_root(root)
    claim = next(c for c in b.budgets["segments"]["seg.thigh"]["claims"] if c["part"] == PART)
    assert claim["kg"] == round(doc["mass_properties"]["mass_kg"], 6) and claim["address"].endswith("#/mass_properties/mass_kg")
    assert "address-unresolved" not in [i.code for i in b.warnings if PART in i.ids]


def test_stamp_refuses_without_a_sidecar_with_drift_and_with_stale_hashes_and_stamps_when_clean(env):
    root, fake, ctx, _ = env
    with pytest.raises(ops.Refused, match="no sidecar"):
        ops.stamp(ctx, PART)
    ops.pull(ctx, PART)                                            # drifted pull: Fusion still at 150 mm
    with pytest.raises(ops.Refused, match="drift"):
        ops.stamp(ctx, PART)
    ops.push(ctx, PART)
    ops.pull(ctx, PART)
    edit_pelvis_length(root, 0.25)                                 # the address moves after the pull
    ctx2 = ops.Context(root, cb.thread_resolver(root), fake, ctx.say)
    with pytest.raises(ops.Refused, match="pull again"):
        ops.stamp(ctx2, PART)
    ops.push(ctx2, PART)
    ops.pull(ctx2, PART)
    path = ops.stamp(ctx2, PART, note="gate", by="test")
    stamp = json.loads(path.read_text(encoding="utf-8"))
    assert stamp["work"] == "work.base-cad" and stamp["note"] == "gate" and stamp["pinned"] is False
    assert [c["address"] for c in stamp["consumes"]] == ["snapshot#/pelvis_length"]


def test_stamp_refuses_an_unhealthy_sidecar_timeline(env):
    root, fake, ctx, _ = env
    ops.push(ctx, PART)
    doc = ops.pull(ctx, PART)
    p = root / "cad" / "sidecars" / f"{PART}.json"
    bad = copy.deepcopy(doc)
    bad["timeline"] = {"healthy": False, "failed_features": ["Extrude1"]}
    p.write_text(json.dumps(bad, indent=2, sort_keys=True), encoding="utf-8")
    with pytest.raises(ops.Refused, match="Extrude1"):
        ops.stamp(ctx, PART)


def test_work_status_follows_the_stamp_and_an_edited_input_g6(env):
    from thread import build
    root, fake, ctx, _ = env
    ops.push(ctx, PART)
    ops.pull(ctx, PART)
    assert build.build_root(root).work["work.base-cad"]["status"] == "unstamped"
    ops.stamp(ctx, PART, by="test")
    assert build.build_root(root).work["work.base-cad"]["status"] == "current"
    edit_pelvis_length(root, 0.3)
    assert build.build_root(root).work["work.base-cad"]["status"] == "stale"
    edit_pelvis_length(root, 0.2)
    assert build.build_root(root).work["work.base-cad"]["status"] == "current"


def test_status_prints_one_line_per_binding(env):
    root, fake, ctx, lines = env
    assert "never pulled" in ops.status(ctx)[0]
    ops.push(ctx, PART)
    ops.pull(ctx, PART)
    from thread import build
    build.write_outputs(root, build.build_root(root))
    (line,) = ops.status(ctx)
    assert line.startswith(f"{PART}  rev t1  doc v4  drift none  timeline healthy  work ")


def test_the_command_line_runs_validate_and_pull_and_status(env):
    root, fake, ctx, lines = env
    assert cli.main(["validate", "--root", str(root)], context=ctx, say=lines.append) == 0
    assert cli.main(["push", PART, "--root", str(root)], context=ctx, say=lines.append) == 0
    assert cli.main(["pull", PART, "--root", str(root)], context=ctx, say=lines.append) == 0
    assert cli.main(["drift", PART, "--root", str(root)], context=ctx, say=lines.append) == 0
    assert cli.main(["status", "--root", str(root)], context=ctx, say=lines.append) == 0
    assert any("pulled doc v4" in x and "chord bound" in x for x in lines)
    fake.local_id = True
    assert cli.main(["validate", "--root", str(root)], context=ctx, say=lines.append) == 1
    assert cli.main(["pull", "no.such.part", "--root", str(root)], context=ctx, say=lines.append) == 1


# ---- push saves a clean document, never one with unsaved changes (memo 41, decision 2) ----------------------------------------------------

def test_a_push_to_a_clean_document_saves_it_with_a_description_naming_the_addresses_and_pull_records_that_version(env):
    root, fake, ctx, _ = env
    r = ops.push(ctx, PART)
    assert r["ok"] and r["unsaved_before"] is False and r["saved"] is True and r["version"] == 4
    (desc,) = fake.saves
    assert "snapshot#/pelvis_length" in desc and "in_pelvis_length" in desc and "200 mm" in desc
    assert [v for v, _ in fake.calls].count("save_document") == 1
    doc = ops.pull(ctx, PART)
    assert doc["document"]["version"] == 4 and doc["document"]["unsaved_changes"] is False and sidecar.problems(doc) == []


def test_the_version_number_that_lags_behind_the_save_is_waited_for(env, monkeypatch):
    root, fake, ctx, _ = env
    monkeypatch.setattr(ops, "VERSION_POLL_S", 0.0)
    fake.lag = 3
    r = ops.push(ctx, PART)
    assert r["saved"] is True and r["version"] == 4 and fake.version == 4
    assert ops.pull(ctx, PART)["document"]["version"] == 4


def test_a_version_that_never_shows_is_reported_not_guessed(env, monkeypatch):
    root, fake, ctx, _ = env
    monkeypatch.setattr(ops, "VERSION_POLL_S", 0.0)
    monkeypatch.setattr(ops, "VERSION_WAIT_S", 0.0)
    fake.lag = 10 ** 6
    r = ops.push(ctx, PART)
    assert r["saved"] is True and r["version"] is None and "not confirmed" in r["save_note"]


def test_a_push_to_a_document_with_unsaved_changes_sets_the_parameters_and_does_not_save(env):
    root, fake, ctx, _ = env
    fake.dirty = True
    r = ops.push(ctx, PART)
    assert r["ok"] and r["unsaved_before"] is True and r["saved"] is False and "unsaved" in r["save_skipped"]
    assert fake.params["in_pelvis_length"][0] == "200 mm" and fake.saves == [] and fake.version == 3
    assert "save_document" not in [v for v, _ in fake.calls]
    doc = ops.pull(ctx, PART)
    assert doc["document"] == {"name": DOC, "id": URN, "version": 3, "unsaved_changes": True}


def test_a_push_that_changes_nothing_in_a_clean_document_saves_nothing(env):
    root, fake, ctx, _ = env
    ops.push(ctx, PART)
    fake.saves.clear()
    r = ops.push(ctx, PART)                                       # same expression: Fusion reports no modification
    assert r["ok"] and r["saved"] is False and fake.saves == [] and fake.version == 4 and "nothing changed" in r["save_skipped"]


def test_a_failed_push_saves_nothing(env):
    root, fake, ctx, _ = env
    fake.break_on = "200 mm"
    r = ops.push(ctx, PART)
    assert not r["ok"] and r["saved"] is False and fake.saves == [] and fake.version == 3


def test_a_save_that_fails_is_reported_and_the_pull_then_records_the_unsaved_state(env):
    root, fake, ctx, lines = env
    fake.save_fails = True
    r = ops.push(ctx, PART)
    assert r["ok"] and r["saved"] is False and "save failed" in r["save_skipped"]
    assert ops.pull(ctx, PART)["document"]["unsaved_changes"] is True


def test_stamp_refuses_a_sidecar_pulled_with_unsaved_changes(env):
    root, fake, ctx, _ = env
    fake.dirty = True
    ops.push(ctx, PART)
    ops.pull(ctx, PART)
    with pytest.raises(ops.Refused, match="unsaved changes"):
        ops.stamp(ctx, PART)
    fake.dirty = False                                            # Joe saves, then pulls again
    ops.pull(ctx, PART)
    assert ops.stamp(ctx, PART, by="test").is_file()


def test_the_command_line_says_whether_the_push_saved_and_status_flags_an_unsaved_pull(env):
    root, fake, ctx, lines = env
    assert cli.main(["push", PART, "--root", str(root)], context=ctx, say=lines.append) == 0
    assert any("saved as version 4" in x for x in lines)
    fake.dirty = True
    fake.params["in_pelvis_length"] = ("1 mm", 0.1)
    lines.clear()
    assert cli.main(["push", PART, "--root", str(root)], context=ctx, say=lines.append) == 0
    assert any("not saved" in x and "unsaved" in x for x in lines)
    cli.main(["pull", PART, "--root", str(root)], context=ctx, say=lines.append)
    assert any("UNSAVED" in x for x in lines)
    (line,) = ops.status(ctx)
    assert "UNSAVED" in line
