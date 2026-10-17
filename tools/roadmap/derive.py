"""
Roadmap status derivation (docs/briefs/architecture/roadmap-brief1.md, "Status derivation") and the Roadmap result object.

Status is derived on every evaluation and never stored in a node file. A blocker is cleared when its status is done. Leaf: done if its
done_when passes, else blocked if an effective blocker is uncleared, else active if active: true, else ready. Stub: blocked or
expandable. Interior: done if every non-superseded child is done, else blocked if an effective blocker is uncleared, else in_progress
if any descendant is done or active, else not_started. `stale` is reserved and never emitted. On a graph with errors, whatever can be
derived is derived; a node caught in a cycle comes back `unknown`.
"""
from __future__ import annotations

import sys
from dataclasses import dataclass

from . import tags as tagvocab
from .evaluate import Evaluation, evaluate
from .model import Issue, load_nodes
from .validate import Graph, validate

STATUSES = ("done", "blocked", "active", "ready", "expandable", "in_progress", "not_started", "superseded", "stale", "unknown")
LIVE_ORDER = ("done", "in_progress", "active", "ready", "expandable", "blocked", "not_started", "unknown")  # print order of counts


@dataclass
class NodeState:
    kind: str  # interior | leaf | stub | superseded
    status: str
    reason: str
    evaluation: Evaluation | None
    uncleared: list


class Roadmap:
    """Everything computed from one root: nodes, issues, derived states and the relations a viewer or a CLI needs."""

    def __init__(self, root, graph, errors, warnings, states, vocabulary=None):
        self.root, self.graph = root, graph
        self.vocabulary = vocabulary or {}  # roadmap/tags.yaml: {namespace: {value: colour or None}}
        self.nodes = graph.nodes
        self.errors, self.warnings, self.states = errors, warnings, states
        live = [i for i in self.nodes if not self.nodes[i].superseded]
        self.node_count = len(live)
        self.superseded_count = len(self.nodes) - len(live)
        self.counts = {}
        for i in live:
            self.counts[states[i].status] = self.counts.get(states[i].status, 0) + 1
        self.frontier = sorted(i for i in live if states[i].status in ("ready", "expandable"))
        self._effective = {i: graph.effective_blockers(i) for i in self.nodes}
        self._dependents = {i: [] for i in self.nodes}
        for i in live:
            for b in self._effective[i]:
                if b in self._dependents:
                    self._dependents[b].append(i)
        for v in self._dependents.values():
            v.sort()

    # accessors (ids in, plain values out)
    def status(self, id) -> str:
        return self.states[id].status

    def reason(self, id) -> str:
        return self.states[id].reason

    def kind(self, id) -> str:
        return self.states[id].kind

    def evaluation(self, id):
        return self.states[id].evaluation

    def children(self, id) -> list:
        return list(self.graph.children.get(id, ()))

    def effective_blockers(self, id) -> list:
        return list(self._effective[id])

    def uncleared(self, id) -> list:
        return list(self.states[id].uncleared)

    def dependents(self, id) -> list:
        return list(self._dependents[id])

    def summary_line(self) -> str:
        if not self.nodes and not self.errors:
            return "roadmap: no nodes"
        return f"roadmap: {self.node_count} nodes | frontier {len(self.frontier)} | errors {len(self.errors)}"


def _kind(g: Graph, id) -> str:
    n = g.nodes[id]
    if n.superseded:
        return "superseded"
    if g.has_children(id):
        return "interior"
    return "stub" if n.stub else "leaf"


def derive(g: Graph, root, extra_warnings=None) -> tuple:
    """(states, warnings): the NodeState of every node and the warnings that need derived statuses."""
    nodes = g.nodes
    states, busy, progress = {}, set(), {}
    warnings = []
    eff = {i: g.effective_blockers(i) for i in nodes}
    sys.setrecursionlimit(max(sys.getrecursionlimit(), 20000))

    def uncleared_of(i) -> list:
        return [b for b in eff[i] if status_of(b) != "done"]

    def status_of(i) -> str:
        if i not in nodes:
            return "unknown"  # an unresolvable blocker is never cleared
        if i in states:
            return states[i].status
        if i in busy:
            return "unknown"
        busy.add(i)
        try:
            states[i] = compute(i)
        finally:
            busy.discard(i)
        return states[i].status

    def has_progress(i) -> bool:
        if i in progress:
            return progress[i]
        progress[i] = False  # guards a parent cycle
        progress[i] = any(status_of(c) in ("done", "active") or has_progress(c) for c in g.children.get(i, ()))
        return progress[i]

    def blocked_reason(unc) -> str:
        return "blocked by " + ", ".join(unc)

    def compute(i) -> NodeState:
        n, kind = nodes[i], _kind(g, i)
        if kind == "superseded":
            return NodeState(kind, "superseded", f"superseded by {n.superseded_by}", None, [])
        if kind == "interior":
            kids = g.children[i]
            kid_status = [status_of(c) for c in kids]
            if all(s == "done" for s in kid_status):
                unc = uncleared_of(i)
                if unc:
                    warnings.append(Issue("done-out-of-order", f"{n.path}: node {i} is done (all its children are) while blocker {', '.join(unc)} is not", (i, *unc), (n.path,)))
                return NodeState(kind, "done", f"all {len(kids)} children done", None, [])
            unc = uncleared_of(i)
            if unc:
                return NodeState(kind, "blocked", blocked_reason(unc), None, unc)
            if any(s == "unknown" for s in kid_status) and not has_progress(i):
                return NodeState(kind, "unknown", "a child's status cannot be derived (see errors)", None, [])
            if has_progress(i):
                done = sum(1 for d in g.descendants(i) if not g.has_children(d) and states.get(d) and states[d].status == "done")
                act = sum(1 for d in g.descendants(i) if not g.has_children(d) and states.get(d) and states[d].status == "active")
                return NodeState(kind, "in_progress", f"{done} leaves done, {act} active below", None, [])
            return NodeState(kind, "not_started", "no descendant is done or active", None, [])
        unc = uncleared_of(i)
        if kind == "stub":
            if unc:
                return NodeState(kind, "blocked", blocked_reason(unc), None, unc)
            return NodeState(kind, "expandable", "stub not yet decomposed", None, [])
        ev = evaluate(n, root)
        if ev is not None and ev.result == "unknown":
            warnings.append(Issue("criterion-unknown", f"{n.path}: node {i} cannot be evaluated: {ev.reason}", (i,), (n.path,)))
        if ev is not None and ev.result == "pass":
            if unc:
                warnings.append(Issue("done-out-of-order", f"{n.path}: node {i} is done while blocker {', '.join(unc)} is not", (i, *unc), (n.path,)))
            if n.active:
                warnings.append(Issue("active-on-done", f"{n.path}: node {i} is done but still marked active", (i,), (n.path,)))
            return NodeState(kind, "done", ev.reason, ev, unc)
        if unc:
            return NodeState(kind, "blocked", blocked_reason(unc), ev, unc)
        if n.active:
            return NodeState(kind, "active", f"in progress; {ev.reason}" if ev else "in progress", ev, [])
        return NodeState(kind, "ready", ev.reason if ev else "ready", ev, [])

    for i in sorted(nodes):
        status_of(i)
    for i in sorted(nodes):
        n = nodes[i]
        if n.signed_off and not (n.done_when and n.done_when.get("type") == "manual" and states[i].kind == "leaf"):
            warnings.append(Issue("signed-off-not-manual", f"{n.path}: node {i} has signed_off but its criterion is not manual", (i,), (n.path,)))
    return states, warnings


def compute(root) -> Roadmap:
    """Load, validate and derive the roadmap under `root` (a repo-shaped directory). Missing roadmap/nodes is an empty roadmap."""
    nodes, known, load_issues = load_nodes(root)
    g = Graph(nodes, known)
    errors, warnings = validate(g)
    vocabulary, vocab_issues = tagvocab.load_vocabulary(root)
    tag_errors, tag_warnings = ([], []) if vocab_issues else tagvocab.check(nodes, vocabulary)  # a broken tags.yaml is one error; its tags are not judged against it
    errors = load_issues + errors + vocab_issues + tag_errors
    warnings = [*warnings, *tag_warnings]
    states, derived_warnings = derive(g, root)
    warnings = sorted([*warnings, *derived_warnings], key=lambda w: (w.code, w.ids))
    errors = sorted(errors, key=lambda e: (e.code, e.ids, e.message))
    return Roadmap(root, g, errors, warnings, states, vocabulary)
