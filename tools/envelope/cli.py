"""
`fy envelope` commands (tools/fy only dispatches here).

    build  [--mesh FILE] [--knee chords|ruler|ansur|breadth] [--base FILE] [--out DIR] [--cache-dir DIR] [--voxel MM]
                    register the mesh to the sheet's nodes, conform and voxelise the right thigh, shank and foot; write <seg>_R.yaml, <seg>_R_sections.csv,
                    the silhouette PNGs, the cache and the inspect bundle (cache/inspect/)
    gates  [same options]   the trial's gate table, the feature report and the Monte Carlo (writes thigh_R_trial.json beside the ledger)
    trunk  [--mesh FILE] [--n N]
                    trunk registration (brief 5, item 1): the CJC anchor candidates and the stretch per sub-segment, written to data/envelope/trunk_registration.json
    ratios          write data/ansur2/ratios.json from the raw ANSUR II female CSV
    offsets [--cache-dir DIR] [--out DIR] [--tilt DEG]
                    brief 7, item 2: the offset between the sim's trunk stack (MuJoCo forward kinematics) and the mesh trunk centre line at the LJC, TJC, CJC and SJC planes, in the zero
                    pose and in the design stance (tilt default: the snapshot's stand_pelvis_tilt_deg); writes <out>/trunk_offsets.json. Needs `build`. Nothing in the sim changes
    check  --segment thigh_R --shapes FILE --poses FILE [--required MM] [--cache-dir DIR] [--occupied | --no-occupied] [--components-dir DIR]
                    clearance of posed shapes inside a built segment; exit 0 feasible, 1 infeasible. --segment a,b,... (built trunk bodies, e.g. pelvis,abdomen) checks
                    containment in their union; the poses are then in the frame of the first body. When the segment has a component registry (<cache-dir>/../components/<segment>.yaml,
                    or --components-dir) the margin to each placed component is reported as well and enters the verdict (--no-occupied ignores the registry, --occupied requires one)
    foreign --owner BODY --host SEGMENT --placement tx,ty,tz[,rx,ry,rz] --out FILE [--samples FILE] [--model FILE]
                    the poses of a part fixed to the owner body (e.g. pelvis), in the host segment's frame (e.g. thigh_R), for joint-angle samples (a CSV with one column per model
                    joint name, degrees; default: the hip's single-axis sweeps at 5 degrees and the three-axis grid at 15 degrees over the model's limits), built on the MuJoCo
                    model; the placement is in the owner's model body frame. Right side only. The output is a poses CSV for `check` or a registry's `poses_file`
    free   --segment S [--required MM] [--union ADJACENT] [--cache-dir DIR] [--components-dir DIR] [--out DIR]
                    the free field of a segment (skin margin at least --required, every placed component dilated by its clearance and swept over its poses removed): free and occupied
                    volume, the largest free sphere, the free-space ledger at 10 mm stations in <out>/free/<segment>.yaml and the inspect-bundle layer

    reserve [--required MM] [--cache-dir DIR] [--out DIR]
                    brief 8, item 5: the spine modules of data/envelope/reservations.yaml as reserved components of each candidate trunk body: the best arrangement of three modules (the largest skin
                    margin at which they fit), the free volume left, the largest free sphere, the mass impact; writes <out>/reserved/<body>.yaml (a components/1 registry per body that holds them)
                    and <out>/reservations_result.json. Needs `build`

    corridor [--required MM] [--cache-dir DIR] [--out DIR]
                    brief 8, item 6: the corridor sweep (the largest vertical column at each x offset d from the hip line, LSJ to CJC, at skin margin t), the sim's stack axis in the same x for the zero pose,
                    the design stance and the stance with the ankle lean, the corridor cylinder (the file's diameter, or 0.8 x the sweep's minimum when null) at the best d as a reserved component of
                    the abdomen and the thorax, and their free-space ledgers; writes <out>/corridor_result.json and <out>/corridor/ (registries and free/). Needs `build` and `offsets`

    hip [--no-alternative]
                    brief 8, item 6b (report only): the model's HJC in the thigh and the pelvis frames (signed skin distance, lateral skin distance, the lateral step of the pelvis and thigh sections at the
                    hip plane) and the volumes under the other shear target; writes <out>/hip_registration.json. Needs `build`

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
    sha = trial.inputs_hash(inp, {"knee": reg.knee_source, "voxel": args.voxel, "sjc_mm": [round(v, 6) for v in inp.sheet.sjc_mm]})      # the trunk's ledgers also depend on the sheet's SJC
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
    from . import arms, arms_report, ruler
    arm_S = arms.build_side(inp, tb, ruler.load(root), arms.sheet_arm(root / "params/snapshot.csv"), "R", args.voxel)
    arm_sha = trial.inputs_hash(inp, {"knee": reg.knee_source, "voxel": args.voxel, "sjc_mm": [round(v, 6) for v in inp.sheet.sjc_mm], "arms": True, "sigma_mm": arms.SIGMA_MM})
    for n in arms_report.write_products(arm_S, out, p["cache"], arm_sha, _label(p["mesh"], root)):
        r = arm_S["results"][n.replace("_R", "")]
        print(f"built {n}: L {r.seg.length:.1f} mm, skin volume {r.seg.volume() / 1e6:.3f} l, stretch {arm_S['frames'][n.replace('_R', '')].k:.4f}, inputs {arm_sha}")
    bdir = bundle.build(inp, feats, reg, results, root, p["cache"] / "inspect", trunk=tb)
    arms_report.inspect_layer(arm_S, inp, bdir)
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


def cmd_offsets(args, root):
    import json
    from . import offsets
    cache = Path(args.cache_dir) if args.cache_dir else root / "data/envelope/cache"
    rep = offsets.report(root, cache, args.tilt)
    print(offsets.format_report(rep))
    out = (Path(args.out) if args.out else root / "data/envelope") / "trunk_offsets.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    doc = {"generated_by": "fy envelope offsets from the built trunk bodies, the model and the snapshot; do not edit, rerun", **rep}
    out.write_text(json.dumps(doc, indent=1, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    print("wrote", _label(out, root))
    return 0


def cmd_reserve(args, root):
    import json
    import yaml
    from . import field, frames, registry, reserve
    cache = Path(args.cache_dir) if args.cache_dir else root / "data/envelope/cache"
    out = Path(args.out) if args.out else root / "data/envelope"
    doc = reserve.load(root)
    chk = reserve.module_check(doc)
    print(f"modules: {chk['count']} x D {chk['diameter_mm']} x L {chk['length_mm']} mm = {chk['volume_mm3']:.0f} mm3 against {chk['reference_mm3']:.3g} ({chk['relative_difference'] * 100:+.2f}%, within 2%: {chk['within_2_percent']})")
    mod, cl = doc["spine_v2"]["module"], float(doc["spine_v2"]["clearance_mm"])
    sheet_mass = {}
    from . import trial
    sh = trial.register.sheet_nodes(root / "params/snapshot.csv")
    sheet_mass = {"abdomen": sh.abdomen_mass_kg, "pelvis": sh.pelvis_mass_kg, "thorax": sh.thorax_mass_kg}
    (out / "reserved").mkdir(parents=True, exist_ok=True)
    res = {"generated_by": "fy envelope reserve; do not edit, rerun", "reservations_file": reserve.PATH, "module_check": chk, "orientation_assumed": "vertical (axis parallel to the trunk axis)",
           "required_skin_margin_mm": args.required, "bodies": {}}
    for b in chk["candidates"]:
        fn = cache / f"{b}.npz"
        if not fn.exists():
            print(f"fy envelope reserve: no built segment at {_label(fn, root)}; run `fy envelope build` first", file=sys.stderr)
            return 2
        seg = field.Segment.load(fn)
        off = frames.segment_offset_mm(b, seg.meta)
        r = reserve.search(seg, mod, cl, (off[0], 0.0))
        entry = {"search": r, "frame_offset_mm": list(off)}
        rdoc = reserve.registry_doc(b, r, mod, cl, off)
        base = reserve.free_numbers(seg, [], args.required, sheet_mass[b], 0.0)
        entry["without_modules"] = base
        if rdoc is not None:
            path = out / "reserved" / f"{b}.yaml"
            path.write_text("# GENERATED by fy envelope reserve (components/1, reserved spine modules in the model body frame). Do not edit; rerun.\n" + yaml.safe_dump(rdoc, sort_keys=False, default_flow_style=None), encoding="utf-8", newline="\n")
            reg = registry.load(path)
            reg.frame_offset_mm = off
            entry["registry"] = _label(path, root)
            entry["with_modules"] = {"at_required_margin": reserve.free_numbers(seg, [(reg, np.zeros(3))], args.required, sheet_mass[b], chk["count"] * mod["mass_kg"]),
                                     "feasible_at_required_margin": bool(r["max_skin_margin_mm"] >= args.required)}
            if r["max_skin_margin_mm"] < args.required:
                entry["with_modules"]["at_skin"] = reserve.free_numbers(seg, [(reg, np.zeros(3))], 0.0, sheet_mass[b], chk["count"] * mod["mass_kg"])
        else:
            (out / "reserved" / f"{b}.yaml").unlink(missing_ok=True)
        res["bodies"][b] = entry
        if r.get("none"):
            print(f"{b}: no arrangement of three modules fits ({r['reason']}); body inner volume at t = {args.required:g} mm {base['inner_volume_l']:.3f} l, sheet mass {base['sheet_mass_kg']:.3f} kg, modules {chk['count'] * mod['mass_kg']:.1f} kg")
        else:
            w = entry["with_modules"]["at_required_margin"]
            print(f"{b}: best arrangement at skin margin {r['max_skin_margin_mm']:.1f} mm (station {r['station_of_centre_mm']:.0f} mm, centroid {r['centroid_offset_from_trunk_axis_mm']:.1f} mm from the trunk axis); "
                  f"at t = {args.required:g} mm free {w['free_volume_l']:.3f} of {w['inner_volume_l']:.3f} l, largest free sphere {w['largest_free_sphere_mm']:.1f} mm; modules {w['module_mass_kg']:.1f} kg "
                  f"= {w['module_mass_fraction_of_sheet_mass'] * 100:.0f}% of the sheet's {w['sheet_mass_kg']:.3f} kg")
    (out / "reservations_result.json").write_text(json.dumps(res, indent=1, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    print("wrote", _label(out / "reservations_result.json", root))
    return 0


def cmd_corridor(args, root):
    import argparse
    import json
    import yaml
    from . import corridor, field, frames, registry, reserve
    cache = Path(args.cache_dir) if args.cache_dir else root / "data/envelope/cache"
    out = Path(args.out) if args.out else root / "data/envelope"
    offs_path = out / "trunk_offsets.json"
    if not offs_path.exists():
        print("fy envelope corridor: data/envelope/trunk_offsets.json is missing; run `fy envelope offsets` first", file=sys.stderr)
        return 2
    segs = {}
    for n in corridor.BODIES:
        fn = cache / f"{n}.npz"
        if not fn.exists():
            print(f"fy envelope corridor: no built segment at {_label(fn, root)}; run `fy envelope build` first", file=sys.stderr)
            return 2
        segs[n] = field.Segment.load(fn)
    prof = corridor.profile(segs, args.required)
    b = corridor.best(prof)
    axes = corridor.sim_axes(json.loads(offs_path.read_text(encoding="utf-8")))
    shift = corridor.forward_shift(b["best_d_mm"], axes)
    doc = reserve.load(root)
    given = doc["spine_v2"]["corridor"].get("diameter_mm")
    diameter = float(given) if given is not None else 0.8 * b["best_min_diameter_mm"]
    res = {"generated_by": "fy envelope corridor; do not edit, rerun", "required_skin_margin_mm": args.required, "d_range_mm": list(corridor.D_RANGE_MM), "d_step_mm": corridor.D_STEP_MM,
           "stations": "every 2 mm layer of the abdomen (LJC to TJC) and the thorax (TJC to CJC); the profile is reported every 10 mm", "sweep": b["table"], "best_d_mm": b["best_d_mm"],
           "best_min_diameter_mm": b["best_min_diameter_mm"], "best_station": b["best_station"], "profile_at_best_d": corridor.profile_at(prof, b["best_d_mm"]),
           "sim_stack_axis_x_mm": axes, "forward_shift_of_best_d_mm": shift, "corridor_diameter_mm": diameter,
           "corridor_diameter_source": "reservations.yaml spine_v2.corridor.diameter_mm" if given is not None else "0.8 x the sweep's minimum diameter (the file's value is null)", "bodies": {}}
    print(f"corridor sweep, skin margin {args.required:g} mm: best d {b['best_d_mm']:+.0f} mm, least diameter {b['best_min_diameter_mm']:.1f} mm at {b['best_station']['body']} station {b['best_station']['station_mm']:.0f} mm "
          f"({b['best_station']['height_above_lsj_mm']:.0f} mm above the LSJ); corridor cylinder {diameter:.1f} mm")
    for pose, planes in axes.items():
        print(f"  sim axis, {pose}: " + ", ".join(f"{p} {x:+.1f}" for p, x in planes.items()) + "; forward shift of the best d: " + ", ".join(f"{p} {shift[pose][p]:+.1f}" for p in planes))
    cdir = out / "corridor"
    cdir.mkdir(parents=True, exist_ok=True)
    (cdir / "free").mkdir(exist_ok=True)
    for n, seg in segs.items():
        off = frames.segment_offset_mm(n, seg.meta)
        comp = {"id": "part.spine.corridor", "name": "corridor_column", "status": "reserved", "owner": n, "primitive": {"type": "cylinder", "diameter": round(diameter, 3), "length": round(seg.length, 3)},
                "pose": {"tx": round(b["best_d_mm"] - off[0], 3), "ty": 0 - off[1], "tz": round(-seg.length / 2 - off[2], 3), "rx": 0, "ry": 0, "rz": 0}, "clearance_mm": 0.0,
                "source": "fy envelope corridor: best d of the sweep"}
        rdoc = {"schema": registry.SCHEMA, "segment": n, "components": [comp]}
        (cdir / f"{n}.yaml").write_text("# GENERATED by fy envelope corridor (components/1, the corridor column as a reserved component, model body frame). Do not edit; rerun.\n" + yaml.safe_dump(rdoc, sort_keys=False, default_flow_style=None), encoding="utf-8", newline="\n")
        base = reserve.free_numbers(seg, [], args.required, 1.0, 0.0)
        ns = argparse.Namespace(segment=n, required=args.required, union=None, cache_dir=str(cache), components_dir=str(cdir), out=str(cdir), mesh=None)
        rc = cmd_free(ns, root)
        led = yaml.safe_load((cdir / "free" / f"{n}.yaml").read_text(encoding="utf-8").split("\n", 1)[1])
        res["bodies"][n] = {"inner_volume_l": led["skin_volume_l"], "free_volume_l": led["free_volume_l"], "occupied_volume_l": led["occupied_volume_l"], "largest_free_sphere_mm": led["largest_free_sphere"]["diameter_mm"],
                            "without_corridor": {"free_volume_l": base["free_volume_l"], "largest_free_sphere_mm": base["largest_free_sphere_mm"]}, "registry": _label(cdir / f"{n}.yaml", root),
                            "ledger": _label(cdir / "free" / f"{n}.yaml", root)}
        if rc:
            return rc
    (out / "corridor_result.json").write_text(json.dumps(res, indent=1, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    print("wrote", _label(out / "corridor_result.json", root))
    return 0


def cmd_hip(args, root):
    import json
    from . import field, hipcheck, trial
    cache = Path(args.cache_dir) if args.cache_dir else root / "data/envelope/cache"
    out = Path(args.out) if args.out else root / "data/envelope"
    for n in ("thigh_R", "pelvis"):
        if not (cache / f"{n}.npz").exists():
            print(f"fy envelope hip: no built segment at {_label(cache / (n + '.npz'), root)}; run `fy envelope build` first", file=sys.stderr)
            return 2
    sh = trial.register.sheet_nodes(root / "params/snapshot.csv")
    res = hipcheck.frame_numbers(field.Segment.load(cache / "thigh_R.npz"), field.Segment.load(cache / "pelvis.npz"), sh.lateral_y, sh.hjc_x_mm)
    if not args.no_alternative:
        mesh = Path(args.mesh) if args.mesh else root / "data/makehuman/freyja-body-v2.obj"
        res["alternative_shear_target"] = hipcheck.alternative_target(root, mesh)
    res = {"generated_by": "fy envelope hip (report only: nothing is fixed); do not edit, rerun", **res}
    s, lat, st, f = res["signed_skin_distance_at_hjc_mm"], res["lateral_skin_distance_at_hjc_plane_mm"], res["lateral_extent_right_half_pelvis_frame_mm"], res["flag"]
    print(f"model HJC: signed skin distance {s['thigh_frame']:.1f} mm in the thigh frame, {s['pelvis_frame']:.1f} mm in the pelvis frame (difference {s['difference']:+.1f})")
    print(f"lateral skin distance at the HJC plane: {lat['thigh_frame']:.1f} mm thigh frame, {lat['pelvis_frame']:.1f} mm pelvis frame (difference {lat['difference']:+.1f})")
    print(f"lateral extent of the right half at the plane: pelvis {st['pelvis_section']:.1f} mm, thigh placed by the model {st['thigh_section_placed_by_the_model']:.1f} (step {st['step_model_frames']:+.1f}), "
          f"placed by the mesh {st['thigh_section_placed_by_the_mesh']:.1f} (step {st['step_conformed_mesh']:+.1f})")
    print(f"hip spacing: sheet {abs(res['sheet_lateral_offset_mm']):.2f} mm, mesh {res['mesh_hjc_separation_from_midline_mm']:.2f} mm (difference {res['hip_spacing_difference_mm']:.2f}); FLAG (limit {f['limit_mm']:g} mm): {f['frames_differ_by_more_than_limit']}")
    if "alternative_shear_target" in res:
        a = res["alternative_shear_target"]
        print(f"other shear target (the mesh's own HJC centroid y {a['target_lateral_y_mm']:.2f} mm): thigh {a['thigh_volume_l']:.4f} l, pelvis {a['pelvis_volume_l']:.4f} l")
    (out / "hip_registration.json").write_text(json.dumps(res, indent=1, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    print("wrote", _label(out / "hip_registration.json", root))
    return 0


def cmd_ratios(args, root):
    from . import anthro
    print("wrote", _label(anthro.write_summary(root), root))
    return 0


def _components_dir(args, cache: Path) -> Path:
    return Path(args.components_dir) if args.components_dir else cache.parent / "components"


def cmd_check(args, root):
    from . import field, frames, occupancy, oracle, registry
    cache = Path(args.cache_dir) if args.cache_dir else root / "data/envelope/cache"
    f = cache / f"{args.segment}.npz"
    if "," not in args.segment and not f.exists():
        print(f"fy envelope check: no built segment at {_label(f, root)}; run `fy envelope build` first", file=sys.stderr)
        return 2
    if args.occupied and args.no_occupied:
        print("fy envelope check: --occupied and --no-occupied exclude each other", file=sys.stderr)
        return 2
    shapes, poses = oracle.read_shapes(args.shapes), oracle.read_poses(args.poses)
    names = args.segment.split(",")
    if "," in args.segment:
        import numpy as np
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
        offsets = [np.array(sg.meta["origin_xyz"]) - o0 for sg in segs]
        fo = [frames.segment_offset_mm(n, sg.meta) for n, sg in zip(names, segs)]          # each body's model-to-segment translation; the poses are in the first body's model frame
        out = oracle.clearance_union(list(zip(segs, offsets)), shapes, poses, args.required, frame_offset_mm=fo[0])
        seg = segs[0]
    else:
        seg = field.Segment.load(f)
        offsets = [(0.0, 0.0, 0.0)]
        fo = [frames.segment_offset_mm(args.segment, seg.meta)]
        segs = [seg]
        out = oracle.clearance(seg, shapes, poses, args.required, frame_offset_mm=fo[0])
    regs = []
    if not args.no_occupied:
        cdir = _components_dir(args, cache)
        for n, off in zip(names, offsets):
            r = registry.find(cdir, n)
            if r is not None:
                r.frame_offset_mm = fo[names.index(n)]
                regs.append((r, off, cdir / f"{n}.yaml"))
        if args.occupied and not regs:
            print(f"fy envelope check: --occupied, but there is no component registry for {args.segment} in {_label(cdir, root)}", file=sys.stderr)
            return 2
    print(f"segment {args.segment} (inputs {seg.meta.get('inputs_sha256_12', '?')}), {len(poses)} pose(s), {len(shapes)} shape(s)")
    for n, sg in zip(names, segs):
        line = frames.describe(n, sg.meta)
        if line:
            print(line)
    for i, (m, o) in enumerate(zip(out["margins_mm"], out["slab_overruns_mm"])):
        print(f"  pose {i}: margin {m:8.2f} mm   slab overrun {o:6.2f} mm")
    x, y, z = out["point_mm"]
    print(f"binds at pose {out['pose_index']} on {out['shape']}: margin {out['margin_mm']:.2f} mm at station {out['station_mm']:.1f} mm, point (x {x:.1f}, y {y:.1f}, z {z:.1f}) mm")
    print(f"slab overrun {out['slab_overrun_mm']:.2f} mm; required margin {out['required_mm']:.2f} mm")
    feasible = out["feasible"]
    if regs:
        skin_sd = seg.signed_distance if len(names) == 1 else occupancy.skin_field(list(zip(segs, offsets)), 0.0).signed_distance
        feasible = _report_components(root, seg, out, shapes, oracle.to_segment_frame(poses, fo[0]), regs, occupancy, skin_sd, fo[0]) and feasible
    print("FEASIBLE" if feasible else "INFEASIBLE")
    return 0 if feasible else 1


def _report_components(root, seg, skin, shapes, poses, regs, occupancy, skin_sd, frame_offset=(0.0, 0.0, 0.0)) -> bool:
    """Print the margin to each placed component, the binding constraint and the confidence; True when every component margin is at least 0. `poses` are in the first body's segment frame
    (already shifted from the model frame); points are printed back in the model frame by `frame_offset`."""
    import numpy as np
    poses = np.atleast_2d(np.asarray(poses, float))
    if poses.shape[1] == 3:
        poses = np.hstack([poses, np.zeros((len(poses), 3))])
    rows = []
    for reg, off, path in regs:
        shifted = poses - np.r_[np.asarray(off, float), 0.0, 0.0, 0.0]            # the candidate's poses in this registry's frame
        for e in occupancy.component_margins(shapes, shifted, reg, 0.0):
            e["point_mm"] = [float(p + o) for p, o in zip(e["point_mm"], off)]
            e["station_mm"] = seg.z_top - e["point_mm"][2]
            e["point_mm"] = [float(p - o) for p, o in zip(e["point_mm"], frame_offset)]
            origin = next((c.origin for c in reg.components if c.name == e["name"] and c.origin is not None), path)
            e["registry"] = _label(origin, root)
            rows.append(e)
        inside = occupancy.component_skin_margins(skin_sd, reg, off)
        for e in rows:
            if e["name"] in inside and "inside_skin_mm" not in e:
                e["inside_skin_mm"] = inside[e["name"]]
    print(f"components ({', '.join(sorted({_label(o, root) for reg, _, p in regs for o in (reg.origins() or [p])}))}): {len(rows)} placed")
    for e in rows:
        px, py, pz = e["point_mm"]
        sweep = f", sweep pose {e['component_pose_index']} of {e['sweep_poses']}" if e["sweep_poses"] > 1 else ""
        print(f"  {e['name']} [{e['status']}]: margin {e['margin_mm']:.2f} mm (distance {e['distance_mm']:.2f} - clearance {e['clearance_mm']:.2f}) at pose {e['pose_index']} on {e['shape']}{sweep}, "
              f"station {e['station_mm']:.1f} mm, point (x {px:.1f}, y {py:.1f}, z {pz:.1f}) mm")
        if e["inside_skin_mm"] < 0 and e["status"] != "foreign":
            print(f"    WARNING: {e['name']} sticks out of the skin by {-e['inside_skin_mm']:.2f} mm (a registry fault; it does not change the verdict)")
        if "bend" in e and not e["bend"]["ok"]:
            print(f"    WARNING: {e['name']} bends to {e['bend']['min_radius_mm']:.1f} mm, tighter than its bend_radius_mm {e['bend']['required_mm']:.1f}")
    # the binding constraint is the least slack: the skin's margin less what is required of it, a component's margin
    cands = [("skin", skin["margin_mm"] - skin["required_mm"], skin)] + [(f"component {e['name']}", e["margin_mm"], e) for e in rows]
    label, slack, b = min(cands, key=lambda c: c[1])
    bx, by, bz = b["point_mm"]
    print(f"binding constraint: {label}: slack {slack:.2f} mm at pose {b['pose_index']}, station {b['station_mm']:.1f} mm, point (x {bx:.1f}, y {by:.1f}, z {bz:.1f}) mm")
    if label != "skin":
        ex = occupancy.exact_binding_distance(b)
        if ex is not None:
            print("  exact mesh-to-mesh distance of the binding pair: " + ("the meshes overlap" if ex["interpenetrating"] else f"{ex['exact_mm']:.3f} mm (sampled {b['distance_mm']:.3f})"))
    print(f"voxel {seg.h:g} mm; confidence: {'clear' if abs(slack) >= seg.h else 'marginal'}")
    return all(e["margin_mm"] >= 0.0 for e in rows)


def cmd_foreign(args, root):
    import numpy as np
    from . import foreign
    place = [float(x) for x in args.placement.split(",")]
    if len(place) not in (3, 6):
        print("fy envelope foreign: --placement needs tx,ty,tz or tx,ty,tz,rx,ry,rz (mm, degrees)", file=sys.stderr)
        return 2
    place = place + [0.0] * (6 - len(place))
    model = foreign.load_model(args.model)
    if args.samples:
        names, angles = foreign.read_samples(args.samples)
        src = f"{_label(Path(args.samples), root)}"
    else:
        names, angles = foreign.default_samples(model, args.host)
        src = "the default hip sampling"
    poses = foreign.foreign_poses(model, args.owner, args.host, place, names, angles)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    foreign.write_poses(out, poses, f"{args.owner} part {','.join(f'{v:.10g}' for v in place)} in {args.host}, {src} ({len(poses)} poses), joints {','.join(names)}")
    print(f"{len(poses)} pose(s) of the {args.owner} part in the {args.host} frame ({src}); joints {', '.join(names)}")
    print("wrote", _label(out, root))
    return 0


def cmd_free(args, root):
    import json
    import numpy as np
    import yaml
    from . import bundle, field, frames, ledger, occupancy, registry, trial
    cache = Path(args.cache_dir) if args.cache_dir else root / "data/envelope/cache"
    names = [args.segment] + ([args.union] if args.union else [])
    segs = []
    for n in names:
        fn = cache / f"{n}.npz"
        if not fn.exists():
            print(f"fy envelope free: no built segment at {_label(fn, root)}; run `fy envelope build` first", file=sys.stderr)
            return 2
        segs.append(field.Segment.load(fn))
    if args.union and any("origin_xyz" not in sg.meta for sg in segs):
        print("fy envelope free: a union needs the bodies' origins; rebuild with `fy envelope build`", file=sys.stderr)
        return 2
    o0 = np.array(segs[0].meta.get("origin_xyz", [0.0, 0.0, 0.0]))
    offsets = [np.array(sg.meta.get("origin_xyz", [0.0, 0.0, 0.0])) - o0 for sg in segs]
    cdir = _components_dir(args, cache)
    fo = {n: frames.segment_offset_mm(n, sg.meta) for n, sg in zip(names, segs)}              # model body frame -> the built segment's frame, per body (zero for a leg)
    regs = []
    for n, off in zip(names, offsets):
        r = registry.find(cdir, n)
        if r is not None:
            r.frame_offset_mm = fo[n]
            regs.append((r, off))
    zone = trial.HIP_ZONE_MM if args.segment.startswith("thigh") else 0.0              # the thigh's hip zone is reported apart, as in its ledger
    virt, rep = occupancy.free_field(list(zip(segs, offsets)), regs, args.required, zone)
    sha = occupancy.inputs_hash({n: sg.meta.get("inputs_sha256_12", "?") for n, sg in zip(names, segs)}, regs, args.required, names[1:])
    side = "right" if args.segment.endswith("_R") else ("left" if args.segment.endswith("_L") else "trunk")
    rows = ledger.rows_for(virt, side)
    tag = "+".join(names)
    s = rep["largest_free_sphere"]
    hdr = {"segment": args.segment, "union": names[1:], "frame": "the first segment's frame: z up, x anterior, y left; stations are distances below the topmost plane",
           "required_skin_margin_mm": args.required, "voxel_mm": virt.h, "length_mm": round(virt.length, 2),
           "skin_volume_l": round(rep["skin_volume_l"], 4), "free_volume_l": round(rep["free_volume_l"], 4), "occupied_volume_l": round(rep["occupied_volume_l"], 4),
           "largest_free_sphere": {"diameter_mm": round(s["diameter_mm"], 2), "centre_mm": [round(v, 2) for v in s["centre_mm"]], "station_mm": round(s["station_mm"], 2), "searched_from_station_mm": zone},
           "components": rep["components"], "registries": [f"components/{r.segment}.yaml" for r, _ in regs] if not any(o.parent.name == registry.CAD_SUBDIR for r, _ in regs for o in r.origins())
                         else sorted({f"components/{'cad/' if o.parent.name == registry.CAD_SUBDIR else ''}{o.name}" for r, _ in regs for o in r.origins()}),
           "directions": {str(a): n for a, n in ledger.direction_names(side).items()}, "inputs_sha256_12": sha, "rows": rows}
    fl = [l for l in (frames.describe(n, sg.meta) for n, sg in zip(names, segs)) if l]
    if fl:
        hdr["model_frames"] = fl                  # a trunk free field is quoted in the oracle's frame; its registry is authored in the model frame (brief 7)
    out = (Path(args.out) if args.out else root / "data/envelope") / "free"
    out.mkdir(parents=True, exist_ok=True)
    text = (f"# GENERATED by fy envelope free from the built segment(s), the component registry and the arguments (inputs sha256:{sha}). Do not edit; change the inputs and rerun.\n"
            + yaml.safe_dump(hdr, sort_keys=True, default_flow_style=None, allow_unicode=True, width=100000))
    (out / f"{tag}.yaml").write_text(text, encoding="utf-8", newline="\n")
    print(f"free field of {tag} (skin margin >= {args.required:g} mm, {len(rep['components'])} component(s), voxel {virt.h:g} mm):")
    for l in fl:
        print("  " + l)
    print(f"  skin volume {rep['skin_volume_l']:.4f} l; free {rep['free_volume_l']:.4f} l; occupied {rep['occupied_volume_l']:.4f} l")
    print(f"  largest free sphere: diameter {s['diameter_mm']:.1f} mm at (x {s['centre_mm'][0]:.1f}, y {s['centre_mm'][1]:.1f}, z {s['centre_mm'][2]:.1f}) mm, station {s['station_mm']:.1f} mm" + (f" (searched from station {zone:g} mm: the hip zone is left out)" if zone else ""))
    print("wrote", _label(out / f"{tag}.yaml", root))
    insp = cache / "inspect"
    if (insp / "inspect.json").exists():
        inp = trial.load_inputs(root, Path(args.mesh) if args.mesh else root / "data/makehuman/freyja-body-v2.obj")
        V, F = bundle.marching_tetrahedra(np.where(virt.region, virt.sd.astype(float), -1.0e3), virt.o + virt.h / 2, virt.h, 0.0)
        bundle.write_obj(insp / f"free_{tag}.obj", bundle.to_mh_dm(V + o0, inp), F)
        j = json.loads((insp / "inspect.json").read_text(encoding="utf-8"))
        j.setdefault("free_space", {})[tag] = f"free_{tag}.obj"
        (insp / "inspect.json").write_text(json.dumps(j, indent=1, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
        print("wrote the inspect layer", _label(insp / f"free_{tag}.obj", root))
    return 0


def main(argv=None, default_root=None) -> int:
    root = Path(default_root) if default_root else REPO
    ap = argparse.ArgumentParser(prog="fy envelope", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    _common(sub.add_parser("build"))
    _common(sub.add_parser("gates"))
    sub.add_parser("ratios")
    o = sub.add_parser("offsets")
    o.add_argument("--cache-dir"), o.add_argument("--out")
    o.add_argument("--tilt", type=float, help="design pelvis tilt in degrees (default the snapshot's stand_pelvis_tilt_deg)")
    rs = sub.add_parser("reserve")
    rs.add_argument("--cache-dir"), rs.add_argument("--out")
    rs.add_argument("--required", type=float, default=5.0, help="skin margin t in mm that the modules and the free field keep (default 5, the design shell)")
    co = sub.add_parser("corridor")
    co.add_argument("--cache-dir"), co.add_argument("--out")
    co.add_argument("--required", type=float, default=5.0, help="skin margin t in mm (default 5, the design shell)")
    hp = sub.add_parser("hip")
    hp.add_argument("--cache-dir"), hp.add_argument("--out"), hp.add_argument("--mesh")
    hp.add_argument("--no-alternative", action="store_true", help="skip the rebuild under the other shear target")
    t = sub.add_parser("trunk")
    t.add_argument("--mesh"), t.add_argument("--out"), t.add_argument("--cache-dir")
    t.add_argument("--n", type=int, default=200, help="Monte Carlo samples")
    c = sub.add_parser("check")
    c.add_argument("--segment", required=True), c.add_argument("--shapes", required=True), c.add_argument("--poses", required=True)
    c.add_argument("--required", type=float, default=0.0, help="required clearance in mm (default 0: inside the skin)")
    c.add_argument("--cache-dir")
    c.add_argument("--occupied", action="store_true", help="require the segment's component registry and check against it (default: use it when it exists)")
    c.add_argument("--no-occupied", action="store_true", help="ignore the component registry")
    c.add_argument("--components-dir", help="default <cache-dir>/../components")
    fo = sub.add_parser("foreign")
    fo.add_argument("--owner", required=True), fo.add_argument("--host", required=True), fo.add_argument("--placement", required=True), fo.add_argument("--out", required=True)
    fo.add_argument("--samples"), fo.add_argument("--model")
    fr = sub.add_parser("free")
    fr.add_argument("--segment", required=True)
    fr.add_argument("--required", type=float, default=0.0, help="margin kept from the skin in mm (default 0)")
    fr.add_argument("--union", help="an adjacent built body whose space joins the segment's (brief 5's union query)")
    fr.add_argument("--cache-dir"), fr.add_argument("--components-dir"), fr.add_argument("--out"), fr.add_argument("--mesh")
    args = ap.parse_args(argv)
    from . import sheet
    try:
        return {"build": cmd_build, "gates": cmd_gates, "check": cmd_check, "free": cmd_free, "foreign": cmd_foreign, "ratios": cmd_ratios, "trunk": cmd_trunk, "offsets": cmd_offsets, "reserve": cmd_reserve, "corridor": cmd_corridor, "hip": cmd_hip}[args.cmd](args, root)
    except sheet.StopAndAsk as e:
        print(f"fy envelope: STOP, ask Joe: {e}", file=sys.stderr)
        return 3
    except NotImplementedError as e:
        print(f"fy envelope: {e}", file=sys.stderr)
        return 2
