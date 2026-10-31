"""The v3 sculpt (adr-0042 D3, brief 10): v2 plus the pinned arm-length targets at the weights that close each arm segment on the adr-0042 D1 nodes.

    python analysis/makehuman_v3.py solve [--forearm-only] [--sjc X Y Z]      # the weights: D1 node-to-node length = sheet within 0.1 mm, the D1 nodes recomputed at every step
    python analysis/makehuman_v3.py write [--upper W] [--lower W] [--out DIR]  # freyja-body-v3.obj and .mhm, by default into data/makehuman/cache/v3-candidate (gitignored)
    python analysis/makehuman_v3.py compare [--candidate OBJ] [--export OBJ]   # the MakeHuman export of the .mhm against the scripted mesh

v3 is generated, never exported by hand: the targets come through the manifest (data/makehuman/mhm_sources.json) and their hashes are verified, a target's deltas are added at its weight to the
body vertices of v2's OBJ (13,380; helper deltas are ignored) and every other byte of the OBJ stays but the material file's name, so topology, face order, UVs, line endings and the four-decimal
format are v2's. The OBJ and the .mhm carry the same six-decimal weights. Memo 52's in-memory evaluation against C1 to C4 patched `tools/envelope/arms.py` before it held the rule; that code is at
commit 5dcd23f. Since the baseline switch `fy envelope gates` is the evaluation.
"""
from __future__ import annotations

import argparse
import dataclasses
import json
import sys
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "analysis"))
sys.path.insert(0, str(REPO / "tools"))
import makehuman_fetch as fetch  # noqa: E402
from envelope import arms, meshio, trial  # noqa: E402

V2_OBJ = REPO / "data/makehuman/freyja-body-v2.obj"
V2_MHM = REPO / "data/makehuman/freyja-body-v2.mhm"
CANDIDATE = REPO / "data/makehuman/cache/v3-candidate"
EXPORT = REPO / "data/makehuman/cache/v3-makehuman-export/freyja-body-v3.obj"
TARGETS = REPO / "data/makehuman/cache/targets"
MANIFEST = REPO / "data/makehuman/mhm_sources.json"
UPPER_REL, LOWER_REL = "measure/measure-upperarm-length-incr.target", "measure/measure-lowerarm-length-incr.target"
UPPER_MOD, LOWER_MOD = "measure/measure-upperarm-length-decr|incr", "measure/measure-lowerarm-length-decr|incr"
AFTER_MOD = "modifier measure/measure-lowerleg-height-decr|incr "                # v2's last measure line; the arm lines follow it
V3_WEIGHTS = {"upper": 0.381365, "lower": 0.512871}                             # `solve`, memo 52
V2_SJC_MM = (15.56705094025046, -192.328859146, 1349.2379236001505)             # the SJC of the registration on v2 (memo 52), the fixed point of `solve`; it moves 0.007 mm on v3
LENGTH_TOL_MM = 0.1            # adr-0042 D3
EXPORT_TOL_MM = 0.02           # Joe, Phase 3: the MakeHuman export against the scripted mesh, largest body-vertex difference
SOLVE_STEP = 0.01              # the weight step of the finite-difference Jacobian; the lengths are close to linear in the weights


def read_verified_target(manifest: dict, folder, rel: str, n_body: int) -> np.ndarray:
    """The target's deltas (n_body, 3) in the OBJ's own axes and units (decimetres, MakeHuman axes), after checking the file against the manifest; helper vertices are dropped."""
    p = Path(folder) / rel
    data = p.read_bytes()
    if fetch.sha256(data) != manifest["files"][rel]["sha256"]:
        raise ValueError(f"{rel}: the file's hash differs from the manifest")
    D = np.zeros((n_body, 3))
    for line in data.decode("utf-8").splitlines():
        if line and not line.startswith("#"):
            s = line.split()
            if int(s[0]) < n_body:
                D[int(s[0])] = [float(s[1]), float(s[2]), float(s[3])]
    return D


def v3_obj_bytes(v2: bytes, delta: np.ndarray, n_body: int = meshio.BODY_VERTICES) -> bytes:
    """v2's OBJ with `delta` (n_body, 3; decimetres) added to its v lines and its mtllib line naming v3's material file. A vertex with no delta keeps its line byte for byte."""
    lines = v2.split(b"\n")
    at = [i for i, s in enumerate(lines) if s.startswith(b"v ")]
    if len(at) != n_body or len(delta) != n_body:
        raise ValueError(f"the OBJ has {len(at)} vertices, delta {len(delta)}, expected {n_body}")
    for i, d in zip(at, delta):
        if np.any(d != 0.0):
            cr = lines[i].endswith(b"\r")
            p = np.array(lines[i].split()[1:4], float) + d
            lines[i] = (f"v {p[0]:.4f} {p[1]:.4f} {p[2]:.4f}").encode("ascii") + (b"\r" if cr else b"")
    return b"\n".join(s.replace(b"freyja-body-v2.mtl", b"freyja-body-v3.mtl") if s.startswith(b"mtllib ") else s for s in lines)


def v3_mhm_text(v2_text: str, upper, lower) -> str:
    """v2's text with the arm modifier lines after its last measure line, in its format. A weight of None leaves that line out (the forearm-only fallback)."""
    out, seen = [], False
    for line in v2_text.split("\n"):
        out.append(line)
        if line.startswith(AFTER_MOD):
            seen = True
            out += [f"modifier {m} {w:.6f}" for m, w in ((UPPER_MOD, upper), (LOWER_MOD, lower)) if w is not None]
    if not seen:
        raise ValueError("v2's .mhm is not the file this edit was written for")
    return "\n".join(out)


def write_candidate(upper, lower, out=CANDIDATE) -> dict:
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    delta = np.zeros((meshio.BODY_VERTICES, 3))
    for rel, w in ((UPPER_REL, upper), (LOWER_REL, lower)):
        if w:
            delta += w * read_verified_target(manifest, TARGETS, rel, meshio.BODY_VERTICES)
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    (out / "freyja-body-v3.obj").write_bytes(v3_obj_bytes(V2_OBJ.read_bytes(), delta))
    (out / "freyja-body-v3.mhm").write_text(v3_mhm_text(V2_MHM.read_text(encoding="utf-8"), upper, lower), encoding="utf-8", newline="\n")
    return {"topology_vs_v2": meshio.topology_difference(out / "freyja-body-v3.obj", V2_OBJ), "sha256_12": {f: fetch.sha256((out / f).read_bytes())[:12] for f in ("freyja-body-v3.obj", "freyja-body-v3.mhm")},
            "vertices_moved": int(np.any(delta != 0.0, axis=1).sum()), "max_delta_mm": float(np.linalg.norm(delta, axis=1).max() * meshio.DM_TO_MM)}


def compare_export(candidate, export) -> dict:
    """The export against the scripted mesh: Joe's test (same topology and vertex count, largest body-vertex difference at most EXPORT_TOL_MM) and, per axis, the affine fit of one to the other, which
    shows a uniform scale or offset (an export setting) if there is one."""
    va, pa = meshio.read_obj(candidate)
    vb, pb = meshio.read_obj(export)
    same = len(va) == len(vb) and pa == pb
    out = {"vertices": [len(va), len(vb)], "polygons": [len(pa), len(pb)], "same_topology": bool(same)}
    if len(va) == len(vb):
        d = (vb - va) * meshio.DM_TO_MM
        m = np.linalg.norm(d, axis=1)
        fit = [np.linalg.lstsq(np.c_[va[:, i], np.ones(len(va))], vb[:, i], rcond=None)[0] for i in range(3)]
        out |= {"max_difference_mm": float(m.max()), "mean_difference_mm": float(m.mean()), "mean_offset_mm": d.mean(axis=0).tolist(), "scale_per_axis": [float(f[0]) for f in fit],
                "offset_per_axis_mm": [float(f[1] * meshio.DM_TO_MM) for f in fit], "tolerance_mm": EXPORT_TOL_MM}
    out["pass"] = bool(same and out.get("max_difference_mm", np.inf) <= EXPORT_TOL_MM)
    return out


def solve_weights(lengths, target, start, tol_mm=1e-3, max_iter=12) -> np.ndarray:
    """Newton on lengths(w) = target with a finite-difference Jacobian. The arms' weights couple through the elbow node, so the two are solved together."""
    w = np.asarray(start, float)
    for _ in range(max_iter):
        f = lengths(w) - target
        if np.abs(f).max() < tol_mm:
            break
        J = np.column_stack([(lengths(w + SOLVE_STEP * e) - target - f) / SOLVE_STEP for e in np.eye(len(w))])
        w = w - np.linalg.solve(J, f)
    return w


def solve(forearm_only=False, sjc=None) -> dict:
    """The weights on v2, with the committed registration's Ruler vertex ids and the sheet's lengths. `sjc` (mesh frame, mm) replaces V2_SJC_MM."""
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    inp = trial.load_inputs(REPO, V2_OBJ)
    D = {k: meshio.to_sheet_mm(read_verified_target(manifest, TARGETS, rel, meshio.BODY_VERTICES)) for k, rel in (("upper", UPPER_REL), ("lower", LOWER_REL))}
    ids = json.loads((REPO / "data/envelope/arm_bodies.json").read_text(encoding="utf-8"))["registration"]["vertex_ids"]
    sheet = arms.sheet_arm(REPO / "params/snapshot.csv")
    sjc_ = np.asarray(sjc if sjc is not None else V2_SJC_MM, float)
    L = {n: sheet[n]["length_mm"] for n in ("upper_arm", "forearm")}
    target = np.array([L["upper_arm"], L["forearm"]])

    def lengths_at(wu, wl):
        V = inp.V + wu * D["upper"] + wl * D["lower"]
        B = arms.d1_nodes(V, inp.F, sjc_, 0.5 * (V[ids["upper_arm_chord_end"]] + V[ids["forearm_chord_start"]]), V[ids["forearm_chord_end"]], L)
        return np.array([np.linalg.norm(B["elbow"] - sjc_), np.linalg.norm(B["wrist"] - B["elbow"])])
    if forearm_only:
        w = solve_weights(lambda x: lengths_at(0.0, x[0])[1:], target[1:], (0.4,))
        wu, wl = None, round(float(w[0]), 6)
    else:
        w = solve_weights(lambda x: lengths_at(x[0], x[1]), target, (0.4, 0.4))
        wu, wl = round(float(w[0]), 6), round(float(w[1]), 6)
    final = lengths_at(wu or 0.0, wl)
    return {"weights": {"upper": wu, "lower": wl}, "lengths_mm": final.tolist(), "sheet_mm": target.tolist(), "residual_mm": (final - target).tolist(), "v2_lengths_mm": lengths_at(0.0, 0.0).tolist(),
            "tolerance_mm": LENGTH_TOL_MM, "in_bounds": all(x is None or 0.0 <= x <= 1.0 for x in (wu, wl)), "sjc_mesh_mm": sjc_.tolist()}


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("solve")
    p.add_argument("--forearm-only", action="store_true"), p.add_argument("--sjc", nargs=3, type=float)
    p = sub.add_parser("write")
    p.add_argument("--upper", type=float, default=V3_WEIGHTS["upper"]), p.add_argument("--lower", type=float, default=V3_WEIGHTS["lower"]), p.add_argument("--out", default=str(CANDIDATE))
    p = sub.add_parser("compare")
    p.add_argument("--candidate", default=str(CANDIDATE / "freyja-body-v3.obj")), p.add_argument("--export", default=str(EXPORT))
    a = ap.parse_args(argv)
    if a.cmd == "solve":
        res = solve(a.forearm_only, a.sjc)
    elif a.cmd == "write":
        res = write_candidate(a.upper, a.lower, a.out)
    else:
        res = compare_export(a.candidate, a.export)
    print(json.dumps(res, indent=1, sort_keys=True, default=float))
    return 0 if a.cmd != "compare" or res["pass"] else 1


if __name__ == "__main__":
    sys.exit(main())
