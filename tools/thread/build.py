"""
The thread build: validate the records against the model and the snapshot, derive everything about each record, compute the work statuses,
and render the generated outputs in memory. `Build` never writes; `write_outputs` and `write_stamp` are the only writers.

Order matters. Validation first (errors stop generation); then the *core* documents, which hold everything derived except the work
statuses; then the work statuses, which resolve their addresses against the core documents (so an address into a generated output sees the
core build, never the file on disk and never a work status); then the final documents, which add the work statuses, and the outputs.

Names (`EXPECTED_SEGMENTS`, `BILATERAL` and the column lists) come from pre_processor by import, never as a copied list.
"""
from __future__ import annotations

import json
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path

import yaml

from . import addr, edges, render
from . import store as st
from .store import Issue, error, warning

MASS_EPS_KG = 1e-9  # a sum of decimal masses carries float round-off of this order; a claim above the target by less is not an over-claim
MASS_DIGITS = 6  # kg figures in the derived files are rounded to a milligram per million, so the files do not carry float noise
VALUE_BYTES = 2048  # a stamp keeps a value itself when its canonical JSON is at most this long (brief: Stamp)
COMMON = ("schema", "id", "kind", "status", "purpose", "notes", "superseded_by")

REFS = {
    "part": (("housed_in", False, ("segment",)), ("acts_across", False, ("joint",)), ("reacts_into", False, ("segment",)),
             ("harness", True, ("harness_run",))),
    "interface": (("between", True, ("part", "segment")), ("carries_cut_of", False, ("joint",))),
    "harness_run": (("path", True, ("segment",)),),
    "work_item": (("of", False, edges.KINDS),),
}

_pp = None


def pre_processor():
    """pre_processor, imported by path from the library's own repo (it imports numpy and nothing that reads the sheet)."""
    global _pp
    if _pp is None:
        scripts = str(Path(__file__).resolve().parents[2] / "sim" / "scripts")
        if scripts not in sys.path:
            sys.path.insert(0, scripts)
        import pre_processor as pp
        _pp = pp
    return _pp


def segment_columns():
    pp = pre_processor()
    return list(pp.BSIP_COLUMNS) + list(pp.POS_COLUMNS)


def segment_name(id: str) -> str:
    return id.split(".", 1)[1]


def is_bilateral_segment(id: str) -> bool:
    return segment_name(id) in pre_processor().BILATERAL


def _claim(pid: str, p: dict, counted: list) -> dict:
    """A part's mass claim, with its arithmetic. `mass.kg` is the mass of one unit and `sides` gives one unit per side; `counted` is the
    sides whose units this budget counts."""
    kg = round(p["mass"]["kg"], MASS_DIGITS)
    n = max(len(counted), 1)
    where = f"{pid} {' and '.join(counted)}" if counted else pid
    return {"part": pid, "kg": kg, "sides": counted, "total_kg": round(kg * n, MASS_DIGITS), "arithmetic": f"{n} x {kg} kg, {where}"}


def keys_of(items):
    return [(i["id"] if isinstance(i, dict) else i) for i in items]


class Build:
    def __init__(self, store: st.Store):
        self.store = store
        self.root = store.root
        self.issues: list = list(store.issues)
        self.known: set = set(store.records)  # every loaded id, schema-valid or not (so one bad record does not cascade)
        self.recs: dict = {}  # schema-valid records
        self.core: dict = {}
        self.docs: dict = {}
        self.work: dict = {}
        self.outputs: dict = {}
        self.sources: dict = {}  # output path -> set of addresses its content was built from
        self.input_hashes: dict = {}  # output path -> 12 hex
        self.graph_core = None
        self._file_cache: dict = {}
        self._snapshot_doc = None
        self._stamp_docs = {st_path: doc for work, lst in store.stamps.items() for name, doc in lst
                            for st_path in [f"{st.STAMPS_DIR}/{work}/{name}.json"]}
        self._run()

    # ---- issues ---------------------------------------------------------------------------

    @property
    def errors(self) -> list:
        return [i for i in self.issues if i.level == "error"]

    @property
    def warnings(self) -> list:
        return [i for i in self.issues if i.level == "warning"]

    def _err(self, code, message, ids=()):
        self.issues.append(error(code, message, ids))

    def _warn(self, code, message, ids=()):
        self.issues.append(warning(code, message, ids))

    # ---- addresses ------------------------------------------------------------------------

    def resolve(self, address: str):
        """(True, value) or (False, None). See CONVENTIONS section 3 for the sources."""
        try:
            source, pointer = addr.parse(address)
        except ValueError:
            return False, None
        s = self.store
        if source == "snapshot":
            if self._snapshot_doc is None:
                self._snapshot_doc = {k: v for k, (v, _) in s.snapshot.items()}
            return addr.pointer_get(self._snapshot_doc, pointer)
        if source in s.records:
            return addr.pointer_get(s.records[source], pointer)
        if source.startswith("req.") and "/" not in source:
            source = f"requirements/{source}.yaml"
        elif "/" not in source and edges.kind_of(source) and not source.endswith((".json", ".yaml", ".yml", ".md")):
            return False, None  # a record id that does not exist
        doc = self._file_doc(source)
        if doc is None:
            return False, None
        return addr.pointer_get(addr.strip_banner(doc), pointer)

    def _file_doc(self, rel: str):
        if rel.startswith("/") or "\\" in rel or ":" in rel or ".." in rel.split("/"):
            return None
        if rel.startswith("thread/derived/") and rel.endswith(".json"):
            return self.core.get(rel[len("thread/derived/"):-len(".json")])
        if rel == "thread/graph.json":
            return self.graph_core
        if rel in self._file_cache:
            return self._file_cache[rel]
        p = self.root / rel
        doc = None
        if p.is_file():
            try:
                if rel.endswith(".json"):
                    doc = json.loads(p.read_text(encoding="utf-8"))
                elif rel.endswith((".yaml", ".yml")):
                    doc = st.normalise(yaml.load(p.read_text(encoding="utf-8"), Loader=st._YAML_LOADER))
            except (ValueError, yaml.YAMLError, UnicodeDecodeError):
                doc = None
        self._file_cache[rel] = doc
        return doc

    def address_hash(self, address: str):
        ok, value = self.resolve(address)
        return addr.hash_value(value) if ok else None

    def _source_hash(self, a: str) -> str:
        """The hash of a source for the `inputs` banner: addresses, plus the model, decision files and stamps, which are not JSON addresses."""
        source, _ = addr.parse(a)
        if source == st.MODEL_PATH:
            return self.store.model.sha
        if source.startswith(st.DECISIONS_DIR + "/"):
            return addr.hash_value(next((d for d in self.store.decisions if d["path"] == source), None))
        if source.startswith(st.STAMPS_DIR + "/"):
            return addr.hash_value(self._stamp_docs.get(source))
        return self.address_hash(a) or "unresolved"

    # ---- the run --------------------------------------------------------------------------

    def _run(self):
        s = self.store
        if s.model is None or not s.snapshot_sha:
            return
        self._validate_schemas()
        self._check_references()
        self._bind()
        self._check_stamps()
        self._static_warnings()
        if self.errors:
            return
        self._derive_core()
        self._work_statuses()
        self._finalize()

    def _validate_schemas(self):
        v = st.validator("thread-record-1.schema.json")
        for id in sorted(self.store.records):
            msg = st.schema_message(v, self.store.records[id])
            if msg is not None:
                self._err("schema", f"{self.store.files[id]}: {msg}", (id,))
            else:
                self.recs[id] = self.store.records[id]

    def _kind(self, id):
        return edges.kind_of(id)

    def _check_references(self):
        for id, r in sorted(self.recs.items()):
            for field, many, kinds in REFS.get(r["kind"], ()):
                targets = r.get(field, [])
                if not many:
                    targets = [targets] if field in r else []
                for t in targets:
                    if t not in self.known:
                        self._err("ref-unresolved", f"{id}: {field} names {t}, which is not a record", (id,))
                    elif self._kind(t) not in kinds:
                        self._err("ref-kind", f"{id}: {field} names {t}, a {self._kind(t)} (expected {' or '.join(kinds)})", (id,))
            if "superseded_by" in r:
                t = r["superseded_by"]
                if t not in self.known:
                    self._err("superseded-by", f"{id}: superseded_by names {t}, which is not a record", (id,))
                elif self._kind(t) != r["kind"]:
                    self._err("ref-kind", f"{id}: superseded_by names {t}, a {self._kind(t)} (expected {r['kind']})", (id,))
                elif t in self.recs and self.recs[t]["status"] == "superseded":
                    self._err("superseded-by", f"{id}: superseded_by names {t}, which is itself superseded", (id,))

    def _expand(self, base: str, names: dict):
        """(bound names, missing names) for a binding: the name itself when the model has it, else both sides."""
        if base in names:
            return [base], []
        both = [f"{base}_left", f"{base}_right"]
        present = [n for n in both if n in names]
        return (present, [n for n in both if n not in names]) if present else ([], [base])

    def _bind(self):
        s, pp = self.store, pre_processor()
        model = s.model
        self.seg_bodies, self.jnt_hinges, self.seg_names, self.jnt_children = {}, {}, {}, {}
        body_owner, hinge_owner, key_owner = defaultdict(list), defaultdict(list), defaultdict(list)
        cols = segment_columns()
        for id, r in sorted(self.recs.items()):
            if r["kind"] == "segment":
                name = segment_name(id)
                if name not in pp.EXPECTED_SEGMENTS:
                    self._err("binding-missing", f"{id}: {name!r} is not one of pre_processor's segments", (id,))
                bound, missing = self._expand(r["body"], model.bodies)
                if missing:
                    self._err("binding-missing", f"{id}: the model has no body {', '.join(missing)}", (id,))
                self.seg_bodies[id] = bound
                for b in bound:
                    body_owner[b].append(id)
                sides = ["right", "left"] if name in pp.BILATERAL else [None]
                names = [name if sd is None else f"{name}_{sd}" for sd in sides]
                self.seg_names[id] = names
                for n in names:
                    for c in cols:
                        if f"{n}_{c}" in s.snapshot:
                            key_owner[f"{n}_{c}"].append(id)
                if ("sides" in r) != (name in pp.BILATERAL):
                    self._err("sides", f"{id}: sides {'given' if 'sides' in r else 'missing'}, but pre_processor.BILATERAL "
                                       f"{'does not list' if name not in pp.BILATERAL else 'lists'} {name}", (id,))
            elif r["kind"] == "joint":
                bound = []
                for h in r["hinges"]:
                    got, missing = self._expand(h, model.hinges)
                    if missing:
                        self._err("binding-missing", f"{id}: the model has no hinge {', '.join(missing)}", (id,))
                    bound += got
                self.jnt_hinges[id] = bound
                for h in bound:
                    hinge_owner[h].append(id)
                for k in r["rom_keys"]:
                    key_owner[k].append(id)
        for table, what in ((body_owner, "body"), (hinge_owner, "hinge")):
            for name, ids in sorted(table.items()):
                if len(ids) > 1:
                    self._err("binding-duplicate", f"the model {what} {name} is bound by {', '.join(sorted(ids))}", tuple(sorted(ids)))
        for key, ids in sorted(key_owner.items()):
            if len(set(ids)) > 1:
                self._err("key-duplicate", f"the snapshot key {key} is bound by {', '.join(sorted(set(ids)))}", tuple(sorted(set(ids))))
        self.body_claimed, self.hinge_claimed = set(body_owner), set(hinge_owner)
        self.body_owner = {b: ids[0] for b, ids in body_owner.items() if len(ids) == 1}  # a doubly bound body has no owner, so nothing cascades from it
        self.hinge_owner = {h: ids[0] for h, ids in hinge_owner.items() if len(ids) == 1}
        # sides of joints and parts, which need the segment bindings
        for id, r in sorted(self.recs.items()):
            if r["kind"] == "joint":
                children = sorted({self.body_owner[model.hinges[h]] for h in self.jnt_hinges[id] if model.hinges[h] in self.body_owner})
                self.jnt_children[id] = children
                if children:
                    bilateral = any(is_bilateral_segment(c) for c in children)
                    if ("sides" in r) != bilateral:
                        self._err("sides", f"{id}: sides {'given' if 'sides' in r else 'missing'}, but its child segment "
                                           f"{', '.join(children)} is {'' if bilateral else 'not '}bilateral in pre_processor.BILATERAL", (id,))
            elif r["kind"] == "part":
                if "acts_across" in r and r["acts_across"] in self.jnt_hinges and self.jnt_children.get(r["acts_across"]):
                    j = r["acts_across"]
                    ends = set(self.jnt_children[j]) | set(self._parents_of(j))
                    if r["reacts_into"] not in ends and not self._ambiguous_ends(j):
                        self._err("reaction-path", f"{id}: reacts_into {r['reacts_into']} is neither the parent nor the child segment of {j} "
                                                   f"({', '.join(sorted(ends))})", (id,))
                seg = r["housed_in"]
                if seg in self.recs and self.recs[seg]["kind"] == "segment" and is_bilateral_segment(seg) and "sides" not in r:
                    self._err("sides", f"{id}: housed in the bilateral segment {seg}, so it needs sides [left, right]", (id,))

    def _parents_of(self, jnt: str) -> list:
        model = self.store.model
        return sorted({self.body_owner[model.bodies[model.hinges[h]]] for h in self.jnt_hinges[jnt]
                       if model.bodies.get(model.hinges[h]) in self.body_owner})

    def _ambiguous_ends(self, jnt: str) -> bool:
        """True when an end of the joint is a body that two records bind (already an error), so the end cannot be named."""
        model = self.store.model
        bodies = {model.hinges[h] for h in self.jnt_hinges[jnt]} | {model.bodies.get(model.hinges[h]) for h in self.jnt_hinges[jnt]}
        return any(b in self.body_claimed and b not in self.body_owner for b in bodies)

    def _check_stamps(self):
        for work in sorted(self.store.stamp_dirs):
            if work not in self.recs or self.recs[work]["kind"] != "work_item":
                self._err("stamp-unknown-work", f"thread/stamps/{work}/ holds stamps, but {work} is not a work item", (work,))

    def _static_warnings(self):
        model = self.store.model
        for b in model.bodies:
            if b not in getattr(self, "body_claimed", ()):
                self._warn("unbound-body", f"the model body {b} has no segment record", (b,))
        for h in model.hinges:
            if h not in getattr(self, "hinge_claimed", ()):
                self._warn("unbound-hinge", f"the model hinge {h} has no joint record", (h,))
        for id, r in sorted(self.recs.items()):
            if r["status"] != "active":
                continue
            for field, many, kinds in REFS.get(r["kind"], ()):
                targets = r.get(field, [])
                if not many:
                    targets = [targets] if field in r else []
                for t in targets:
                    if t in self.recs and self.recs[t]["status"] != "active":
                        self._warn("active-refs-inactive", f"{id} is active but {field} names {t}, which is {self.recs[t]['status']}", (id, t))

    # ---- derivation -----------------------------------------------------------------------

    def _derive_core(self):
        s, recs = self.store, self.recs
        src = defaultdict(set)  # record id -> addresses its derived document was built from
        inv = defaultdict(lambda: defaultdict(set))  # relation name -> target id -> {source ids}

        def link(rel, target, owner, field):
            """target's derived document lists owner under `rel`; it depends on that one field of the owner, not on the whole record, so an
            unrelated edit to the owner leaves the target's bytes (banner hash included) alone."""
            inv[rel][target].add(owner)
            src[target].add(f"{owner}#/{field}")

        consumed_targets = defaultdict(set)
        for id, r in sorted(recs.items()):
            src[id].add(f"{id}#")
            k = r["kind"]
            if k == "part":
                link("houses", r["housed_in"], id, "housed_in")
                if "reacts_into" in r:
                    link("reacted_by", r["reacts_into"], id, "reacts_into")
                if "acts_across" in r:
                    link("acted_on_by", r["acts_across"], id, "acts_across")
                for h in r.get("harness", []):
                    link("used_by", h, id, "harness")
            elif k == "interface":
                for t in r["between"]:
                    link("interfaces", t, id, "between")
                if "carries_cut_of" in r:
                    link("interfaces", r["carries_cut_of"], id, "carries_cut_of")
            elif k == "harness_run":
                for t in r["path"]:
                    link("crossed_by", t, id, "path")
            elif k == "work_item":
                for a in r["consumes"]:
                    t = self._record_of_address(a)
                    if t is not None and t in recs:
                        link("consumed_by", t, id, "consumes")
                        consumed_targets[id].add(t)
        decisions = defaultdict(list)
        for d in s.decisions:
            for t in d["links"]:
                if t in recs:
                    decisions[t].append({"id": d["id"], "status": d["status"]})
                    src[t].add(f"{d['path']}#")
        # joints: parent and child segments from the model's body tree
        model = s.model
        joints_parent, joints_child = defaultdict(set), defaultdict(set)
        jnt_parent_segs = {}
        for id, bound in self.jnt_hinges.items():
            parents = set()
            src[id].add(f"{st.MODEL_PATH}#")
            for h in bound:
                body = model.hinges[h]
                pb = model.bodies.get(body)
                if pb in self.body_owner:
                    parents.add(self.body_owner[pb])
            jnt_parent_segs[id] = sorted(parents)
            for c in self.jnt_children[id]:
                joints_child[c].add(id)
                src[c].add(f"{id}#/hinges")
                src[id].add(f"{c}#/body")
            for p in parents:
                joints_parent[p].add(id)
                src[p].add(f"{id}#/hinges")
                src[id].add(f"{p}#/body")
        budgets = self._mass_budgets(src)
        for id, r in sorted(recs.items()):
            doc = {k: r[k] for k in COMMON if k in r and k != "schema"}
            doc.update({k: v for k, v in r.items() if k not in COMMON})
            k = r["kind"]
            lst = lambda rel: sorted(inv[rel][id])  # noqa: E731
            if k == "segment":
                doc["bound_bodies"] = sorted(self.seg_bodies[id])
                src[id].add(f"{st.MODEL_PATH}#")
                doc["values"] = {}
                for key in sorted(f"{self.seg_names[id][0]}_{c}" for c in segment_columns()):
                    if key in s.snapshot:
                        doc["values"][key] = {"value": s.snapshot[key][0], "sheet_source": s.snapshot[key][1]}
                        src[id].add(f"snapshot#/{key}")
                doc.update(houses=lst("houses"), reacted_by=lst("reacted_by"), crossed_by=lst("crossed_by"),
                           joints_as_parent=sorted(joints_parent[id]), joints_as_child=sorted(joints_child[id]), interfaces=lst("interfaces"),
                           budgets={"mass": budgets["segments"][id]})
            elif k == "joint":
                doc["bound_hinges"] = sorted(self.jnt_hinges[id])
                doc["parent_segments"] = jnt_parent_segs[id]
                doc["child_segments"] = self.jnt_children[id]
                doc["rom"] = {key: {"value": s.snapshot[key][0], "sheet_source": s.snapshot[key][1]} for key in sorted(r["rom_keys"]) if key in s.snapshot}
                doc["rom_missing"] = sorted(key for key in r["rom_keys"] if key not in s.snapshot)
                for key in r["rom_keys"]:
                    src[id].add(f"snapshot#/{key}")
                doc.update(acted_on_by=lst("acted_on_by"), interfaces=lst("interfaces"))
            elif k == "part":
                doc["interfaces"] = lst("interfaces")
            elif k == "harness_run":
                doc["used_by"] = lst("used_by")
            doc["consumed_by"] = lst("consumed_by")
            doc["decisions"] = sorted(decisions[id], key=lambda d: d["id"])
            self.core[id] = doc
        self._src = src
        self._consumed_targets = consumed_targets
        self.budgets = budgets
        self.graph_core = self._graph(None)

    def _record_of_address(self, a: str):
        """The record an address belongs to: the record itself, or the record whose derived file it points into."""
        try:
            source, _ = addr.parse(a)
        except ValueError:
            return None
        if source.startswith("thread/derived/") and source.endswith(".json"):
            return source[len("thread/derived/"):-len(".json")]
        return source if "/" not in source and edges.kind_of(source) else None

    def _mass_budgets(self, src) -> dict:
        s, recs = self.store, self.recs
        segs = {}
        for id, r in sorted(recs.items()):
            if r["kind"] != "segment":
                continue
            bil = is_bilateral_segment(id)
            key = f"{self.seg_names[id][0]}_mass"
            target = float(s.snapshot[key][0]) if key in s.snapshot else None
            if target is not None:
                src[id].add(f"snapshot#/{key}")
            claims = []
            for pid, p in sorted(recs.items()):
                if p["kind"] == "part" and p["housed_in"] == id and p["status"] in ("active", "proposed"):
                    counted = (["right"] if bil else list(p["sides"])) if "sides" in p else []
                    claims.append(_claim(pid, p, counted))
                    src[id].update(f"{pid}#/{f}" for f in ("housed_in", "status", "mass", "sides"))
            claimed = round(sum(c["total_kg"] for c in claims), MASS_DIGITS)
            over = target is not None and claimed - target > MASS_EPS_KG
            segs[id] = {"target_kg": target, "claimed_kg": claimed, "remaining_kg": None if target is None else round(target - claimed, MASS_DIGITS),
                        "over": bool(over), "claims": claims}
            if over:
                self._warn("budget-over", f"{id} claims {claimed} kg against a target of {target} kg", (id,))
        body_claims = [_claim(pid, p, list(p["sides"]) if "sides" in p else []) for pid, p in sorted(recs.items())
                       if p["kind"] == "part" and p["status"] in ("active", "proposed")]
        total = round(sum(c["total_kg"] for c in body_claims), MASS_DIGITS)
        target = float(s.snapshot["target_mass"][0]) if "target_mass" in s.snapshot else None
        body = {"target_kg": target, "claimed_kg": total, "over": bool(target is not None and total - target > MASS_EPS_KG), "claims": body_claims}
        if body["over"]:
            self._warn("budget-over", f"the parts claim {total} kg against a body target of {target} kg", ("body",))
        return {"segments": segs, "body": body}

    # ---- work -----------------------------------------------------------------------------

    def _work_statuses(self):
        s = self.store
        self.work_sources = {}
        for id, r in sorted(self.recs.items()):
            if r["kind"] != "work_item":
                continue
            stamps = s.stamps.get(id, [])
            consumes = list(r["consumes"])
            unresolved = [a for a in consumes if not self.resolve(a)[0]]
            moved, baseline_name, pinned = [], None, False
            status = "unstamped"
            wsrc = {f"{id}#"} | set(consumes)
            if stamps:
                baseline_name, base = stamps[-1]
                pinned = base["pinned"]
                wsrc |= {f"{st.STAMPS_DIR}/{id}/{baseline_name}.json#"} | {c["address"] for c in base["consumes"]}
                broken = False
                for c in base["consumes"]:
                    ok, value = self.resolve(c["address"])
                    if not ok:
                        broken = True
                        unresolved.append(c["address"])
                        moved.append({"address": c["address"], "stamped": c["value"], "stamped_hash": c["hash"], "current": None, "current_hash": None})
                    elif addr.hash_value(value) != c["hash"]:
                        moved.append({"address": c["address"], "stamped": c["value"], "stamped_hash": c["hash"],
                                      "current": value if len(addr.canonical(value)) <= VALUE_BYTES else None, "current_hash": addr.hash_value(value)})
                status = "unknown" if broken else ("current" if not moved else ("drifted" if pinned else "stale"))
                if {c["address"] for c in base["consumes"]} != set(consumes):
                    self._warn("consumes-changed", f"{id}: the consumes list differs from the baseline stamp {baseline_name}", (id,))
            unresolved = sorted(set(unresolved))
            if unresolved:
                self._warn("address-unresolved", f"{id}: {', '.join(unresolved)} does not resolve", (id,))
            self.work[id] = {"status": status, "stamp": baseline_name, "pinned": pinned, "moved": moved}
            self.work_sources[id] = wsrc

    # ---- outputs --------------------------------------------------------------------------

    def _finalize(self):
        recs = self.recs
        involved = defaultdict(dict)  # record id -> {work id: set(roles)}
        for wid, r in recs.items():
            if r["kind"] != "work_item":
                continue
            involved[r["of"]].setdefault(wid, set()).add("owns")
            for t in self._consumed_targets.get(wid, ()):
                involved[t].setdefault(wid, set()).add("consumes")
        self.graph_final = self._graph(self.work)
        for id, doc in self.core.items():
            final = dict(doc)
            if recs[id]["kind"] == "work_item":
                final["work"] = dict(self.work[id])
                self._src[id] |= self.work_sources[id]
            else:
                final["work"] = []
            for wid, roles in sorted(involved.get(id, {}).items()):
                if recs[id]["kind"] != "work_item":
                    final["work"].append({"id": wid, "status": self.work[wid]["status"], "role": sorted(roles)})
                self._src[id] |= self.work_sources[wid]
            self.docs[id] = final
        paths = {}
        for id in sorted(self.docs):
            paths[f"thread/derived/{id}.json"] = self._src[id]
            paths[f"thread/dossiers/{id}.md"] = self._src[id]
        everything = set().union(*paths.values()) if paths else set()
        paths["thread/graph.json"] = everything
        paths["thread/STATUS.md"] = everything
        self.sources = paths
        for path, srcs in paths.items():
            self.input_hashes[path] = addr.hash_value(sorted([a, self._source_hash(a)] for a in srcs))
        ctx = render.Context(self)
        for id in sorted(self.docs):
            self.outputs[f"thread/derived/{id}.json"] = render.json_bytes(self.docs[id], ctx.banner(f"thread/derived/{id}.json"))
            self.outputs[f"thread/dossiers/{id}.md"] = ctx.dossier(id)
        self.outputs["thread/graph.json"] = render.json_bytes(self.graph_final, ctx.banner("thread/graph.json"))
        self.outputs["thread/STATUS.md"] = ctx.status()

    def _graph(self, work_statuses) -> dict:
        recs = self.recs
        nodes = [{"id": i, "kind": r["kind"], "status": r["status"]} for i, r in sorted(recs.items())]
        es = set()
        for id, r in recs.items():
            for field, many, _ in REFS.get(r["kind"], ()):
                if field in r and field != "of":
                    for t in (r[field] if many else [r[field]]):
                        es.add((field, id, t))
            if "superseded_by" in r:
                es.add(("superseded_by", id, r["superseded_by"]))
            if r["kind"] == "work_item":
                es.add(("of", id, r["of"]))
                for t in self._consumed_targets.get(id, ()):
                    es.add(("consumes", id, t))
        for id, doc in self.core.items():
            for name, t in edges.BY_NAME.items():
                if t.origin == "derived" and name in doc:
                    for to in doc[name]:
                        es.add((name, id, to))
        g = {"schema": "thread-graph/1", "nodes": nodes,
             "edges": [{"type": a, "from": b, "to": c} for a, b, c in sorted(es)],
             "edge_types": [t.to_dict() for t in edges.EDGE_TYPES],
             "budgets": {"mass": {"body": self.budgets["body"], "segments": {i: {k: v for k, v in b.items() if k in ("target_kg", "claimed_kg", "over")}
                                                                                for i, b in self.budgets["segments"].items()}}}}
        if work_statuses is not None:
            g["work_statuses"] = {i: w["status"] for i, w in sorted(work_statuses.items())}
        return g


def build(store: st.Store) -> Build:
    return Build(store)


def build_root(root) -> Build:
    return Build(st.load(root))


def write_outputs(root, b: Build) -> list:
    """Write the generated outputs under root; only files whose bytes changed. Removes generated files for ids that no longer exist.
    Returns the repo-relative paths written or removed. Nothing is written when the build has errors."""
    root = Path(root)
    if b.errors:
        raise ValueError("the thread has errors; nothing was written")
    done = []
    for rel, data in sorted(b.outputs.items()):
        p = root / rel
        if p.is_file() and p.read_bytes() == data:
            continue
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(data)
        done.append(rel)
    for sub in ("derived", "dossiers"):
        d = root / "thread" / sub
        if d.is_dir():
            for p in sorted(d.iterdir()):
                rel = p.relative_to(root).as_posix()
                if p.is_file() and rel not in b.outputs:
                    p.unlink()
                    done.append(rel)
    return done


def write_stamp(root, b: Build, work: str, *, stamp: str | None = None, note: str = "", pinned: bool = False, by: str) -> Path:
    """Write thread/stamps/<work>/<stamp>.json for the work item's current `consumes`. ValueError (nothing written) when the thread has errors,
    the work item is unknown, an address does not resolve, or the stamp already exists (a stamp is never edited)."""
    if b.errors:
        raise ValueError("the thread has errors: " + "; ".join(f"{i.code} {i.message}" for i in b.errors[:3]))
    r = b.recs.get(work)
    if r is None or r["kind"] != "work_item":
        raise ValueError(f"{work} is not a work item")
    rows, bad = [], []
    for a in r["consumes"]:
        ok, value = b.resolve(a)
        if not ok:
            bad.append(a)
            continue
        rows.append({"address": a, "hash": addr.hash_value(value), "value": value if len(addr.canonical(value)) <= VALUE_BYTES else None})
    if bad:
        raise ValueError(f"{work}: these addresses do not resolve: {', '.join(bad)}")
    stamp = stamp or datetime.now().strftime("%Y%m%d-%H%M")
    p = Path(root) / st.STAMPS_DIR / work / f"{stamp}.json"
    if p.exists():
        raise ValueError(f"{p.relative_to(root).as_posix()} already exists; a stamp is never edited")
    doc = {"schema": "thread-stamp/1", "work": work, "stamp": stamp, "consumes": rows, "note": note, "pinned": bool(pinned), "by": by}
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(doc, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
    return p
