"""
Roadmap validation: structure across nodes (docs/briefs/architecture/roadmap-brief1.md, "Validation"). Errors stop generation; warnings
are listed in the outputs. Every message names the offending ids and file paths.

A node counts as having children when at least one child is not superseded. A superseded node is retired and exempt from the leaf,
stub and interior field rules.
"""
from __future__ import annotations

from .model import ESTIMATE_CAP_DAYS, Issue


class Graph:
    """The tree and the blocking edges over the loaded nodes. Safe on graphs with cycles and dangling references."""

    def __init__(self, nodes: dict, known: set):
        self.nodes, self.known = nodes, set(known) | set(nodes)
        self.all_children = {i: [] for i in nodes}  # every child, superseded or not
        for n in nodes.values():
            if n.parent in nodes:
                self.all_children[n.parent].append(n.id)
        for v in self.all_children.values():
            v.sort()
        self.children = {i: [c for c in cs if not nodes[c].superseded] for i, cs in self.all_children.items()}

    def live(self, id) -> bool:
        return id in self.nodes and not self.nodes[id].superseded

    def has_children(self, id) -> bool:
        return bool(self.children.get(id))

    def ancestors(self, id) -> list:
        """Parents from nearest to root; stops at a missing parent or a repeat."""
        out, seen, cur = [], {id}, self.nodes[id].parent if id in self.nodes else None
        while cur is not None and cur in self.nodes and cur not in seen:
            out.append(cur)
            seen.add(cur)
            cur = self.nodes[cur].parent
        return out

    def descendants(self, id) -> list:
        """All live descendants (through live children), sorted; safe on cycles."""
        out, seen, stack = [], {id}, list(self.children.get(id, ()))
        while stack:
            c = stack.pop()
            if c in seen:
                continue
            seen.add(c)
            out.append(c)
            stack.extend(self.children.get(c, ()))
        return sorted(out)

    def effective_blockers(self, id) -> list:
        """The node's own blocked_by plus every ancestor's, unique and sorted."""
        out = set(self.nodes[id].blocked_by)
        for a in self.ancestors(id):
            out.update(self.nodes[a].blocked_by)
        return sorted(out)

    def leaves_under(self, id) -> list:
        """Live leaves and stubs at or below id: the node itself if it has no live children."""
        if id not in self.nodes or self.nodes[id].superseded:
            return []
        if not self.has_children(id):
            return [id]
        return [d for d in self.descendants(id) if not self.has_children(d)]


def _where(g: Graph, ids) -> tuple:
    return tuple(g.nodes[i].path for i in ids if i in g.nodes)


def _cycle_in(edges: dict, members: set) -> list:
    """One cycle inside a strongly connected set, as a list of ids in order."""
    start = min(members)
    path, seen = [start], {start: 0}
    cur = start
    while True:
        nxt = min(n for n in edges.get(cur, ()) if n in members)
        if nxt in seen:
            return path[seen[nxt]:]
        seen[nxt] = len(path)
        path.append(nxt)
        cur = nxt


def _sccs(edges: dict) -> list:
    """Strongly connected components with more than one node (iterative Tarjan)."""
    index, low, on, stack, out, counter = {}, {}, set(), [], [], [0]
    for root in sorted(edges):
        if root in index:
            continue
        work = [(root, iter(sorted(edges.get(root, ()))))]
        index[root] = low[root] = counter[0]
        counter[0] += 1
        stack.append(root)
        on.add(root)
        while work:
            v, it = work[-1]
            advanced = False
            for w in it:
                if w not in index:
                    index[w] = low[w] = counter[0]
                    counter[0] += 1
                    stack.append(w)
                    on.add(w)
                    work.append((w, iter(sorted(edges.get(w, ())))))
                    advanced = True
                    break
                if w in on:
                    low[v] = min(low[v], index[w])
            if advanced:
                continue
            work.pop()
            if work:
                low[work[-1][0]] = min(low[work[-1][0]], low[v])
            if low[v] == index[v]:
                comp = set()
                while True:
                    w = stack.pop()
                    on.discard(w)
                    comp.add(w)
                    if w == v:
                        break
                if len(comp) > 1:
                    out.append(comp)
    return out


def _complete(g: Graph, e: Issue) -> Issue:
    """Every message names its ids and file paths: take the paths of the named nodes and add any the message does not already show."""
    paths = list(dict.fromkeys([*e.paths, *_where(g, e.ids)]))
    missing = [p for p in paths if p not in e.message]
    msg = e.message + (f" (files: {', '.join(missing)})" if missing else "")
    return Issue(e.code, msg, e.ids, tuple(paths))


def validate(g: Graph) -> tuple:
    """(errors, warnings) for the loaded graph. Schema, filename and id-format errors come from loading."""
    nodes = g.nodes
    errors, warnings = [], []

    # roots
    roots = sorted(i for i, n in nodes.items() if n.parent is None)
    if nodes and not roots:
        errors.append(Issue("no-root", "no root: every node names a parent (a root has parent: null)"))
    if len(roots) > 1:
        errors.append(Issue("multiple-roots", f"more than one root: {', '.join(roots)}", tuple(roots), _where(g, roots)))

    # parents
    for i in sorted(nodes):
        p = nodes[i].parent
        if p is not None and p not in nodes and p not in g.known:
            errors.append(Issue("parent-unresolved", f"{nodes[i].path}: node {i} has parent {p}, which does not exist", (i,), (nodes[i].path,)))
    seen_cycles = set()
    for i in sorted(nodes):
        chain, cur = [], i
        while cur is not None and cur in nodes and cur not in chain:
            chain.append(cur)
            cur = nodes[cur].parent
        if cur is not None and cur in chain:
            cyc = tuple(sorted(chain[chain.index(cur):]))
            if cyc not in seen_cycles:
                seen_cycles.add(cyc)
                errors.append(Issue("parent-cycle", f"cycle in the parent relation: {' -> '.join(chain[chain.index(cur):] + [cur])}", cyc, _where(g, cyc)))

    # blockers
    for i in sorted(nodes):
        n = nodes[i]
        anc, desc = set(g.ancestors(i)), set(g.descendants(i))
        for b in n.blocked_by:
            if b not in nodes and b not in g.known:
                errors.append(Issue("blocker-unresolved", f"{n.path}: node {i} is blocked by {b}, which does not exist", (i,), (n.path,)))
            elif b == i:
                errors.append(Issue("blocked-relative", f"{n.path}: node {i} is blocked by itself", (i,), (n.path,)))
            elif b in anc:
                errors.append(Issue("blocked-relative", f"{n.path}: node {i} is blocked by its ancestor {b}", (i, b), (n.path, nodes[b].path)))
            elif b in desc:
                errors.append(Issue("blocked-relative", f"{n.path}: node {i} is blocked by its descendant {b}", (i, b), (n.path, nodes[b].path)))
            elif b in nodes and nodes[b].superseded:
                errors.append(Issue("blocked-by-superseded", f"{n.path}: node {i} is blocked by {b}, which is superseded by {nodes[b].superseded_by}", (i, b),
                                    (n.path, nodes[b].path)))

    # blocking cycles, over leaves and stubs: interior blockers expand to their live leaves, ancestors' blockers are inherited
    edges = {}
    for i in sorted(nodes):
        if not g.live(i) or g.has_children(i):
            continue
        targets = set()
        for b in g.effective_blockers(i):
            if b in nodes:
                targets.update(t for t in g.leaves_under(b) if t != i)
        edges[i] = targets
    for comp in sorted(_sccs(edges), key=min):
        cyc = _cycle_in(edges, comp)
        errors.append(Issue("blocking-cycle", f"cycle in the blocking graph: {' -> '.join(cyc + [cyc[0]])}", tuple(sorted(cyc)), _where(g, sorted(cyc))))

    # shape of each node
    for i in sorted(nodes):
        n = nodes[i]
        if n.superseded:
            sb = n.superseded_by
            if sb not in nodes and sb not in g.known:
                errors.append(Issue("superseded-by-unresolved", f"{n.path}: node {i} is superseded by {sb}, which does not exist", (i,), (n.path,)))
            elif sb in nodes and nodes[sb].superseded:
                errors.append(Issue("superseded-by-superseded", f"{n.path}: node {i} is superseded by {sb}, which is itself superseded", (i, sb), (n.path, nodes[sb].path)))
            if g.children.get(i):
                kids = g.children[i]
                errors.append(Issue("superseded-live-children", f"{n.path}: node {i} is superseded but has children that are not: {', '.join(kids)}",
                                    (i, *kids), (n.path, *_where(g, kids))))
            continue
        extras = [name for name, present in (("stub: true", n.stub), ("done_when", n.done_when is not None), ("estimate_days", n.estimate_days is not None)) if present]
        if g.has_children(i):
            if extras:
                errors.append(Issue("interior-forbidden", f"{n.path}: node {i} has children, so it may not carry {', '.join(extras)}", (i,), (n.path,)))
        elif n.stub:
            extras = [x for x in extras if x != "stub: true"]
            if extras:
                errors.append(Issue("stub-forbidden", f"{n.path}: stub {i} may not carry {', '.join(extras)}", (i,), (n.path,)))
        else:
            missing = [name for name, present in (("done_when", n.done_when is not None), ("estimate_days", n.estimate_days is not None)) if not present]
            if missing:
                errors.append(Issue("leaf-incomplete", f"{n.path}: node {i} has no children and is not a stub, so it needs {' and '.join(missing)}", (i,), (n.path,)))
        if n.estimate_days is not None and n.estimate_days > ESTIMATE_CAP_DAYS:
            warnings.append(Issue("estimate-over-cap", f"{n.path}: node {i} estimates {n.estimate_days:g} days, above the {ESTIMATE_CAP_DAYS:g} day cap; split it", (i,), (n.path,)))
    return [_complete(g, e) for e in errors], [_complete(g, w) for w in warnings]
