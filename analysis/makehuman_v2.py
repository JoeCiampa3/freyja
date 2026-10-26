"""The v2 sculpt: the .mhm derived from v1 by the three slider changes memo 30 found, and the readouts MakeHuman's Measure and Statistics boxes show.

    python analysis/makehuman_v2.py write-mhm            # data/makehuman/freyja-body-v2.mhm from the committed v1
    python analysis/makehuman_v2.py predict --base B --targets T --out data/envelope/v2_prediction.json

v1 is never written. The prediction rebuilds the v1 and v2 meshes at rest with the attribution script's rule (base.obj plus weighted targets), so it is only
as good as that script's check against the exported OBJ; the readouts are MakeHuman's own arithmetic (`Ruler.getMeasure`: the summed distances between
consecutive listed vertices, open unless the list repeats its first vertex, x10 for dm -> cm; the Statistics height is the body mesh's bounding box in y).
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "analysis"))
import makehuman_attribution as A  # noqa: E402

V1_MHM = REPO / "data/makehuman/freyja-body-v1.mhm"
V2_MHM = REPO / "data/makehuman/freyja-body-v2.mhm"
V1_MHM_SHA256_12 = "a6c2ba83452d"          # of the LF form, as committed
HEIGHT = "macrodetails-height/Height"
UPPER = "measure/measure-upperleg-height-decr|incr"
LOWER = "measure/measure-lowerleg-height-decr|incr"
V2_CHANGES = {HEIGHT: 0.625, UPPER: 0.269, LOWER: -0.515}     # memo 30, section 5; stature unchanged, knee and hip land on the sheet's fractions
HIPS_LINE = "modifier measure/measure-hips-circ-decr|incr"


def v2_mhm_text(v1_text: str) -> str:
    """v1's text with Height 0.623 -> 0.625, the two leg-height measures added after the hips measure, and the pose line removed. Nothing else."""
    lines = v1_text.replace("\r\n", "\n").split("\n")
    out, seen = [], {"height": False, "hips": False, "pose": False}
    for line in lines:
        if line == f"modifier {HEIGHT} 0.623000":
            out.append(f"modifier {HEIGHT} {V2_CHANGES[HEIGHT]:.6f}")
            seen["height"] = True
        elif line.startswith("pose "):
            seen["pose"] = True
        else:
            out.append(line)
            if line.startswith(HIPS_LINE + " "):
                out.append(f"modifier {UPPER} {V2_CHANGES[UPPER]:.6f}")
                out.append(f"modifier {LOWER} {V2_CHANGES[LOWER]:.6f}")
                seen["hips"] = True
    if not all(seen.values()):
        raise ValueError(f"v1 is not the file this edit was written for (missing: {[k for k, v in seen.items() if not v]})")
    return "\n".join(out)


def mh_measure_cm(V, ids) -> float:
    """MakeHuman's Ruler.getMeasure in cm for vertices V in dm: the sum of the distances between consecutive listed vertices, starting from the first."""
    V = np.asarray(V)
    ids = list(ids)
    return float(10.0 * sum(np.linalg.norm(V[a] - V[b]) for a, b in zip(ids, ids[1:])))


def height_cm(V, n_body=A.BODY_VERTICES) -> float:
    """The Statistics height: bounding box of the body mesh in y (dm) x 10."""
    y = np.asarray(V)[:n_body, 1]
    return float(10.0 * (y.max() - y.min()))


def readouts(V, measures) -> dict:
    """Every Measure-tab box (cm, keyed by the measure name) plus the Statistics height; the Statistics chest, waist and hips are the bust, waist and hips boxes."""
    out = {k.split("measure-")[1].split("-decr")[0]: mh_measure_cm(V, ids) for k, ids in measures.items()}
    out["statistics_height"] = height_cm(V)
    return out


def loop_heights_mm(V, measures, keys=("thigh-circ", "knee-circ", "calf-circ", "ankle-circ")) -> dict:
    """Mean height above the body's lowest vertex (mm) and plane-fit tilt (deg) of the leg girth loops."""
    V = np.asarray(V)
    sole = V[: A.BODY_VERTICES, 1].min()
    out = {}
    for key in keys:
        ids = measures[f"measure/measure-{key}-decr|incr"]
        P = V[list(ids)]
        c = P.mean(axis=0)
        n = np.linalg.svd(P - c)[2][2]
        out[key] = {"z_mm": float((c[1] - sole) * A.DM_TO_MM), "tilt_deg": float(np.degrees(np.arccos(min(1.0, abs(n[1])))))}
    return out


def predict(base_path, targets_dir, ruler_path=A.REPO / "data/makehuman/ruler_measures.json", obj_path=A.REPO / "data/makehuman/freyja-body-v1.obj") -> dict:
    base = A.read_obj_vertices(base_path, include_helpers=True)
    T = A.Targets(targets_dir)
    measures = json.loads(Path(ruler_path).read_text())["measures"]
    v1 = A.read_mhm(V1_MHM)
    v2 = A.read_mhm_text(v2_mhm_text(V1_MHM.read_text()))
    meshes = {"v1 as MakeHuman showed it (committed OBJ, posed standing02)": np.vstack([A.read_obj_vertices(obj_path), base[A.BODY_VERTICES:]]),
              "v1 rebuilt at rest (no pose)": T.mesh(base, v1),
              "v2 predicted (rest, unposed)": T.mesh(base, v2)}
    chords = {"upper": measures[UPPER], "lower": measures[LOWER]}
    out = {"v2_changes": V2_CHANGES, "rows": {}, "knee_hip": {}, "girth_loops": {}}
    for label, V in meshes.items():
        out["rows"][label] = readouts(V, measures)
        out["knee_hip"][label] = A.knee_metrics(V, chords)
        out["girth_loops"][label] = loop_heights_mm(V, measures)
    out["targets_used"] = sorted(T.used)
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("write-mhm")
    p = sub.add_parser("predict")
    p.add_argument("--base", default=str(REPO / "data/makehuman/base.obj")), p.add_argument("--targets", required=True)
    p.add_argument("--out", default=str(REPO / "data/envelope/v2_prediction.json")), p.add_argument("--used-out")
    a = ap.parse_args(argv)
    if a.cmd == "write-mhm":
        V2_MHM.write_text(v2_mhm_text(V1_MHM.read_text()), encoding="utf-8", newline="\n")
        print(f"wrote {V2_MHM.relative_to(REPO)}")
        return 0
    res = predict(a.base, a.targets)
    used = res.pop("targets_used")
    if a.used_out:
        Path(a.used_out).write_text(json.dumps(used))
    Path(a.out).write_text(json.dumps(res, indent=1, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    print(f"wrote {a.out}; {len(used)} target files read")
    return 0


if __name__ == "__main__":
    sys.exit(main())
