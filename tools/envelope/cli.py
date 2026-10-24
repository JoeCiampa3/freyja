"""
`fy envelope` commands (tools/fy only dispatches here).

    build  [--landmarks FILE] [--b1 FILE] [--mesh FILE] [--k asis|sheet] [--out DIR] [--cache-dir DIR]
                    voxelise the conformed right thigh; write thigh_R.yaml, thigh_R_sections.csv, the two silhouette PNGs and the cache
    gates  [same options]   the trial's gate table and sensitivity (writes thigh_R_trial.json beside the ledger)
    check  --segment thigh_R --shapes FILE --poses FILE [--required MM] [--cache-dir DIR]
                    clearance of posed shapes inside a built segment; exit 0 feasible, 1 infeasible

Defaults: landmarks data/mesh/landmarks.json (Joe's picks), b1 data/envelope/sheet_b1.json (the sheet pull), mesh
data/makehuman/freyja-body-v1.obj, out data/envelope, cache data/envelope/cache (gitignored). Results from `--landmarks` files that are marked
provisional are refused into data/envelope: give `--out` elsewhere.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[2]


def _paths(args, root: Path):
    return {
        "mesh": Path(args.mesh) if args.mesh else root / "data/makehuman/freyja-body-v1.obj",
        "landmarks": Path(args.landmarks) if args.landmarks else root / "data/mesh/landmarks.json",
        "b1": Path(args.b1) if args.b1 else root / "data/envelope/sheet_b1.json",
        "snapshot": root / "params/snapshot.csv",
        "out": Path(args.out) if args.out else root / "data/envelope",
        "cache": Path(args.cache_dir) if args.cache_dir else root / "data/envelope/cache",
    }


def _label(p: Path, root: Path) -> str:
    """A repo-relative name, never an absolute path (artifacts carry none)."""
    try:
        return p.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return p.name


def _common(sp):
    sp.add_argument("--landmarks"), sp.add_argument("--b1"), sp.add_argument("--mesh")
    sp.add_argument("--k", choices=("asis", "sheet"), default="asis", help="pelvis scale: mesh inter-ASIS over the sheet's (default) or the sheet's pelvis factor")
    sp.add_argument("--out"), sp.add_argument("--cache-dir")
    sp.add_argument("--voxel", type=float, default=2.0)


def _load(args, root):
    from . import sheet, trial
    p = _paths(args, root)
    for key, hint in (("landmarks", "Joe's picks (tools/landmark-picker) or a provisional file"), ("b1", "the sheet's table B1 (see tools/envelope/sheet.py)")):
        if not p[key].exists():
            raise sheet.StopAndAsk(f"{_label(p[key], root)} is missing: {hint}")
    inp = trial.load_inputs(p["mesh"], p["landmarks"], p["b1"], p["snapshot"])
    if inp.provisional and not args.out:
        raise sheet.StopAndAsk("the landmark file is marked provisional: pass --out DIR so its results do not land in data/envelope")
    return p, inp


def cmd_build(args, root):
    from . import ledger, plots, trial
    p, inp = _load(args, root)
    res = trial.build_thigh(inp, args.k, args.voxel)
    sha = trial.inputs_hash(inp, {"k": args.k, "voxel": args.voxel})
    rows = ledger.rows_for(res.seg, "right")
    note = "sheet thigh mass over the skin volume of the conformed mesh thigh, hip zone included; soft tissue is about 1.0-1.1 kg/l"
    hdr = ledger.header(res, rows, ledger.SHELL_MM, note, "provisional" if inp.provisional else _label(p["landmarks"], root),
                        inp_b1_label(p, root), sha, trial.HIP_ZONE_MM)
    hdr["checks"] = {k: (bool(v) if isinstance(v, (bool, np.bool_)) else int(v)) for k, v in res.checks.items()}
    out = p["out"]
    out.mkdir(parents=True, exist_ok=True)
    (out / "thigh_R.yaml").write_text(ledger.to_yaml(hdr, sha), encoding="utf-8", newline="\n")
    (out / "thigh_R_sections.csv").write_text(ledger.to_csv(rows, sha), encoding="utf-8", newline="\n")
    title = f"right thigh, conformed (s = {res.s:.4f}, k {res.k_variant} = {res.k:.4f})"
    for view in ("sagittal", "coronal"):
        plots.silhouette_png(res.seg, out / f"thigh_R_{view}.png", view, ledger.SHELL_MM, f"{view}: {title}")
    res.seg.meta = {"inputs_sha256_12": sha, "segment": "thigh_R", "k_variant": res.k_variant, "stretch_s": res.s}
    p["cache"].mkdir(parents=True, exist_ok=True)
    res.seg.save(p["cache"] / "thigh_R.npz")
    print(f"built thigh_R: L {res.seg.length:.1f} mm, s {res.s:.4f}, skin volume {res.seg.volume() / 1e6:.3f} l, inputs {sha}")
    print(f"wrote {_label(out / 'thigh_R.yaml', root)}, thigh_R_sections.csv, thigh_R_sagittal.png, thigh_R_coronal.png")
    return 0


def inp_b1_label(p, root):
    d = json.loads(Path(p["b1"]).read_text(encoding="utf-8"))
    return d.get("source", _label(p["b1"], root))


def cmd_gates(args, root):
    from . import gates
    p, inp = _load(args, root)
    return gates.run(inp, p, args, root, _label)


def cmd_check(args, root):
    from . import field, oracle
    cache = Path(args.cache_dir) if args.cache_dir else root / "data/envelope/cache"
    f = cache / f"{args.segment}.npz"
    if not f.exists():
        print(f"fy envelope check: no built segment at {_label(f, root)}; run `fy envelope build` first", file=sys.stderr)
        return 2
    seg = field.Segment.load(f)
    shapes, poses = oracle.read_shapes(args.shapes), oracle.read_poses(args.poses)
    out = oracle.clearance(seg, shapes, poses, args.required)
    print(f"segment {args.segment} (inputs {seg.meta.get('inputs_sha256_12', '?')}), {len(poses)} pose(s), {len(shapes)} shape(s)")
    for i, (m, o) in enumerate(zip(out["margins_mm"], out["slab_overruns_mm"])):
        print(f"  pose {i}: margin {m:8.2f} mm   slab overrun {o:6.2f} mm")
    x, y, z = out["point_mm"]
    print(f"binds at pose {out['pose_index']} on {out['shape']}: margin {out['margin_mm']:.2f} mm at station {out['station_mm']:.1f} mm, point (x {x:.1f}, y {y:.1f}, z {z:.1f}) mm")
    print(f"slab overrun {out['slab_overrun_mm']:.2f} mm; required margin {out['required_mm']:.2f} mm")
    print("FEASIBLE" if out["feasible"] else "INFEASIBLE")
    return 0 if out["feasible"] else 1


def main(argv=None, default_root=None) -> int:
    root = Path(default_root) if default_root else REPO
    ap = argparse.ArgumentParser(prog="fy envelope", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    _common(sub.add_parser("build"))
    _common(sub.add_parser("gates"))
    c = sub.add_parser("check")
    c.add_argument("--segment", required=True), c.add_argument("--shapes", required=True), c.add_argument("--poses", required=True)
    c.add_argument("--required", type=float, default=0.0, help="required clearance in mm (default 0: inside the skin)")
    c.add_argument("--cache-dir")
    args = ap.parse_args(argv)
    from . import sheet
    try:
        return {"build": cmd_build, "gates": cmd_gates, "check": cmd_check}[args.cmd](args, root)
    except sheet.StopAndAsk as e:
        print(f"fy envelope: STOP, ask Joe: {e}", file=sys.stderr)
        return 3
