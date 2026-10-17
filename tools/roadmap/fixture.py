"""
Roadmap fixture generator: `fy roadmap fixture --size N --out DIR` writes a repo-shaped root holding a valid synthetic roadmap, with the
records its criteria read and the status it intended for each node in fixture-intent.json.

Deterministic for a given (size, seed). It is deliberately independent of the rest of the library: the records and blockers are built from
intents (a leaf is meant to be done, ready, active, blocked or expandable) and the intended status of every interior node comes from the
rules written out again here over those intents, so that comparing the library's derived statuses with the sidecar is a real test.
The root has 5 to 10 first-layer branches (`first_layer` overrides the count) of uneven size, each named for a different noun. The tree
has depth up to 8 (the root is depth 0), uneven branching, cross-branch blockers, stubs and retired nodes. Every status appears
once the roadmap has a few dozen nodes. Fixtures are not committed; tests generate them into a temporary directory.
"""
from __future__ import annotations

import json
import random
from pathlib import Path

import yaml

MAX_DEPTH = 8
MIN_SIZE = 8
NOUNS = ["actuator", "bearing", "cable", "pelvis", "femur", "ankle", "sensor", "harness", "driver", "gearbox", "spring", "bracket",
         "encoder", "battery", "controller", "mount", "knee", "wrist", "spine", "cooling"]
PHRASES = ["selected and decision recorded", "characterised and report filed", "validated against the model", "assembled and torque tested",
           "specified in the sheet", "benchmarked on the bench", "reviewed and signed off", "fitted inside the envelope"]
TAGS = ["arm", "leg", "torso", "actuation", "sensing", "power", "software", "cad"]
CRITERIA = ["artifact", "decision", "check", "metric", "manual"]
CRITERIA_WEIGHTS = [3, 2, 2, 3, 2]
FIXTURE_SCHEMA = {"$schema": "https://json-schema.org/draft/2020-12/schema", "type": "object", "required": ["ok"], "properties": {"ok": {"const": True}}}
OPS = ["<", "<=", ">", ">=", "=="]


def _dump(path: Path, text: str):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)


def _node_file(path: Path, front: dict, body: str):
    _dump(path, "---\n" + yaml.safe_dump(front, sort_keys=True) + "---\n" + body)


def generate(size: int, out, seed: int = 0, first_layer: int | None = None) -> dict:
    """Write the fixture under `out` (which must be absent or empty). Returns the intended statuses {id: status}."""
    if size < MIN_SIZE:
        raise ValueError(f"size must be at least {MIN_SIZE}")
    out = Path(out)
    if out.exists() and any(out.iterdir()):
        raise FileExistsError(f"{out} is not empty")
    rng = random.Random(seed)
    n_super = max(1, size // 20)
    n = size - n_super  # live nodes, indexed 0..n-1; 0 is the root

    if first_layer is None:
        k = min(rng.randint(5, 10), n - 1)
    elif 1 <= first_layer <= n - 1:
        k = first_layer
    else:
        raise ValueError(f"--first-layer must be between 1 and {n - 1} for {size} nodes (it is {first_layer})")

    # ---- the tree: k first-layer branches of uneven weight; inside a branch, preferential attachment toward busy and deep nodes gives
    # uneven branching and a long spine
    parent, depth, kids = [None], [0], [[]]
    members = []  # the nodes of each branch, its head first
    for b in range(k):
        parent.append(0)
        depth.append(1)
        kids.append([])
        kids[0].append(1 + b)
        members.append([1 + b])
    branch_weight = [rng.lognormvariate(0, 1.0) for _ in range(k)]
    for idx in range(k + 1, n):
        b = rng.choices(range(k), branch_weight)[0]
        eligible = [i for i in members[b] if depth[i] < MAX_DEPTH]
        weights = [(1 + len(kids[i])) ** 1.3 * (1 + depth[i]) ** 1.6 for i in eligible]
        p = rng.choices(eligible, weights)[0]
        parent.append(p)
        depth.append(depth[p] + 1)
        kids.append([])
        kids[p].append(idx)
        members[b].append(idx)
    ids = [f"rm.n{i:03d}-{rng.choice(NOUNS)}" for i in range(n)]
    ids[0] = "rm.n000-root"
    head_nouns = rng.sample(NOUNS, min(k, len(NOUNS)))  # a different noun for each branch, so titles are distinct at a glance
    for b, noun in enumerate(head_nouns):
        ids[1 + b] = f"rm.n{1 + b:03d}-{noun}"

    # ---- depth-first leaf order: every node covers a contiguous run [lo, hi] of it
    leaf_order, lo, hi = [], [0] * n, [0] * n

    def walk(i):
        lo[i] = len(leaf_order)
        if not kids[i]:
            leaf_order.append(i)
        for c in kids[i]:
            walk(c)
        hi[i] = len(leaf_order) - 1

    walk(0)
    leaves = [i for i in range(n) if not kids[i]]

    def under(i):
        return leaf_order[lo[i]:hi[i] + 1]

    # ---- intents for the leaves and stubs
    is_stub = {i: rng.random() < 0.12 for i in leaves}
    intent = {}
    for i in leaves:
        if is_stub[i]:
            intent[i] = "expandable" if rng.random() < 0.65 else "blocked"
        else:
            intent[i] = rng.choices(["done", "ready", "active", "blocked"], [0.32, 0.22, 0.10, 0.36])[0]

    def done_node(i):  # a node is done when every leaf under it is done (a stub never is)
        return all(intent[l] == "done" for l in under(i))

    own = {i: [] for i in range(n)}

    def eff(i):
        out_, cur = list(own[i]), parent[i]
        while cur is not None:
            out_ += own[cur]
            cur = parent[cur]
        return out_

    # ---- blocking edges: a blocker lies entirely before the node in leaf order, so the graph cannot cycle
    for _ in range(3 * n):
        x, b = rng.randrange(1, n), rng.randrange(1, n)
        if hi[b] >= lo[x] or b in own[x] or len(own[x]) >= 2:
            continue
        if done_node(b) or all(intent[l] == "blocked" for l in under(x)):
            own[x].append(b)
    for l in leaf_order:  # a blocked leaf must have an uncleared blocker; otherwise it cannot be blocked
        if intent[l] != "blocked" or any(not done_node(b) for b in eff(l)):
            continue
        options = [b for b in range(1, n) if hi[b] < lo[l] and not done_node(b)]
        if options:
            own[l].append(rng.choice(options))
        else:
            intent[l] = "expandable" if is_stub[l] else "ready"

    # ---- intended status of every live node
    status = {}
    for i in range(n):
        if not kids[i]:
            status[i] = intent[i]
        elif done_node(i):
            status[i] = "done"
        elif any(not done_node(b) for b in eff(i)):
            status[i] = "blocked"
        elif any(intent[l] in ("done", "active") for l in under(i)):
            status[i] = "in_progress"
        else:
            status[i] = "not_started"

    # ---- retired nodes: extra leaves under interior nodes, pointing at a live leaf
    interior = [i for i in range(n) if kids[i]]
    sup = []
    for k in range(n_super):
        sid = f"rm.n{n + k:03d}-{rng.choice(NOUNS)}-retired"
        sup.append((sid, ids[rng.choice(interior)], ids[rng.choice(leaves)]))

    # ---- records and node files
    meta = {}  # which check ids are listed, and how
    checks = {}
    decision_no = [0]
    unknown = []  # leaves whose evidence cannot be read or expected: they evaluate unknown and draw a criterion-unknown warning
    awaiting = []  # leaves whose evidence does not exist yet (absent file in an existing directory, checks not run): no warning
    log_ids = []

    def criterion(i, done):
        """(done_when, signed_off) for a leaf, and the files that make it pass (done) or not."""
        slug = ids[i][3:]
        kind = rng.choices(CRITERIA, CRITERIA_WEIGHTS)[0]
        if kind == "manual":
            return {"type": "manual"}, done
        if kind == "artifact":
            rel = f"records/artifacts/{slug}.json"
            dw = {"type": "artifact", "path": rel}
            if rng.random() < 0.5:
                dw["schema"] = "docs/schemas/fixture-artifact.json"
            how = "good" if done else rng.choice(["missing", "empty", "bad", "nodir"])
            if how == "nodir":  # the directory is never created: nothing says where the file would appear
                dw["path"] = f"records/pending/{slug}.json"
                unknown.append(ids[i])
            if how == "missing":
                (out / "records" / "artifacts").mkdir(parents=True, exist_ok=True)
                awaiting.append(ids[i])
            if how == "good":
                _dump(out / rel, json.dumps({"ok": True, "id": slug}, sort_keys=True) + "\n")
            elif how == "empty":
                _dump(out / rel, "")
            elif how == "bad":
                _dump(out / rel, json.dumps({"ok": False, "id": slug}, sort_keys=True) + "\n")
                dw["schema"] = "docs/schemas/fixture-artifact.json"  # the empty-or-not distinction only matters with a schema
            return dw, False
        if kind == "decision":
            decision_no[0] += 1
            rel = f"decisions/{decision_no[0]:04d}-{slug}.md"
            how = "accepted" if done else rng.choice(["proposed", "missing", "superseded", "nostatus"])
            if how == "missing":
                awaiting.append(ids[i])
            elif how == "nostatus":
                unknown.append(ids[i])
                _dump(out / rel, f"---\nid: adr-{decision_no[0]:04d}\ndate: 2026-01-01\nlinks: []\n---\n## Context\n")
            else:
                st = "accepted" if how == "accepted" else ("proposed" if how == "proposed" else '"superseded-by: adr-9999"')
                _dump(out / rel, f"---\nid: adr-{decision_no[0]:04d}\nstatus: {st}\ndate: 2026-01-01\nlinks: []\n---\n## Context\n")
            return {"type": "decision", "record": rel}, False
        if kind == "check":
            cid = f"check.fixture.{slug}"
            how = "PASS" if done else rng.choice(["FAIL", "WAIVED", "absent", "NOT_RUN"])
            if how == "absent":
                unknown.append(ids[i])  # listed nowhere in docs/STATE.md
            else:
                checks[cid] = how
                if how == "NOT_RUN":
                    awaiting.append(ids[i])
            return {"type": "check", "check": cid}, False
        rel = f"records/metrics/{slug}.json"  # metric
        op = rng.choice(OPS)
        t = round(rng.uniform(0.5, 9.5), 2)
        good = {"<": t / 2, "<=": t, ">": t * 2, ">=": t, "==": t}[op]
        bad = {"<": t * 2, "<=": t * 2, ">": t / 2, ">=": t / 2, "==": t + 1}[op]
        how = "good" if done else rng.choice(["bad", "missing", "nopointer", "corrupt"])
        if how == "missing":
            (out / "records" / "metrics").mkdir(parents=True, exist_ok=True)
            awaiting.append(ids[i])
        if how == "corrupt":
            _dump(out / rel, "{not json\n")
        if how in ("good", "bad"):
            _dump(out / rel, json.dumps({"result": {"value": round(good if how == "good" else bad, 4)}}, sort_keys=True) + "\n")
        elif how == "nopointer":
            _dump(out / rel, json.dumps({"result": {}}) + "\n")
        if how in ("nopointer", "corrupt"):
            unknown.append(ids[i])
        return {"type": "metric", "record": rel, "pointer": "/result/value", "op": op, "value": t, "units": "arb"}, False

    lrng = random.Random(f"labels-{seed}")  # short labels come from their own stream, so adding them moved nothing else in the fixture
    for i in range(n):
        front = {"schema": "roadmap-node/1", "id": ids[i], "parent": ids[parent[i]] if parent[i] is not None else None}
        if (parent[i] == 0 or (i and lrng.random() < 0.2)):  # every first-layer branch has a short label, and about one node in five below them
            front["schema"] = "roadmap-node/2"
            front["short"] = ids[i].split("-", 1)[-1].capitalize()
        noun = ids[i].split("-", 1)[-1]
        front["title"] = f"{noun.capitalize()} {i:03d} {rng.choice(PHRASES)}" if i else "Freyja v1 walks indoors at 1.4 m/s"
        if own[i]:
            front["blocked_by"] = sorted(ids[b] for b in own[i])
        if rng.random() < 0.5:
            front["tags"] = sorted(rng.sample(TAGS, rng.randint(1, 2)))
        if not kids[i]:
            if is_stub[i]:
                front["stub"] = True
            else:
                front["estimate_days"] = rng.choice([0.5, 1, 1.5, 2, 2.5, 3])
                front["done_when"], signed = criterion(i, intent[i] == "done")
                if front["done_when"]["type"] == "manual":
                    front["signed_off"] = bool(signed)
                if intent[i] == "active":
                    front["active"] = True
        _node_file(out / "roadmap" / "nodes" / f"{ids[i]}.md", front, f"Fixture node {i}.\n")
    for sid, par, new in sup:
        front = {"schema": "roadmap-node/1", "id": sid, "parent": par, "title": f"{sid[3:]} retired", "superseded_by": new,
                 "estimate_days": 1, "done_when": {"type": "manual"}}
        _node_file(out / "roadmap" / "nodes" / f"{sid}.md", front, "Retired fixture node.\n")

    # ---- shared records: the artifact schema, the recorded check results, and files that mention ids
    _dump(out / "docs" / "schemas" / "fixture-artifact.json", json.dumps(FIXTURE_SCHEMA, sort_keys=True, indent=2) + "\n")
    lines = [f"- {c} | gate | {s}" for c, s in sorted(checks.items())]
    _dump(out / "docs" / "STATE.md", "<!-- fixture -->\n\nSTATE: fixture\n\n## Checks\n\n" + "\n".join(lines) + "\n\n## Waivers\n\nnone\n")
    mentioned = [ids[i] for i in range(n) if rng.random() < 0.4]
    log = [f"event {k:03d} touched {m}" + (" and " + m + "-extra" if k % 5 == 0 else "") for k, m in enumerate(mentioned)]
    _dump(out / "log" / "events.log", "\n".join(log) + "\n")
    _dump(out / "docs" / "memos" / "memo1-fixture.md", "# Fixture memo\n\n" + "\n".join(f"Discussed {m}." for m in mentioned[::3]) + "\n")
    _dump(out / "notebook" / "2026-01-01-fixture.md", "---\norigin: me\n---\n" + "\n".join(f"- see {m}, and also {m}" for m in mentioned[1::4]) + "\n")
    _dump(out / "decisions" / "README.md", "Fixture decisions.\n")

    intended = {ids[i]: status[i] for i in range(n)}
    intended.update({sid: "superseded" for sid, _, _ in sup})
    _dump(out / "fixture-intent.json", json.dumps({"seed": seed, "size": size, "awaiting_criteria": sorted(awaiting), "unknown_criteria": sorted(unknown), "statuses": dict(sorted(intended.items()))}, indent=2, sort_keys=True) + "\n")
    return intended
