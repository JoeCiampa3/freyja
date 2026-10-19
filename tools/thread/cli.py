"""
`fy thread` commands (tools/fy only dispatches here). Every command takes --root DIR (default: the repo root).

    validate [--json]                       errors and warnings; exit 1 on errors
    build                                   validate, then write the generated outputs under thread/ (nothing on errors; exit 1)
    show <query> [--json]                   one record's derived view in the terminal
    impact [<address>] [--edit <address>=<YAML value> ...] [--json]   the work items and outputs an address touches; with --edit, the
                                            in-memory what-if. Writes nothing. Either an address or at least one --edit is needed.
    why <work query> [--json]               a work item's status and, for each moved address, the stamped value against the current one
    stamp <work query> [--note TEXT] [--pin] [--by NAME]   write a stamp for the work item's current `consumes`; refuses when the work item
                                            is unknown, an address does not resolve, or the thread has errors
    fixture --out DIR [--seed N] [--scenario general|reallocation]   write a synthetic repo-shaped root (deterministic, never into a non-empty directory)

<query> is an exact id, the id with a kind prefix (seg. jnt. part. if. lc. hn. work.) added, or a unique case-insensitive substring of an id.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

from . import addr, build, fixture, query
from . import impact as impact_mod
from . import store as st

REPO = Path(__file__).resolve().parents[2]


def _parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(prog="fy thread", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--root", help="a repo-shaped directory containing thread/ (default: the repo root)")
    data = argparse.ArgumentParser(add_help=False, parents=[common])
    data.add_argument("--json", action="store_true", help="machine-readable output")
    sub = ap.add_subparsers(dest="command", required=True)
    sub.add_parser("validate", parents=[data], help="print errors and warnings")
    sub.add_parser("build", parents=[common], help="write the generated outputs")
    sh = sub.add_parser("show", parents=[data], help="show one record")
    sh.add_argument("query")
    wy = sub.add_parser("why", parents=[data], help="why a work item has its status")
    wy.add_argument("query")
    sp = sub.add_parser("stamp", parents=[common], help="stamp a work item")
    sp.add_argument("query")
    sp.add_argument("--note", default="")
    sp.add_argument("--pin", action="store_true")
    sp.add_argument("--by")
    fx = sub.add_parser("fixture", parents=[common], help="generate a synthetic thread")
    fx.add_argument("--out", required=True)
    fx.add_argument("--seed", type=int, default=0)
    fx.add_argument("--scenario", choices=("general", "reallocation"), default="general")
    im = sub.add_parser("impact", parents=[data], help="impact of an address, or the in-memory what-if")
    im.add_argument("address", nargs="?")
    im.add_argument("--edit", action="append", default=[], metavar="ADDRESS=VALUE")
    return ap


def _root(args, default_root) -> Path:
    return Path(args.root) if args.root else Path(default_root or REPO)


def summary_line(b) -> str:
    rework = sum(1 for w in b.work.values() if w["status"] in ("stale", "drifted", "unknown"))
    return f"{len(b.recs)} records | {len(b.work)} work items | rework {rework} | errors {len(b.errors)} | warnings {len(b.warnings)}"


def _issues(b, say):
    for i in sorted(b.issues, key=lambda i: (i.level != "error", i.code, i.ids, i.message)):
        say(f"{i.level} {i.code}: {i.message}")


def _load(args, default_root, say):
    """(root, Build) or None when the root has no thread/ directory (said once)."""
    root = _root(args, default_root)
    if not (root / "thread").is_dir():
        say(f"fy thread: no thread/ directory under {root}; nothing to do")
        return None
    return root, build.build_root(root)


def cmd_validate(args, default_root, say) -> int:
    got = _load(args, default_root, say)
    if got is None:
        return 0
    b = got[1]
    if args.json:
        say(json.dumps({"errors": [i.to_dict() for i in b.errors], "warnings": [i.to_dict() for i in b.warnings], "summary": summary_line(b)}, indent=2, sort_keys=True))
    else:
        _issues(b, say)
        say(summary_line(b))
    return 1 if b.errors else 0


def cmd_build(args, default_root, say) -> int:
    got = _load(args, default_root, say)
    if got is None:
        return 0
    root, b = got
    if b.errors:
        _issues(b, say)
        say(f"fy thread: {len(b.errors)} error(s); nothing written")
        return 1
    changed = build.write_outputs(root, b)
    for i in b.warnings:
        say(f"warning {i.code}: {i.message}")
    say(f"wrote thread/: {len(b.outputs)} files, {len(changed)} changed | {summary_line(b)}")
    return 0


def _pick(b, q, say, want_kind=None):
    status, got = query.resolve(b, q)
    if status == "ok":
        if want_kind and b.recs[got]["kind"] != want_kind:
            say(f"fy thread: {got} is not a work item ({b.recs[got]['kind']})")
            return None
        return got
    if status == "ambiguous":
        say(f"fy thread: {q!r} is ambiguous: {', '.join(got)}")
    else:
        say(f"fy thread: no record matches {q!r}" + (f"; close: {', '.join(got)}" if got else ""))
    return None


def cmd_show(args, default_root, say) -> int:
    got = _load(args, default_root, say)
    if got is None:
        return 0
    b = got[1]
    if b.errors:
        _issues(b, say)
        return 1
    id = _pick(b, args.query, say)
    if id is None:
        return 2
    if args.json:
        say(json.dumps(b.docs[id], indent=2, sort_keys=True, ensure_ascii=False))
        return 0
    text = b.outputs[f"thread/dossiers/{id}.md"].decode().split("\n", 1)[1]
    say(text.split("## References")[0].strip("\n"))
    return 0


def cmd_why(args, default_root, say) -> int:
    got = _load(args, default_root, say)
    if got is None:
        return 0
    b = got[1]
    if b.errors:
        _issues(b, say)
        return 1
    id = _pick(b, args.query, say, "work_item")
    if id is None:
        return 2
    w = b.work[id]
    if args.json:
        say(json.dumps({"id": id, **w}, indent=2, sort_keys=True, ensure_ascii=False))
        return 0
    say(f"{id}: {w['status']}" + (f" (baseline stamp {w['stamp']}{', pinned' if w['pinned'] else ''})" if w["stamp"] else " (no stamp yet)"))
    if w["status"] == "current":
        say("every stamped address hashes as it did when stamped")
    for m in w["moved"]:
        say(f"  {m['address']}")
        say(f"    stamped: {_full(m['stamped'], m['stamped_hash'])}")
        say(f"    current: {'does not resolve' if m['current_hash'] is None else _full(m['current'], m['current_hash'])}")
    return 0


def _full(value, hash) -> str:
    return f"{addr.canonical(value)}  (hash {hash})" if value is not None else f"(value not stored, hash {hash})"


def _by(args) -> str:
    if args.by:
        return args.by
    try:
        name = subprocess.run(["git", "config", "user.name"], capture_output=True, text=True, check=True).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        name = ""
    return name or "unknown"


def cmd_stamp(args, default_root, say) -> int:
    got = _load(args, default_root, say)
    if got is None:
        return 1
    root, b = got
    if b.errors:
        _issues(b, say)
        say("fy thread: refused: the thread has errors; nothing stamped")
        return 1
    id = _pick(b, args.query, say, "work_item")
    if id is None:
        say("fy thread: refused: no such work item; nothing stamped")
        return 1
    try:
        path = build.write_stamp(root, b, id, note=args.note, pinned=args.pin, by=_by(args))
    except ValueError as e:
        say(f"fy thread: refused: {e}")
        return 1
    doc = json.loads(path.read_text(encoding="utf-8"))
    say(f"stamped {id} as {doc['stamp']}{' (pinned)' if doc['pinned'] else ''}; it consumed:")
    for c in doc["consumes"]:
        say(f"  {c['address']}  hash {c['hash']}")
    return 0


def cmd_fixture(args, default_root, say) -> int:
    try:
        if args.scenario == "reallocation":
            info = fixture.reallocation(args.out)
            say(f"wrote the reallocation fixture to {args.out} (M1 {info['m1_kg']} kg and M2 {info['m2_kg']} kg per unit)")
        else:
            intent = fixture.generate(args.out, args.seed)
            say(f"wrote the fixture to {args.out} (seed {args.seed}; {len(intent)} work items: {', '.join(sorted(set(intent.values())))})")
    except ValueError as e:
        say(f"fy thread: {e}")
        return 1
    return 0


def cmd_impact(args, default_root, say) -> int:
    if not args.address and not args.edit:
        say("fy thread impact: give an address, or at least one --edit ADDRESS=VALUE")
        return 2
    store = st.load(_root(args, default_root))
    out = {}
    try:
        if args.address:
            out["impact"] = impact_mod.impact(store, args.address)
        if args.edit:
            out["whatif"] = impact_mod.whatif(store, args.edit)
    except ValueError as e:
        say(f"fy thread impact: {e}")
        return 2
    if args.json:
        say(json.dumps(out, indent=2, sort_keys=True))
        return 0
    if "impact" in out:
        i = out["impact"]
        say(f"impact of {i['address']}")
        say(f"  work items ({len(i['work'])}): {', '.join(i['work']) or 'none'}")
        say(f"  outputs built from its source ({len(i['outputs'])}):")
        for p in i["outputs"]:
            say(f"    {p}")
    if "whatif" in out:
        w = out["whatif"]
        say("what-if (nothing is written): " + "; ".join(w["edits"]))
        if w["errors"]:
            say(f"  the edit would cause {len(w['errors'])} error(s), so nothing would be generated:")
            for e in w["errors"]:
                say(f"    {e['code']}: {e['message']}")
            return 1
        say(f"  outputs that would change ({len(w['outputs_changed'])}):")
        for p in w["outputs_changed"]:
            say(f"    {p}")
        say(f"  work status changes ({len(w['status_changes'])}):")
        for k, v in w["status_changes"].items():
            say(f"    {k}: {v['from']} -> {v['to']}")
        for e in w["warnings"]:
            say(f"  new warning {e['code']}: {e['message']}")
    return 0


COMMANDS = {"validate": cmd_validate, "build": cmd_build, "show": cmd_show, "why": cmd_why, "stamp": cmd_stamp, "fixture": cmd_fixture, "impact": cmd_impact}


def main(argv=None, default_root=None, say=print) -> int:
    args = _parser().parse_args(argv)
    return COMMANDS[args.command](args, default_root, say)


if __name__ == "__main__":
    sys.exit(main())
