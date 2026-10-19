"""
`fy thread` commands (tools/fy only dispatches here). Every command takes --root DIR (default: the repo root).

    fixture --out DIR [--seed N] [--scenario general|reallocation]   write a synthetic repo-shaped root (deterministic, never into a non-empty directory)
    impact [<address>] [--edit <address>=<YAML value> ...] [--json]   the work items and outputs an address touches; with --edit, the in-memory what-if.
                                                                      Writes nothing. Either an address or at least one --edit is needed.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import fixture, impact as impact_mod
from . import store as st

REPO = Path(__file__).resolve().parents[2]


def _parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(prog="fy thread", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--root", help="a repo-shaped directory containing thread/ (default: the repo root)")
    sub = ap.add_subparsers(dest="command", required=True)
    fx = sub.add_parser("fixture", parents=[common], help="generate a synthetic thread")
    fx.add_argument("--out", required=True)
    fx.add_argument("--seed", type=int, default=0)
    fx.add_argument("--scenario", choices=("general", "reallocation"), default="general")
    im = sub.add_parser("impact", parents=[common], help="impact of an address, or the in-memory what-if")
    im.add_argument("address", nargs="?")
    im.add_argument("--edit", action="append", default=[], metavar="ADDRESS=VALUE")
    im.add_argument("--json", action="store_true")
    return ap


def _root(args, default_root) -> Path:
    return Path(args.root) if args.root else Path(default_root or REPO)


def cmd_fixture(args, default_root, say) -> int:
    try:
        if args.scenario == "reallocation":
            info = fixture.reallocation(args.out)
            say(f"wrote the reallocation fixture to {args.out} (M1 {info['m1_kg']} kg and M2 {info['m2_kg']} kg per side)")
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


def main(argv=None, default_root=None, say=print) -> int:
    args = _parser().parse_args(argv)
    return {"fixture": cmd_fixture, "impact": cmd_impact}[args.command](args, default_root, say)


if __name__ == "__main__":
    sys.exit(main())
