"""
`fy roadmap` commands (tools/fy only dispatches here). Every command takes --root DIR (default: the repo root) and every data command
takes --json.

    validate                         print errors and warnings; exit 1 on errors
    build                            validate, then write roadmap/state.json and roadmap/STATUS.md (nothing on errors)
    show <query>                     one node: breadcrumb, fields, status and reason, criterion and its evaluation, children, blockers, dependents, references
    frontier                         every ready leaf and expandable stub, with criterion and estimate
    refs <query>                     where the node id is mentioned (log/, docs/memos/, notebook/, commit messages)
    open <query>                     open the node file in an editor (FREYJA_EDITOR, VISUAL, EDITOR, code -g, the file association)
    pin <query> | unpin <query>      add or remove a personal bookmark (roadmap/.pins.json, gitignored)
    pins                             list the pins with their current status; ids no longer in the graph are listed as dangling
    fixture --size N --out DIR       write a synthetic roadmap (seeded; --seed S; --first-layer N sets the root's branch count)
    notify --before SHA --after SHA --repo OWNER/NAME [--dry-run]   open GitHub issues for nodes that entered the frontier between two commits
    serve [--port 8765] [--focus QUERY] [--no-browser]   the local viewer (127.0.0.1 only)
    install-hooks                    git config core.hooksPath .githooks (stops if hooks already exist)

<query> is an exact id, the id without `rm.`, or a unique case-insensitive substring of an id or title.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

from . import editor, fixture, notify, pins, query, refs, render, server
from .derive import compute

REPO = Path(__file__).resolve().parents[2]
HOOKS_DIR = ".githooks"


def _parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(prog="fy roadmap", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--root", help="a repo-shaped directory containing roadmap/nodes/ (default: the repo root)")
    data = argparse.ArgumentParser(add_help=False, parents=[common])
    data.add_argument("--json", action="store_true", help="machine-readable output")
    sub = ap.add_subparsers(dest="command", required=True)
    sub.add_parser("validate", parents=[data], help="print errors and warnings")
    sub.add_parser("build", parents=[data], help="write roadmap/state.json and roadmap/STATUS.md")
    for name, helptext in (("show", "show one node"), ("refs", "list references to a node"), ("open", "open a node file in an editor"),
                           ("pin", "pin a node (a personal bookmark)"), ("unpin", "remove a pin")):
        p = sub.add_parser(name, parents=[data], help=helptext)
        p.add_argument("query")
    sub.add_parser("frontier", parents=[data], help="list the frontier")
    sub.add_parser("pins", parents=[data], help="list the pins with their status")
    fx = sub.add_parser("fixture", parents=[common], help="generate a synthetic roadmap")
    fx.add_argument("--size", type=int, required=True)
    fx.add_argument("--out", required=True)
    fx.add_argument("--seed", type=int, default=0)
    fx.add_argument("--first-layer", type=int, default=None, help="number of first-layer branches under the root (default: 5 to 10, seeded)")
    nt = sub.add_parser("notify", parents=[common], help="open issues for nodes that entered the frontier between two commits")
    nt.add_argument("--before", required=True, help="the commit before the push (all zeros or unknown: nothing is opened)")
    nt.add_argument("--after", required=True, help="the commit after the push")
    nt.add_argument("--repo", required=True, help="OWNER/NAME, for the links in the issue bodies")
    nt.add_argument("--dry-run", action="store_true", help="print the issues instead of creating them; gh is not called")
    sv = sub.add_parser("serve", parents=[common], help="serve the local roadmap viewer on 127.0.0.1")
    sv.add_argument("--port", type=int, default=server.DEFAULT_PORT)
    sv.add_argument("--focus", help="open on this node (the same query rules as show)")
    sv.add_argument("--no-browser", action="store_true", help="print the URL without opening a browser")
    sub.add_parser("install-hooks", parents=[common], help="enable .githooks for this clone")
    return ap


def _issue_lines(label, items):
    return [f"{label} {x.code}: {x.message}" for x in items]


def _resolve(rm, q, say):
    status, got = query.search(rm, q)
    if status == "ok":
        return got[0]
    if status == "ambiguous":
        say(f"{q!r} matches {len(got)} nodes" + (f" (showing {query.MAX_CANDIDATES})" if len(got) > query.MAX_CANDIDATES else "") + "; be more specific:")
        got = got[:query.MAX_CANDIDATES]
    else:
        say(f"no node matches {q!r}." + (" Close ids:" if got else ""))
    for c in got:
        say(f"  {c}  {rm.nodes[c].title}")
    return None


def _breadcrumb(rm, id) -> list:
    return [*reversed(rm.graph.ancestors(id)), id]


def node_detail(rm, root, id, with_refs=True) -> dict:
    """Everything `show` prints, as plain data."""
    n, st = rm.nodes[id], rm.states[id]
    return {
        "id": id, "breadcrumb": _breadcrumb(rm, id), "kind": st.kind, "status": st.status, "reason": st.reason, "title": n.title, "path": n.path,
        "fields": {"parent": n.parent, "blocked_by": sorted(n.blocked_by), "stub": n.stub, "estimate_days": n.estimate_days, "tags": list(n.tags),
                   "active": n.active, "signed_off": n.signed_off, "superseded_by": n.superseded_by},
        "done_when": n.done_when, "evaluation": st.evaluation.to_dict() if st.evaluation else None,
        "children": [{"id": c, "status": rm.status(c), "title": rm.nodes[c].title} for c in rm.children(id)],
        "effective_blockers": rm.effective_blockers(id), "uncleared_blockers": rm.uncleared(id),
        "dependents": [{"id": d, "status": rm.status(d), "title": rm.nodes[d].title} for d in rm.dependents(id)],
        "references": refs.references(root, id) if with_refs else {"files": [], "commits": []}, "body": n.body}


def _show_text(d) -> list:
    out = [" > ".join(d["breadcrumb"]), "", f"{d['title']}", f"  id:      {d['id']}", f"  file:    {d['path']}", f"  kind:    {d['kind']}",
           f"  status:  {d['status']} ({d['reason']})"]
    f = d["fields"]
    if f["estimate_days"] is not None:
        out.append(f"  estimate: {f['estimate_days']:g} days")
    if f["tags"]:
        out.append(f"  tags:    {', '.join(f['tags'])}")
    if f["active"]:
        out.append("  active:  yes")
    if f["superseded_by"]:
        out.append(f"  superseded by: {f['superseded_by']}")
    out.append(f"  done_when: {render.criterion_text(d['done_when']) if d['done_when'] else 'none'}")
    ev = d["evaluation"]
    if ev:
        out.append(f"  evaluation: {ev['result']} - {ev['reason']}" + (f" [measured {ev['measured']:g}]" if ev["measured"] is not None else ""))
    out += ["", f"children ({len(d['children'])}):"] + [f"  {c['id']}  [{c['status']}]  {c['title']}" for c in d["children"]]
    out += ["", f"effective blockers ({len(d['effective_blockers'])}): {', '.join(d['effective_blockers']) or 'none'}",
            f"uncleared blockers: {', '.join(d['uncleared_blockers']) or 'none'}", "", f"dependents ({len(d['dependents'])}):"]
    out += [f"  {c['id']}  [{c['status']}]  {c['title']}" for c in d["dependents"]]
    r = d["references"]
    out += ["", f"references ({len(r['files'])} in files, {len(r['commits'])} in commits):"]
    out += [f"  {x['path']}:{x['line']}: {x['text']}" for x in r["files"]] + [f"  {x['hash']} {x['subject']}" for x in r["commits"]]
    return out


def install_hooks(root, say) -> int:
    root = Path(root)
    if not (root / ".git").exists():
        say(f"{root} is not a git repository root; nothing changed.")
        return 1
    git = lambda *a: subprocess.run(["git", *a], cwd=root, capture_output=True, text=True, encoding="utf-8")  # noqa: E731
    current = git("config", "--get", "core.hooksPath").stdout.strip()
    if current == HOOKS_DIR:
        say(f"core.hooksPath is already {HOOKS_DIR}; nothing to do.")
        return 0
    if current:
        say(f"core.hooksPath is already set to {current!r}; not changing it. Merge {HOOKS_DIR}/pre-commit into those hooks yourself.")
        return 1
    existing = sorted(p.name for p in (root / ".git" / "hooks").glob("*") if p.is_file() and not p.name.endswith(".sample")) if (root / ".git" / "hooks").is_dir() else []
    if existing:
        say(f".git/hooks already holds {', '.join(existing)}; not changing core.hooksPath (it would stop them running). Merge {HOOKS_DIR}/pre-commit in by hand.")
        return 1
    if not (root / HOOKS_DIR / "pre-commit").is_file():
        say(f"{HOOKS_DIR}/pre-commit is missing under {root}; nothing changed.")
        return 1
    git("config", "core.hooksPath", HOOKS_DIR)
    say(f"set core.hooksPath to {HOOKS_DIR} for this clone.")
    return 0


def _pins_command(cmd, ns, root, say, as_json) -> int:
    rm = compute(root)
    try:
        if cmd == "pins":
            rows = []
            for id in pins.load(root):
                n = rm.nodes.get(id)
                rows.append({"id": id, "status": rm.status(id) if n else "dangling", "title": n.title if n else None})
            if as_json:
                say(json.dumps(rows, indent=2, sort_keys=True))
            elif not rows:
                say("no pins")
            for r in rows if not as_json else []:
                say(f"{r['id']}  {r['status']}  {r['title']}" if r["title"] is not None else f"{r['id']}  DANGLING (no such node in the roadmap; `fy roadmap unpin {r['id']}` removes it)")
            return 0
        if cmd == "unpin" and ns.query.strip() in pins.load(root) and ns.query.strip() not in rm.nodes:
            id = ns.query.strip()  # a dangling pin is removed by its exact id
        else:
            id = _resolve(rm, ns.query, say)
            if id is None:
                return 1
        if cmd == "pin":
            say(f"pinned {id}" if pins.add(root, id) else f"{id} is already pinned")
        else:
            say(f"unpinned {id}" if pins.remove(root, id) else f"{id} was not pinned")
    except pins.PinsError as e:
        say(f"{cmd}: {e}")
        return 1
    return 0


def main(argv=None, say=print, opener=None, default_root=None) -> int:
    ns = _parser().parse_args(list(sys.argv[1:] if argv is None else argv))
    cmd = ns.command
    if cmd == "fixture":
        try:
            fixture.generate(ns.size, ns.out, seed=ns.seed, first_layer=ns.first_layer)
        except (FileExistsError, ValueError) as e:
            say(f"fixture: {e}")
            return 1
        say(f"wrote a {ns.size}-node fixture (seed {ns.seed}) to {ns.out}")
        return 0
    root = Path(ns.root or default_root or REPO)
    if cmd == "install-hooks":
        return install_hooks(root, say)
    if cmd == "serve":
        return server.serve(root, ns.port, ns.focus, browser=not ns.no_browser, say=say)
    if cmd == "notify":
        return notify.run(root, ns.before, ns.after, ns.repo, dry_run=ns.dry_run, say=say)
    as_json = getattr(ns, "json", False)

    if cmd == "build":
        rm = render.build(root)
        if rm is None:
            for line in _issue_lines("error", compute(root).errors):
                say(line)
            say("roadmap not built: fix the errors above.")
            return 1
        for line in _issue_lines("warning", rm.warnings):
            say(line)
        say(f"wrote {render.STATE_JSON} and {render.STATUS_MD}: {rm.summary_line()[len('roadmap: '):]}")
        return 0

    if cmd in ("pin", "unpin", "pins"):
        return _pins_command(cmd, ns, root, say, as_json)

    rm = compute(root)
    if cmd == "validate":
        if as_json:
            say(json.dumps({"errors": [e.to_dict() for e in rm.errors], "warnings": [w.to_dict() for w in rm.warnings], "node_count": rm.node_count},
                           indent=2, sort_keys=True))
        else:
            for line in _issue_lines("error", rm.errors) + _issue_lines("warning", rm.warnings):
                say(line)
            say(f"{len(rm.errors)} errors, {len(rm.warnings)} warnings" + ("; no nodes" if not rm.nodes else f"; {rm.node_count} nodes"))
        return 1 if rm.errors else 0

    if cmd == "frontier":
        rows = []
        for i in rm.frontier:
            n = rm.nodes[i]
            rows.append({"id": i, "kind": rm.kind(i), "title": n.title, "done_when": n.done_when, "estimate_days": n.estimate_days})
        if as_json:
            say(json.dumps(rows, indent=2, sort_keys=True))
        else:
            say(f"frontier: {len(rows)} ({sum(r['kind'] == 'leaf' for r in rows)} ready leaves, {sum(r['kind'] == 'stub' for r in rows)} expandable stubs)")
            for r in rows:
                crit = render.criterion_text(r["done_when"]) if r["done_when"] else "stub"
                est = f"{r['estimate_days']:g} d" if r["estimate_days"] is not None else "-"
                say(f"  {r['id']}  {est:>6}  {crit}  |  {r['title']}")
        return 0

    id = _resolve(rm, ns.query, say)
    if id is None:
        return 1
    if cmd == "show":
        d = node_detail(rm, root, id)
        say(json.dumps(d, indent=2, sort_keys=True) if as_json else "\n".join(_show_text(d)))
    elif cmd == "refs":
        r = refs.references(root, id)
        if as_json:
            say(json.dumps(r, indent=2, sort_keys=True))
        else:
            say(f"{id}: {len(r['files'])} in files, {len(r['commits'])} in commits")
            for x in r["files"]:
                say(f"  {x['path']}:{x['line']}: {x['text']}")
            for x in r["commits"]:
                say(f"  {x['hash']} {x['subject']}")
    elif cmd == "open":
        try:
            (opener or editor.open_file)(editor.node_file(root, rm.nodes[id].path))
        except (OSError, ValueError) as e:
            say(f"open: {e}")
            return 1
        say(f"opened {rm.nodes[id].path}")
    return 0
