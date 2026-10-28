"""The bridge's operations (Stage 3b T6): validate, push, pull, drift, stamp and status for the bound documents of a repo root. Each takes a `Context`: the repo
root, the thread's address resolver and a `bridge(verb, **args)` callable that runs a verb of the Fusion-side module. Tests pass a recorded fake; the
command line passes the HTTP transport. No operation here imports `adsk`."""
from __future__ import annotations

import json
import math
import shutil
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

import yaml

from thread import addr

from . import binding as cb
from . import component, drift, frames, massprops, mesh, params, sidecar, step, units

BINDINGS = "cad/bindings"
SIDECARS = "cad/sidecars"
EXPORTS = "cad/exports"
COMPONENTS = "data/envelope/components/cad"
VERSION_WAIT_S = 20.0       # Fusion shows the new version number about a second after a save
VERSION_POLL_S = 0.5
ACCURACY = "veryhigh"       # the highest calculation accuracy Fusion's API offers


class Refused(RuntimeError):
    """An operation that would be unsafe or meaningless; the message says why. Nothing was written."""


@dataclass
class Context:
    root: Path
    resolve: Callable            # address -> (ok, value)
    bridge: Callable             # (verb, **args) -> dict
    say: Callable = print


# ---- bindings --------------------------------------------------------------------------------------------------------------------------

def parts(root) -> list:
    return sorted(p.stem for p in (Path(root) / BINDINGS).glob("*.yaml"))


def load_binding(root, part: str) -> dict:
    p = Path(root) / BINDINGS / f"{part}.yaml"
    if not p.is_file():
        raise Refused(f"no binding {BINDINGS}/{part}.yaml")
    return cb.load(p)


def _expect(binding: dict) -> dict:
    return {"expect_name": binding["document"]["name"]}


def _call(ctx: Context, binding: dict, verb: str, **args):
    return ctx.bridge(verb, **_expect(binding), **args)


def document_problems(binding: dict, info: dict) -> list:
    out = []
    if not str(info.get("id") or "").startswith("urn:"):
        out.append(f"the document's id is {info.get('id')!r}, not a urn: it has not finished syncing, or was never saved; a local path never enters a tracked file")
    elif info["id"] != binding["document"]["id"]:
        out.append(f"the document's id {info['id']} is not the binding's {binding['document']['id']}")
    if not info.get("parametric", False):
        out.append("the document is not a parametric design")
    if info.get("length_units") != "mm":
        out.append(f"the document's length unit is {info.get('length_units')!r}, not mm")
    return out


# ---- validate --------------------------------------------------------------------------------------------------------------------------

def validate(ctx: Context, part: str) -> list:
    """Problems with a bound document: the document's identity, every parameter's prefix, every inherited parameter present, no extra user parameters, and
    every inherited address resolving to a number. Reads only."""
    binding = load_binding(ctx.root, part)
    problems = document_problems(binding, _call(ctx, binding, "doc_info"))
    problems += params.check_document(binding, _call(ctx, binding, "read_params")["parameters"])
    try:
        cb.resolve_inherited(binding, ctx.resolve)
    except cb.BindingError as e:
        problems.append(str(e))
    return problems


# ---- push, drift -----------------------------------------------------------------------------------------------------------------------

def push(ctx: Context, part: str) -> dict:
    """Set the inherited parameters from their addresses by expression. On a failed regeneration the bridge rolls back; the result says so."""
    binding = load_binding(ctx.root, part)
    problems = validate(ctx, part)
    if problems:
        raise Refused("; ".join(problems))
    rows = cb.resolve_inherited(binding, ctx.resolve)
    before = _call(ctx, binding, "doc_info")
    unsaved_before = _unsaved(before)
    result = _call(ctx, binding, "set_expressions", expressions={r["name"]: r["expression"] for r in rows}, allowed_prefixes=["in_"], rollback_on_failure=True)
    result["rows"] = rows
    result.update(unsaved_before=unsaved_before, saved=False, save_skipped=None, save_note=None)
    if not result["ok"]:
        result["save_skipped"] = "the push failed"
    elif unsaved_before:
        result["save_skipped"] = "the document had unsaved changes before the push, so it was not saved and the pull will record unsaved_changes"
    elif not _unsaved(_call(ctx, binding, "doc_info")):
        result["save_skipped"] = "nothing changed"
    else:
        desc = "fy cad push: " + "; ".join(f"{r['address']} -> {r['name']} = {r['expression']}" for r in rows)
        saved = _call(ctx, binding, "save_document", description=desc)
        if saved["saved"]:
            result["saved"] = True
            result["version"] = _new_version(ctx, binding, before["version"])
            if result["version"] is None:
                result["save_note"] = "saved, but Fusion's new version number was not confirmed"
        else:
            result["save_skipped"] = "save failed: Fusion did not save the document"
    return result


def _new_version(ctx: Context, binding: dict, old: int):
    """The version number after a save, once Fusion shows it (it lags the save by about a second); None when it does not within VERSION_WAIT_S."""
    import time
    deadline = time.monotonic() + VERSION_WAIT_S
    while True:
        v = _call(ctx, binding, "doc_info")["version"]
        if v is not None and (old is None or v > old):
            return v
        if time.monotonic() >= deadline:
            return None
        time.sleep(VERSION_POLL_S)


def _unsaved(info: dict) -> bool:
    return bool(info.get("modified") or not info.get("saved", True))


def drift_of(ctx: Context, part: str) -> list:
    binding = load_binding(ctx.root, part)
    return drift.check(binding, _call(ctx, binding, "read_params")["parameters"], ctx.resolve)


# ---- pull ------------------------------------------------------------------------------------------------------------------------------

def segment_of(root, part: str) -> str:
    """The envelope's name of the segment housing a part: the thread record's `housed_in`, with `_R` on a bilateral segment (the right side is modelled)."""
    rec = Path(root) / "thread" / "records" / f"{part}.yaml"
    if not rec.is_file():
        raise Refused(f"{part} has no thread record, so its segment is unknown (thread/records/{part}.yaml)")
    seg = yaml.safe_load(rec.read_text(encoding="utf-8"))["housed_in"]
    segrec = yaml.safe_load((Path(root) / "thread" / "records" / f"{seg}.yaml").read_text(encoding="utf-8"))
    name = seg.split(".", 1)[1]
    return f"{name}_R" if segrec.get("sides") == ["left", "right"] else name


def _relative(path: Path, start: Path) -> str:
    import os
    return os.path.relpath(path, start).replace("\\", "/")


def pull(ctx: Context, part: str, segment: str | None = None) -> dict:
    """Read the bound document and write its sidecar, the canonical STL, the STEP (gitignored) and the generated component registry of its segment.
    Refuses an unhealthy timeline, a document that does not match its binding, and any parameter problem."""
    root = Path(ctx.root)
    binding = load_binding(root, part)
    info = _call(ctx, binding, "doc_info")
    problems = document_problems(binding, info)
    health = _call(ctx, binding, "timeline_health")
    if not health["healthy"]:
        raise Refused("the timeline is not healthy: " + ", ".join(health["failed_features"]))
    raw = _call(ctx, binding, "read_params")["parameters"]
    problems += params.check_document(binding, raw)
    if problems:
        raise Refused("; ".join(problems))
    segment = segment or segment_of(root, part)
    resolved = cb.resolve_inherited(binding, ctx.resolve)
    values = {r["name"]: units.fusion_value_to_unit(r["value"], p["unit"]) for p in cb.inherited(binding) for r in raw if r["name"] == p["name"]}
    drifted = drift.compare(resolved, values)
    consumes = cb.consumes(binding, ctx.resolve)

    mass = massprops.mass_properties(_call(ctx, binding, "physical_properties", accuracy=ACCURACY))

    chord = float(binding.get("chord_tolerance_mm", 0.05))
    curv = _call(ctx, binding, "max_curvature_radius")
    r_max_mm = None if curv["max_radius_cm"] is None else units.fusion_length_to_mm(curv["max_radius_cm"])
    normal_deg = mesh.normal_deviation_deg(chord, r_max_mm)
    bound_mm = 0.0 if r_max_mm is None else r_max_mm * (1.0 - math.cos(math.radians(normal_deg) / 2.0))

    exports = root / EXPORTS
    exports.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="freyja-cad-") as tmp:
        stl_tmp, step_tmp = (Path(tmp) / "part.stl").as_posix(), (Path(tmp) / "part.step").as_posix()
        _call(ctx, binding, "export_stl", path=stl_tmp, surface_deviation_cm=units.mm_to_fusion_length(chord), normal_deviation_deg=normal_deg)
        verts, faces = mesh.read(stl_tmp)
        vm = frames.points_to_model(verts, binding["side"])
        stl_path = exports / f"{part}.stl"
        mesh_hash = mesh.write_canonical_stl(stl_path, vm, faces)
        _call(ctx, binding, "export_step", path=step_tmp)
        step_bytes = Path(step_tmp).read_bytes()
    (exports / f"{part}.step").write_bytes(step_bytes)

    stl_rel = f"{EXPORTS}/{part}.stl"
    comp = component.component_entry(binding, segment=segment, vertices_model=vm, mesh_hash=mesh_hash, mass_kg=mass["mass_kg"], consumes=consumes, mesh_path=stl_rel)
    doc = sidecar.assemble(
        require_healthy=True,
        identity={"part": part, "revision": binding["revision"], "side": binding["side"], "binding_sha256": cb.binding_hash(binding)},
        document={"name": info["name"], "id": info["id"], "version": info["version"], "unsaved_changes": _unsaved(info)},
        parameters=params.sidecar_parameters(binding, raw, resolved),
        drift=drifted,
        timeline={"healthy": health["healthy"], "failed_features": health["failed_features"]},
        mass_properties=mass,
        exports={"stl": {"path": stl_rel, "sha256": mesh_hash, "chord_tolerance_mm": chord, "normal_deviation_deg": normal_deg, "chord_bound_mm": bound_mm,
                         "chord_guarantee": int(curv.get("freeform_faces", 0)) == 0, "triangles": int(len(faces))},
                 "step": {"path": f"{EXPORTS}/{part}.step", "sha256": step.step_hash(step_bytes)}},
        component=comp,
        consumes=consumes)
    (root / SIDECARS).mkdir(parents=True, exist_ok=True)
    sidecar.write(root / SIDECARS / f"{part}.json", doc)
    write_components(root, segment)
    return doc


def write_components(root, segment: str) -> Path:
    """data/envelope/components/cad/<segment>.yaml from every sidecar whose component is owned by the segment. Generated; sorted by id."""
    root = Path(root)
    entries, inputs = [], []
    for f in sorted((root / SIDECARS).glob("*.json")):
        doc = json.loads(f.read_text(encoding="utf-8"))
        c = doc["component"]
        if c["owner"] != segment:
            continue
        inputs.append(doc["inputs"])
        entries.append({"id": c["id"], "name": c["name"], "status": c["status"], "owner": c["owner"], "revision": c["revision"], "primitive": c["primitive"],
                        "mesh": _relative(root / c["mesh"], root / COMPONENTS), "clearance_mm": c["clearance_mm"], "mass_kg": c["mass_kg"],
                        "sha256": c["sha256"], "parameter_inputs": c["parameter_inputs"], "source": f"{SIDECARS}/{f.name}"})
    out = root / COMPONENTS / f"{segment}.yaml"
    out.parent.mkdir(parents=True, exist_ok=True)
    banner = f"# GENERATED by tools/cad pull from {SIDECARS}/*.json (inputs sha256:{addr.hash_value(inputs)}). Do not edit; change the inputs and rerun `fy cad pull`.\n"
    out.write_text(banner + yaml.safe_dump({"schema": "components/1", "segment": segment, "components": entries}, sort_keys=False, default_flow_style=None), encoding="utf-8", newline="\n")
    return out


# ---- stamp, status ---------------------------------------------------------------------------------------------------------------------

def work_item_of(root, part: str) -> str:
    recs = sorted((Path(root) / "thread" / "records").glob("work.*.yaml"))
    ids = [r.stem for r in recs if yaml.safe_load(r.read_text(encoding="utf-8")).get("of") == part]
    if len(ids) != 1:
        raise Refused(f"{part} needs exactly one work item with `of: {part}`; found {ids}")
    return ids[0]


def load_sidecar(root, part: str) -> dict:
    p = Path(root) / SIDECARS / f"{part}.json"
    if not p.is_file():
        raise Refused(f"no sidecar {SIDECARS}/{part}.json: run `fy cad pull {part}` first")
    return json.loads(p.read_text(encoding="utf-8"))


def stamp_refusals(ctx: Context, part: str) -> list:
    """Why the work item may not be stamped: drift recorded in the sidecar, an unhealthy timeline, or consumed hashes that differ from the current ones."""
    sc = load_sidecar(ctx.root, part)
    out = []
    if sc["drift"]:
        out.append("the sidecar shows drift in " + ", ".join(d["name"] for d in sc["drift"]))
    if sc["document"]["unsaved_changes"]:
        out.append("the sidecar was pulled with unsaved changes in Fusion, so it does not describe a saved version: save the document and pull again")
    if not sc["timeline"]["healthy"]:
        out.append("the sidecar's timeline is not healthy: " + ", ".join(sc["timeline"]["failed_features"]))
    now = {c["address"]: c["hash"] for c in cb.consumes(load_binding(ctx.root, part), ctx.resolve)}
    for c in sc["consumes"]:
        if now.get(c["address"]) != c["hash"]:
            out.append(f"{c['address']} was {c['hash']} when pulled and is {now.get(c['address'])} now: pull again")
    for a in sorted(set(now) - {c["address"] for c in sc["consumes"]}):
        out.append(f"{a} is consumed by the binding but not recorded in the sidecar: pull again")
    return out


def stamp(ctx: Context, part: str, note: str = "", by: str | None = None) -> Path:
    from thread import build as thread_build
    why = stamp_refusals(ctx, part)
    if why:
        raise Refused("; ".join(why))
    work = work_item_of(ctx.root, part)
    b = thread_build.build_root(ctx.root)
    return thread_build.write_stamp(ctx.root, b, work, note=note, pinned=False, by=by or _git_user())


def _git_user() -> str:
    import subprocess
    try:
        return subprocess.run(["git", "config", "user.name"], capture_output=True, text=True, check=True).stdout.strip() or "unknown"
    except (OSError, subprocess.CalledProcessError):
        return "unknown"


def status(ctx: Context) -> list:
    """One line per binding: revision, the sidecar's document version, drift, timeline, work status. Reads the sidecar and thread/graph.json, not Fusion."""
    lines = []
    graph_path = Path(ctx.root) / "thread" / "graph.json"
    graph = json.loads(graph_path.read_text(encoding="utf-8")) if graph_path.is_file() else {}
    for part in parts(ctx.root):
        b = load_binding(ctx.root, part)
        sc = Path(ctx.root) / SIDECARS / f"{part}.json"
        if not sc.is_file():
            lines.append(f"{part}  rev {b['revision']}  no sidecar (never pulled)")
            continue
        d = json.loads(sc.read_text(encoding="utf-8"))
        try:
            w = graph_work_status(graph, work_item_of(ctx.root, part))
        except Refused:
            w = "no work item"
        lines.append(f"{part}  rev {d['identity']['revision']}  doc v{d['document']['version']}{'  UNSAVED' if d['document']['unsaved_changes'] else ''}  drift {'none' if not d['drift'] else ','.join(x['name'] for x in d['drift'])}"
                     f"  timeline {'healthy' if d['timeline']['healthy'] else 'FAILED'}  work {w}")
    return lines


def graph_work_status(graph: dict, work: str) -> str:
    return graph.get("work_statuses", {}).get(work, "unknown")
