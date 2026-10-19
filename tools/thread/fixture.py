"""
Thread fixture generator: `fy thread fixture --out DIR [--seed N]` writes a repo-shaped root holding copies of the tracked model and
snapshot, a segment record per segment and a joint record per anatomical joint (covering every body and hinge), and synthetic parts,
interfaces, harness runs, load cases, work items, stamps and decision records. Deterministic for a given seed. It also writes
`fixture-intent.json` (the status it meant each work item to have), which a test compares with the derived statuses.

`reallocation(out)` writes the fixture of the Stage 3a acceptance test (T4): hip actuators M1 and M2 and a harness run, with masses chosen
so that moving M2 from the thigh into the pelvis overfills the pelvis budget.

Fixtures are generated into temporary directories and never committed. The generator is deliberately independent of the library's
judgement: the intended status of each work item is decided here, by how its stamp is made (current values, a tampered value, a pinned
baseline, an address that no longer resolves), and only the stamps' hashes use the library's `addr`.
"""
from __future__ import annotations

import json
import random
import shutil
from pathlib import Path

import yaml

from . import addr, build, seed
from . import store as st

REPO = Path(__file__).resolve().parents[2]
STAMP = "20261001-1000"
OLDER_STAMP = "20260901-0900"


def _yaml(path: Path, doc: dict):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(doc, sort_keys=True, allow_unicode=True), encoding="utf-8", newline="\n")


def _json(path: Path, doc):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(doc, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")


def _prepare(out) -> Path:
    out = Path(out)
    if out.exists() and any(out.iterdir()):
        raise ValueError(f"{out} exists and is not empty; the fixture generator never overwrites")
    (out / "sim" / "models").mkdir(parents=True, exist_ok=True)
    (out / "params").mkdir(parents=True, exist_ok=True)
    shutil.copyfile(REPO / st.MODEL_PATH, out / st.MODEL_PATH)
    shutil.copyfile(REPO / st.SNAPSHOT_PATH, out / st.SNAPSHOT_PATH)
    return out


def _structural(out: Path):
    """A segment record per segment and a joint record per joint, as the proposal in seed.py has them."""
    pp = build.pre_processor()
    model = st.Model.parse((out / st.MODEL_PATH).read_bytes())
    rec = out / st.RECORDS_DIR
    for name in seed.SEGMENTS:
        _yaml(rec / f"seg.{name}.yaml", seed.segment_record(name, name in pp.BILATERAL))
    for name in seed.JOINTS:
        _yaml(rec / f"jnt.{name}.yaml", seed.joint_record(name, seed.joint_is_bilateral(name, model.hinges)))


def _record(kind, id, purpose, **f) -> dict:
    return {"schema": "thread-record/1", "id": id, "kind": kind, "status": f.pop("status", "proposed"), "purpose": purpose, **f}


def _part(id, purpose, housed_in, kg, **f) -> dict:
    reserved = f.pop("reserved", False)
    return _record("part", id, purpose, housed_in=housed_in, mass={"kg": kg, "source": "fixture", "reserved": reserved}, category=f.pop("category", "fixture"), **f)


def _decision(out: Path, name: str, id: str, status: str, links: list):
    p = out / "decisions" / name
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(f"---\nid: {id}\nstatus: {status}\ndate: 2026-01-01\nlinks: [{', '.join(links)}]\n---\n## Context\nA fixture decision.\n", encoding="utf-8", newline="\n")


def _stamp(out: Path, work: str, name: str, rows: list, pinned=False, note=""):
    _json(out / st.STAMPS_DIR / work / f"{name}.json", {"schema": "thread-stamp/1", "work": work, "stamp": name, "note": note, "pinned": pinned, "by": "fixture",
                                                        "consumes": [{"address": a, "hash": addr.hash_value(v), "value": v} for a, v in rows]})


def _current_rows(b, work_record: dict, override: dict | None = None) -> list:
    rows = []
    for a in work_record["consumes"]:
        ok, v = b.resolve(a)
        if not ok:
            raise ValueError(f"the fixture's own address {a} does not resolve")
        rows.append((a, (override or {}).get(a, v)))
    return rows


def generate(out, seed_value: int = 0) -> dict:
    """Write the general fixture; returns the intent {work id: status}."""
    rng = random.Random(seed_value)
    out = _prepare(out)
    _structural(out)
    rec = out / st.RECORDS_DIR

    def kg(lo, hi):
        return round(rng.uniform(lo, hi), 3)

    def status():
        return rng.choice(["proposed", "proposed", "active"])

    def iface_state():
        return {"status": rng.choice(["open", "defined"]), "notes": ""}

    both = ["left", "right"]
    parts = [
        _part("part.hip.m1", "Hip drive module in the pelvis.", "seg.pelvis", kg(0.8, 1.6), acts_across="jnt.hip", reacts_into="seg.pelvis", harness=["hn.leg-power"],
              sides=both, category="actuator", status=status()),
        _part("part.hip.m2", "Hip drive module in the thigh.", "seg.thigh", kg(0.8, 1.6), acts_across="jnt.hip", reacts_into="seg.thigh", harness=["hn.leg-power"],
              sides=both, category="actuator", status=status()),
        _part("part.hip.old", "A superseded hip drive.", "seg.pelvis", kg(0.8, 1.6), status="superseded", superseded_by="part.hip.m1", category="actuator"),
        _part("part.knee.drive", "Knee drive in the thigh.", "seg.thigh", kg(0.5, 1.2), acts_across="jnt.knee", reacts_into="seg.thigh", harness=["hn.leg-power"],
              sides=both, category="actuator", status=status()),
        _part("part.ankle.drive", "Ankle drive in the shank.", "seg.shank", kg(0.3, 0.9), acts_across="jnt.ankle", reacts_into="seg.shank", harness=["hn.leg-power"],
              sides=both, category="actuator", status=status()),
        _part("part.foot.loadcell", "Force sensor in the foot.", "seg.foot", kg(0.05, 0.2), sides=both, category="sensor", harness=[], status=status()),
        _part("part.torso.battery", "Main battery in the abdomen.", "seg.abdomen", kg(0.8, 1.6), category="battery", harness=["hn.torso-bus"], status=status()),
        _part("part.torso.computer", "Controller in the thorax.", "seg.thorax", kg(0.3, 0.8), category="electronics", harness=["hn.torso-bus", "hn.arm-signal"],
              reserved=rng.random() < 0.5, status=status()),
        _part("part.arm.elbow", "Elbow drive in the upper arm.", "seg.upper_arm", kg(0.3, 0.9), acts_across="jnt.elbow", reacts_into="seg.upper_arm",
              harness=["hn.arm-signal"], sides=both, category="actuator", status=status()),
        _part("part.head.sensors", "Sensor head.", "seg.head_neck", kg(0.2, 0.6), reserved=True, category="sensor", status=status()),
    ]
    for p in parts:
        _yaml(rec / f"{p['id']}.yaml", p)
    runs = [
        _record("harness_run", "hn.leg-power", "Power to the leg drives.", path=["seg.pelvis", "seg.thigh", "seg.shank"], carries="motor power"),
        _record("harness_run", "hn.arm-signal", "Signal to the arm.", path=["seg.thorax", "seg.upper_arm", "seg.forearm"], carries="signals"),
        _record("harness_run", "hn.torso-bus", "Torso bus.", path=["seg.abdomen", "seg.thorax"], carries="power and signals"),
    ]
    ifaces = [
        _record("interface", "if.hip-m1-pelvis", "Mount of M1 in the pelvis.", between=["part.hip.m1", "seg.pelvis"], carries_cut_of="jnt.hip",
                mechanical=iface_state(), electrical=iface_state(), thermal=iface_state()),
        _record("interface", "if.hip-m2-thigh", "Mount of M2 in the thigh.", between=["part.hip.m2", "seg.thigh"], carries_cut_of="jnt.hip",
                mechanical=iface_state(), electrical=iface_state(), thermal=iface_state()),
        _record("interface", "if.m1-m2", "Coupling of the two hip modules.", between=["part.hip.m1", "part.hip.m2"],
                mechanical=iface_state(), electrical=iface_state(), thermal=iface_state()),
        _record("interface", "if.battery-abdomen", "Battery in the abdomen.", between=["part.torso.battery", "seg.abdomen"],
                mechanical=iface_state(), electrical=iface_state(), thermal=iface_state()),
    ]
    cases = [
        _record("load_case", "lc.stand-static", "Quiet standing.", source={"scenario": "stand_static"}, independent_source_required=False),
        _record("load_case", "lc.walk-1p4", "Level walking at 1.4 m/s.", source={"gait_spec": "walk_treadmill", "condition": "1.4 m/s"}, independent_source_required=False),
        _record("load_case", "lc.fall-impact", "A fall onto the hip.", source={"scenario": "fall_impact"}, independent_source_required=True, notes="Simulation alone may not size from this."),
    ]
    work = {
        "work.pelvis-cad": ("seg.pelvis", "assisted", ["snapshot#/pelvis_mass", "snapshot#/pelvis_length", "thread/derived/seg.pelvis.json#/houses"]),
        "work.thigh-cad": ("seg.thigh", "assisted", ["snapshot#/thigh_right_mass", "thread/derived/seg.thigh.json#/houses"]),
        "work.hip-fea": ("jnt.hip", "assisted", ["snapshot#/hip_flexion", "part.hip.m2#/mass", "thread/derived/jnt.hip.json#/acted_on_by"]),
        "work.ankle-print": ("part.ankle.drive", "manual", ["part.ankle.drive#/mass/kg", "thread/derived/seg.shank.json#/budgets/mass"]),
        "work.battery-bench": ("part.torso.battery", "manual", ["part.torso.battery#/mass", "snapshot#/retired_key"]),
        "work.arm-cad": ("seg.upper_arm", "manual", ["snapshot#/upper_arm_right_mass", "thread/derived/seg.upper_arm.json#/houses"]),
    }
    works = [_record("work_item", w, f"Fixture work on {of}.", of=of, mode=mode, consumes=c, output=f"cad/{w}.step") for w, (of, mode, c) in sorted(work.items())]
    for r in runs + ifaces + cases + works:
        _yaml(rec / f"{r['id']}.yaml", r)
    _decision(out, "0001-hip-drive.md", "adr-0001", "accepted", ["part.hip.m1", "part.hip.m2", "jnt.hip"])
    _decision(out, "0002-battery-location.md", "adr-0002", "proposed", ["part.torso.battery", "seg.abdomen"])
    # stamps: the library resolves the current values; the generator decides how each stamp departs from them
    b = build.build_root(out)
    if b.errors:
        raise ValueError("the fixture's records have errors: " + "; ".join(f"{i.code} {i.message}" for i in b.errors[:3]))
    wr = {r["id"]: r for r in works}
    _stamp(out, "work.thigh-cad", STAMP, _current_rows(b, wr["work.thigh-cad"]), note="current")
    _stamp(out, "work.thigh-cad", OLDER_STAMP, _current_rows(b, wr["work.thigh-cad"], {"snapshot#/thigh_right_mass": "0"}), note="an older stamp is not the baseline")
    _stamp(out, "work.arm-cad", STAMP, _current_rows(b, wr["work.arm-cad"]), note="current")
    _stamp(out, "work.hip-fea", STAMP, _current_rows(b, wr["work.hip-fea"], {"part.hip.m2#/mass": {"kg": 0.1, "reserved": False, "source": "an earlier estimate"}}), note="stale")
    _stamp(out, "work.ankle-print", STAMP, _current_rows(b, wr["work.ankle-print"], {"part.ankle.drive#/mass/kg": 99.0}), pinned=True, note="pinned, then the mass moved")
    rows = _current_rows(b, {"consumes": ["part.torso.battery#/mass"]}) + [("snapshot#/retired_key", "1.0")]
    _stamp(out, "work.battery-bench", STAMP, rows, note="a key since removed from the snapshot")
    intent = {"work.arm-cad": "current", "work.thigh-cad": "current", "work.hip-fea": "stale", "work.ankle-print": "drifted", "work.battery-bench": "unknown",
              "work.pelvis-cad": "unstamped"}
    _json(out / "fixture-intent.json", {"seed": seed_value, "work": dict(sorted(intent.items()))})
    return intent


def reallocation(out) -> dict:
    """The T4 fixture. Returns {'m1_kg', 'm2_kg'}; no stamps (the test stamps)."""
    out = _prepare(out)
    _structural(out)
    rec = out / st.RECORDS_DIR
    snap = st.load(out).snapshot
    pelvis = float(snap["pelvis_mass"][0])
    m1, m2 = round(0.30 * pelvis, 3), round(0.25 * pelvis, 3)  # per side: before, pelvis 0.6 of its target; after the move 1.1 of it
    both = ["left", "right"]
    recs = [
        _part("part.hip.m1", "Hip drive module M1, in the pelvis.", "seg.pelvis", m1, acts_across="jnt.hip", reacts_into="seg.pelvis", harness=["hn.leg-power"], sides=both, category="actuator"),
        _part("part.hip.m2", "Hip drive module M2, in the thigh.", "seg.thigh", m2, acts_across="jnt.hip", reacts_into="seg.thigh", harness=["hn.leg-power"], sides=both, category="actuator"),
        _part("part.leg.m3", "Ankle drive M3, in the shank.", "seg.shank", 0.4, acts_across="jnt.ankle", reacts_into="seg.shank", harness=["hn.leg-power"], sides=both, category="actuator"),
        _record("harness_run", "hn.leg-power", "Power to the leg drives.", path=["seg.pelvis", "seg.thigh", "seg.shank"], carries="motor power"),
        _record("interface", "if.m2-thigh", "Mount of M2 in the thigh.", between=["part.hip.m2", "seg.thigh"], carries_cut_of="jnt.hip",
                mechanical={"status": "open"}, electrical={"status": "open"}, thermal={"status": "open"}),
    ]
    work = {
        "work.thigh-houses": ("seg.thigh", ["thread/derived/seg.thigh.json#/houses"]),
        "work.pelvis-houses": ("seg.pelvis", ["thread/derived/seg.pelvis.json#/houses"]),
        "work.m2-mount": ("part.hip.m2", ["part.hip.m2#/housed_in"]),
        "work.pelvis-mass": ("seg.pelvis", ["thread/derived/seg.pelvis.json#/budgets/mass"]),
        "work.hip-actuation": ("jnt.hip", ["thread/derived/jnt.hip.json#/acted_on_by"]),
        "work.shank-only": ("seg.shank", ["snapshot#/shank_right_mass", "snapshot#/shank_right_length", "thread/derived/seg.shank.json#/houses",
                                          "thread/derived/seg.shank.json#/budgets/mass"]),
    }
    recs += [_record("work_item", w, f"Fixture work on {of}.", of=of, mode="assisted", consumes=c) for w, (of, c) in sorted(work.items())]
    for r in recs:
        _yaml(rec / f"{r['id']}.yaml", r)
    _decision(out, "0001-hip-drive.md", "adr-0001", "accepted", ["part.hip.m1", "part.hip.m2"])
    return {"m1_kg": m1, "m2_kg": m2}
