"""
`fy cad` commands (tools/fy only dispatches here). Every command takes --root DIR (default: the repo root).

    validate [<part id>]                   the binding against its schema and the bound document's parameters against the binding; exit 1 on a problem
    push <part id>                         set the inherited parameters from their addresses by expression; on a failed regeneration roll back and exit 1
    pull <part id> [--segment NAME]        read parameters, mass properties and exports; write the sidecar, the STL and the generated component registry
    drift <part id>                        inherited values in Fusion against the current addresses; exit 1 on drift. Reads only
    stamp <part id> [--note TEXT] [--by NAME]   stamp the part's work item for the addresses it consumed; refuses on drift, an unhealthy timeline or stale hashes
    status                                 one line per binding: revision, document version, drift, timeline, work status (from the sidecar and thread/graph.json)

Fusion must be running with its MCP server (port FUSION_MCP_PORT, default 27182) and the bound document active. Nothing here saves a document.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import binding as cb
from . import ops, transport

REPO = Path(__file__).resolve().parents[2]


def build_parser() -> argparse.ArgumentParser:
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--root", default=None, help="the repo root (default: this repo)")
    p = argparse.ArgumentParser(prog="fy cad", description="the CAD bridge", parents=[common])
    sub = p.add_subparsers(dest="command", required=True)
    sub.add_parser("validate", parents=[common]).add_argument("part", nargs="?")
    sub.add_parser("push", parents=[common]).add_argument("part")
    sp = sub.add_parser("pull", parents=[common])
    sp.add_argument("part")
    sp.add_argument("--segment", default=None, help="the envelope segment name when the part has no thread record")
    sub.add_parser("drift", parents=[common]).add_argument("part")
    sp = sub.add_parser("stamp", parents=[common])
    sp.add_argument("part")
    sp.add_argument("--note", default="")
    sp.add_argument("--by", default=None)
    sub.add_parser("status", parents=[common])
    return p


class _Lazy:
    """The thread's resolver and the Fusion session are built on first use, so a command that needs neither (status) pays for neither."""

    def __init__(self, root):
        self.root, self._resolve, self._session = root, None, None

    def resolve(self, address):
        if self._resolve is None:
            self._resolve = cb.thread_resolver(self.root)
        return self._resolve(address)

    def bridge(self, verb, **args):
        if self._session is None:
            self._session = transport.Session().open()
        return transport.call(verb, args, session=self._session)


def make_context(root, say=print) -> ops.Context:
    lazy = _Lazy(Path(root))
    return ops.Context(Path(root), lazy.resolve, lazy.bridge, say)


def main(argv=None, default_root=None, say=print, context=None) -> int:
    args = build_parser().parse_args(argv)
    root = Path(args.root) if args.root else Path(default_root or REPO)
    ctx = context or make_context(root, say)
    try:
        return COMMANDS[args.command](args, ctx, say)
    except (ops.Refused, cb.BindingError, transport.FusionError) as e:
        say(f"fy cad {args.command}: refused: {e}")
        return 1


def cmd_validate(args, ctx, say) -> int:
    bad = 0
    for part in ([args.part] if args.part else ops.parts(ctx.root)):
        problems = ops.validate(ctx, part)
        say(f"{part}: " + ("ok" if not problems else f"{len(problems)} problem(s)"))
        for pr in problems:
            say(f"  - {pr}")
        bad += bool(problems)
    return 1 if bad else 0


def cmd_push(args, ctx, say) -> int:
    r = ops.push(ctx, args.part)
    if r["ok"]:
        say(f"{args.part}: pushed " + ", ".join(f"{x['name']} = {x['expression']}" for x in r["rows"]))
        say(f"{args.part}: saved as version {r['version']}" if r["saved"] and r["version"] is not None else f"{args.part}: {r['save_note']}" if r["saved"] else f"{args.part}: not saved: {r['save_skipped']}")
        return 0
    why = r.get("refused") or r.get("errors") or r.get("failed_features")
    say(f"{args.part}: push failed: {why}; failed features {r.get('failed_features')}; rolled back {r.get('rolled_back')}"
        f" (expressions restored exactly: {r.get('rollback', {}).get('equal')})")
    return 1


def cmd_pull(args, ctx, say) -> int:
    doc = ops.pull(ctx, args.part, args.segment)
    stl = doc["exports"]["stl"]
    say(f"{args.part}: pulled doc v{doc['document']['version']}; mass {doc['mass_properties']['mass_kg']:.6f} kg; stl {stl['triangles']} triangles, chord bound {stl['chord_bound_mm']:.4f} mm"
        f" (guarantee {stl['chord_guarantee']}); drift {len(doc['drift'])}")
    if doc["document"]["unsaved_changes"]:
        say(f"{args.part}: UNSAVED: the document has unsaved changes, so this pull does not describe doc v{doc['document']['version']} and `stamp` will refuse; save it and pull again")
    return 0


def cmd_drift(args, ctx, say) -> int:
    d = ops.drift_of(ctx, args.part)
    for x in d:
        say(f"{args.part}: DRIFT {x['name']}: Fusion {x['fusion_value']:.9g}, {x['address']} gives {x['address_value']:.9g}")
    if not d:
        say(f"{args.part}: no drift")
    return 1 if d else 0


def cmd_stamp(args, ctx, say) -> int:
    path = ops.stamp(ctx, args.part, note=args.note, by=args.by)
    say(f"{args.part}: stamped {path.relative_to(ctx.root).as_posix()}")
    return 0


def cmd_status(args, ctx, say) -> int:
    for line in ops.status(ctx):
        say(line)
    return 0


COMMANDS = {"validate": cmd_validate, "push": cmd_push, "pull": cmd_pull, "drift": cmd_drift, "stamp": cmd_stamp, "status": cmd_status}

if __name__ == "__main__":
    sys.exit(main())
