"""
`fy envelope` commands (tools/fy only dispatches here).

    build  [--mesh FILE] [--knee chords|ruler|ansur|breadth] [--base FILE] [--out DIR] [--cache-dir DIR] [--voxel MM]
                    register the mesh to the sheet's nodes, conform and voxelise the right thigh, shank and foot; write <seg>_R.yaml, <seg>_R_sections.csv,
                    the silhouette PNGs, the cache and the inspect bundle (cache/inspect/)
    gates  [same options]   the trial's gate table, the feature report and the Monte Carlo (writes thigh_R_trial.json beside the ledger)
    trunk  [--mesh FILE] [--n N]
                    trunk registration (brief 5, item 1): the CJC anchor candidates and the stretch per sub-segment, written to data/envelope/trunk_registration.json
    ratios          write data/ansur2/ratios.json from the raw ANSUR II female CSV
    check  --segment thigh_R --shapes FILE --poses FILE [--required MM] [--cache-dir DIR]
                    clearance of posed shapes inside a built segment; exit 0 feasible, 1 infeasible. --segment a,b,... (built trunk bodies, e.g. pelvis,abdomen) checks
                    containment in their union; the poses are then in the frame of the first body

Defaults: mesh data/makehuman/freyja-body-v2.obj (the baseline since volume-extractor brief 4; v1 is historical), sheet values from params/snapshot.csv, out data/envelope, cache data/envelope/cache (gitignored).
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[2]


def _paths(args, root: Path):
    return {
        "mesh": Path(args.mesh) if args.mesh else root / "data/makehuman/freyja-body-v2.obj",
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
    sp.add_argument("--mesh"), sp.add_argument("--out"), sp.add_argument("--cache-dir")
    sp.add_argument("--knee", choices=("chords", "ruler", "ansur", "breadth"), default="chords",
                    help="mesh knee height: the mean of the Ruler upper-leg chord's lower end and the lower-leg chord's upper end (default), the Ruler knee loop "
                         "plus the ANSUR epicondyle-above-midpatella offset, the ANSUR ratio, or the knee-breadth peak (stops when the mesh has none)")
    sp.add_argument("--base", help="MakeHuman base.obj for the topology gate (default data/makehuman/base.obj; the gate stops when it is absent)")
    sp.add_argument("--voxel", type=float, default=2.0)


def cmd_build(args, root):
    from . import bundle, ledger, plots, trial
    p = _paths(args, root)
    inp = trial.load_inputs(root, p["mesh"])
    feats = trial.find_features(inp)
    reg = trial.make_registration(inp, feats, args.knee)
    sha = trial.inputs_hash(inp, {"knee": reg.knee_source, "voxel": args.voxel})
    out = p["out"]
    out.mkdir(parents=True, exist_ok=True)
    p["cache"].mkdir(parents=True, exist_ok=True)
    st = reg.axial.stretches()
    results = {}
    for name in trial.SEGMENTS:
        res = trial.build_segment(inp, feats, reg, name, args.voxel)
        results[name] = res
        rows = ledger.rows_for(res.seg, "right")
        hdr = ledger.header(res, rows, ledger.SHELL_MM, "", _label(p["mesh"], root), "data/ansur2/ratios.json", sha, trial.HIP_ZONE_MM)
        hdr["checks"] = {k: (bool(v) if isinstance(v, (bool, np.bool_)) else int(v)) for k, v in res.checks.items()}
        (out / f"{name}_R.yaml").write_text(ledger.to_yaml(hdr, sha), encoding="utf-8", newline="\n")
        (out / f"{name}_R_sections.csv").write_text(ledger.to_csv(rows, sha), encoding="utf-8", newline="\n")
        if name != "foot":
            title = f"right {name}, conformed; knee anchor: {reg.knee_source}\nstretch thigh {st['thigh']:.4f}, shank {st['shank']:.4f}"
            for view in ("sagittal", "coronal"):
                plots.silhouette_png(res.seg, out / f"{name}_R_{view}.png", view, ledger.SHELL_MM, f"{view}: {title}")
        res.seg.meta = {"inputs_sha256_12": sha, "segment": f"{name}_R", "knee_source": reg.knee_source, "origin_xyz": [float(x) for x in res.origin_xyz]}
        res.seg.save(p["cache"] / f"{name}_R.npz")
        print(f"built {name}_R: L {res.seg.length:.1f} mm, skin volume {res.seg.volume() / 1e6:.3f} l, inputs {sha}")
    from . import bodies, masses
    tb = bodies.build(inp, feats, reg, masses.load_dumas_table1(root), args.voxel)
    for name in bodies.BODIES:
        res, rows = tb.results[name], tb.rows[name]
        hdr = bodies.body_header(name, tb, rows, sha, _label(p["mesh"], root))
        (out / f"{name}.yaml").write_text(ledger.to_yaml(hdr, sha), encoding="utf-8", newline="\n")
        (out / f"{name}_sections.csv").write_text(ledger.to_csv(rows, sha), encoding="utf-8", newline="\n")
        title = f"{name}, conformed; CJC anchor: {bodies.trunk.PRIMARY_CANDIDATE}; stretch {hdr['stretch']:.4f}"
        for view in ("sagittal", "coronal"):
            plots.silhouette_png(res.seg, out / f"{name}_{view}.png", view, ledger.SHELL_MM, f"{view}: {title}", side="trunk")
        res.seg.meta = {**res.seg.meta, "inputs_sha256_12": sha}
        res.seg.save(p["cache"] / f"{name}.npz")
        print(f"built {name}: L {res.seg.length:.1f} mm, skin volume {res.seg.volume() / 1e6:.3f} l, inputs {sha}")
    bdir = bundle.build(inp, feats, reg, results, root, p["cache"] / "inspect", trunk=tb)
    print(f"stretch thigh {st['thigh']:.4f} shank {st['shank']:.4f} foot {st['foot']:.4f}; knee source {reg.knee_source}")
    print(f"wrote ledgers and silhouettes to {_label(out, root)}, the inspect bundle to {_label(bdir, root)}")
    return 0


def cmd_gates(args, root):
    from . import gates
    return gates.run(_paths(args, root), args, root, _label)


def cmd_trunk(args, root):
    from . import trunk
    p = _paths(args, root)
    res = trunk.run(root, p["mesh"], n=args.n)
    print(trunk.format_report(res))
    print("wrote", _label(trunk.write(res, root), root))
    return 0


def cmd_ratios(args, root):
    from . import anthro
    print("wrote", _label(anthro.write_summary(root), root))
    return 0


def cmd_check(args, root):
    from . import field, oracle
    cache = Path(args.cache_dir) if args.cache_dir else root / "data/envelope/cache"
    f = cache / f"{args.segment}.npz"
    if "," not in args.segment and not f.exists():
        print(f"fy envelope check: no built segment at {_label(f, root)}; run `fy envelope build` first", file=sys.stderr)
        return 2
    shapes, poses = oracle.read_shapes(args.shapes), oracle.read_poses(args.poses)
    if "," in args.segment:
        import numpy as np
        names = args.segment.split(",")
        segs = []
        for n in names:
            fn = cache / f"{n}.npz"
            if not fn.exists():
                print(f"fy envelope check: no built segment at {_label(fn, root)}; run `fy envelope build` first", file=sys.stderr)
                return 2
            segs.append(field.Segment.load(fn))
        if any("origin_xyz" not in sg.meta for sg in segs):
            print("fy envelope check: a union needs the bodies' origins; rebuild with `fy envelope build`", file=sys.stderr)
            return 2
        o0 = np.array(segs[0].meta["origin_xyz"])
        out = oracle.clearance_union([(sg, np.array(sg.meta["origin_xyz"]) - o0) for sg in segs], shapes, poses, args.required)
        seg = segs[0]
    else:
        seg = field.Segment.load(f)
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
    sub.add_parser("ratios")
    t = sub.add_parser("trunk")
    t.add_argument("--mesh"), t.add_argument("--out"), t.add_argument("--cache-dir")
    t.add_argument("--n", type=int, default=200, help="Monte Carlo samples")
    c = sub.add_parser("check")
    c.add_argument("--segment", required=True), c.add_argument("--shapes", required=True), c.add_argument("--poses", required=True)
    c.add_argument("--required", type=float, default=0.0, help="required clearance in mm (default 0: inside the skin)")
    c.add_argument("--cache-dir")
    args = ap.parse_args(argv)
    from . import sheet
    try:
        return {"build": cmd_build, "gates": cmd_gates, "check": cmd_check, "ratios": cmd_ratios, "trunk": cmd_trunk}[args.cmd](args, root)
    except sheet.StopAndAsk as e:
        print(f"fy envelope: STOP, ask Joe: {e}", file=sys.stderr)
        return 3
