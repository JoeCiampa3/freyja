"""Attribute the sculpt's knee-height shift versus MakeHuman's base mesh to the modifiers in the committed .mhm, and find the slider changes that remove it.

Report only: nothing here edits the sculpt. The mesh is rebuilt the way MakeHuman builds it, base.obj plus the weighted sum of the .target files, with the
weights from human.py (`_set*Vals`) and humanmodifier.py (macro targets weighted by the product of their variables' values, universal modifiers by
-min(v, 0) and max(v, 0)). The rebuild is checked against the committed OBJ first; the attribution is only as good as that check.

    python analysis/makehuman_attribution.py --base base.obj --targets DIR --out data/envelope/sculpt_attribution.json

`base.obj` is committed at data/makehuman/base.obj and DIR is the folder `python analysis/makehuman_fetch.py` fills (default
data/makehuman/cache/targets, gitignored), both pinned by hash in data/makehuman/mhm_sources.json; all CC0. The output records the hashes. The knee is the one the trial uses:
the mean of the lower end of the Ruler upper-leg chord and the upper end of the lower-leg chord, as a fraction of stature (top of head over the sole).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[1]
BODY_VERTICES = 13380
DM_TO_MM = 100.0
CATEGORIES = {"gender": ["male", "female"], "age": ["baby", "child", "young", "old"], "race": ["caucasian", "asian", "african"],
              "muscle": ["maxmuscle", "averagemuscle", "minmuscle"], "weight": ["minweight", "averageweight", "maxweight"],
              "height": ["minheight", "averageheight", "maxheight"], "breastsize": ["mincup", "averagecup", "maxcup"],
              "breastfirmness": ["minfirmness", "averagefirmness", "maxfirmness"], "bodyproportions": ["uncommonproportions", "regularproportions", "idealproportions"]}
VARIABLE_TOKENS = {v for vs in CATEGORIES.values() for v in vs}
MACRO_DEFAULTS = {"macrodetails/Gender": 0.5, "macrodetails/Age": 0.5, "macrodetails/African": 1 / 3, "macrodetails/Asian": 1 / 3, "macrodetails/Caucasian": 1 / 3,
                  "macrodetails-universal/Muscle": 0.5, "macrodetails-universal/Weight": 0.5, "macrodetails-height/Height": 0.5,
                  "macrodetails-proportions/BodyProportions": 0.5, "breast/BreastSize": 0.5, "breast/BreastFirmness": 0.5}


# ---- weights, after MakeHuman's human.py ---------------------------------------------------------------------------------------------

def macro_values(state) -> dict:
    """The `...Val` attributes of MakeHuman's human object for the macro modifier values in `state`."""
    v = {}
    g = state["macrodetails/Gender"]
    v["male"], v["female"] = g, 1 - g
    a = state["macrodetails/Age"]
    if a < 0.5:
        v["old"] = 0.0
        v["baby"] = max(0.0, 1 - a * 5.333)
        v["young"] = max(0.0, (a - 0.1875) * 3.2)
        v["child"] = max(0.0, min(1.0, 5.333 * a) - v["young"])
    else:
        v["child"] = v["baby"] = 0.0
        v["old"] = max(0.0, a * 2 - 1)
        v["young"] = 1 - v["old"]

    def three(x, lo, mid, hi, mid_rule):
        v[hi] = max(0.0, x * 2 - 1)
        v[lo] = max(0.0, 1 - x * 2)
        v[mid] = (1 - (v[hi] + v[lo])) if mid_rule == "sum" else ((1 - v[hi]) if v[hi] > v[lo] else (1 - v[lo]))

    three(state["macrodetails-universal/Weight"], "minweight", "averageweight", "maxweight", "sum")
    three(state["macrodetails-universal/Muscle"], "minmuscle", "averagemuscle", "maxmuscle", "sum")
    three(state["macrodetails-height/Height"], "minheight", "averageheight", "maxheight", "branch")
    three(state["macrodetails-proportions/BodyProportions"], "uncommonproportions", "regularproportions", "idealproportions", "branch")
    three(state["breast/BreastSize"], "mincup", "averagecup", "maxcup", "branch")
    three(state["breast/BreastFirmness"], "minfirmness", "averagefirmness", "maxfirmness", "branch")
    eth = {"african": state["macrodetails/African"], "asian": state["macrodetails/Asian"], "caucasian": state["macrodetails/Caucasian"]}
    tot = sum(eth.values())
    for k, x in eth.items():
        v[k] = x / tot                                   # MakeHuman keeps the three summing to 1
    return v


def parse_target(rel: str):
    """(variable tokens, key tokens) of a target path relative to the targets folder, the way MakeHuman's targets crawler splits it."""
    toks = re.split(r"[/\-]", rel[: -len(".target")])
    return [t for t in toks if t in VARIABLE_TOKENS], [t for t in toks if t not in VARIABLE_TOKENS]


def target_weights(files, state, vals) -> dict:
    """path -> weight for every target file the state activates."""
    w = {}
    for rel in files:
        variables, _ = parse_target(rel)
        if variables:
            x = 1.0
            for t in variables:
                x *= vals[t]
            if x > 0:
                w[rel] = x
    for name, value in state.items():
        if name in MACRO_DEFAULTS or value == 0:
            continue
        group, mod = name.split("/", 1)
        m = re.match(r"^(.*)-([A-Za-z]+)\|([A-Za-z]+)$", mod)
        if m:
            base, left, right = m.groups()
            rel = f"{group}/{base}-{left if value < 0 else right}.target"
            if rel in files:
                w[rel] = w.get(rel, 0.0) + abs(value)
            else:
                raise KeyError(f"no target {rel} for modifier {name}")
        else:
            rel = f"{group}/{mod}.target"
            if rel not in files:
                raise KeyError(f"no target {rel} for modifier {name}")
            w[rel] = w.get(rel, 0.0) + max(0.0, value)
    return w


def read_mhm_text(text) -> dict:
    out = {}
    for line in text.splitlines():
        p = line.split()
        if len(p) == 3 and p[0] == "modifier":
            out[p[1]] = float(p[2])
    return out


def read_mhm(path) -> dict:
    return read_mhm_text(Path(path).read_text())


class Targets:
    def __init__(self, folder):
        self.folder = Path(folder)
        if not self.folder.is_dir():
            raise FileNotFoundError(f"{folder}: no targets folder; run `python analysis/makehuman_fetch.py`")
        self.files = sorted(str(p.relative_to(self.folder)).replace("\\", "/") for p in self.folder.rglob("*.target"))
        self._cache = {}
        self.used = set()                                # every target file read, for the pinned manifest

    def load(self, rel):
        self.used.add(rel)
        if rel not in self._cache:
            idx, d = [], []
            for line in (self.folder / rel).read_text().splitlines():
                if line and not line.startswith("#"):
                    p = line.split()
                    idx.append(int(p[0]))
                    d.append([float(p[1]), float(p[2]), float(p[3])])
            self._cache[rel] = (np.array(idx, int), np.array(d, float).reshape(-1, 3))
        return self._cache[rel]

    def mesh(self, base, state) -> np.ndarray:
        full = dict(MACRO_DEFAULTS)
        full.update(state)
        w = target_weights(self.files, full, macro_values(full))
        V = base.copy()
        for rel, x in w.items():
            i, d = self.load(rel)
            V[i] += x * d
        return V


# ---- measuring ---------------------------------------------------------------------------------------------------------------------

def read_obj_vertices(path, include_helpers=False):
    """The OBJ's vertices. MakeHuman's base.obj carries helper geometry after the body's BODY_VERTICES; unless the caller opts in with `include_helpers`, only the body is returned, so a
    result computed from base.obj cannot pick the helpers up by accident. Targets are applied to, and the rebuild is made on, the whole array, so those callers opt in."""
    V = np.array([[float(t) for t in line.split()[1:4]] for line in Path(path).read_text().splitlines() if line.startswith("v ")])
    return V if include_helpers else V[:BODY_VERTICES]


def knee_metrics(V, chords) -> dict:
    """Heights (mm) above the sole in the OBJ's y axis, stature and the knee-height fraction used by the trial."""
    body = V[:BODY_VERTICES, 1]
    sole, top = body.min(), body.max()
    up = V[chords["upper"], 1]
    lo = V[chords["lower"], 1]
    knee = (up.min() + lo.max()) / 2
    return {"stature_mm": (top - sole) * DM_TO_MM, "knee_mm": (knee - sole) * DM_TO_MM, "knee_fraction": (knee - sole) / (top - sole),
            "hip_mm": (up.max() - sole) * DM_TO_MM, "hip_fraction": (up.max() - sole) / (top - sole)}


def solve(f, lo, hi, n=41):
    """Smallest-|v| root of f on [lo, hi] by sampling then linear interpolation; None when f does not change sign. Also returns the samples' range."""
    xs = np.linspace(lo, hi, n)
    ys = np.array([f(x) for x in xs])
    roots = []
    for i in range(n - 1):
        if ys[i] == 0:
            roots.append(xs[i])
        elif ys[i] * ys[i + 1] < 0:
            roots.append(xs[i] - ys[i] * (xs[i + 1] - xs[i]) / (ys[i + 1] - ys[i]))
    return (min(roots, key=abs) if roots else None), (float(ys.min()), float(ys.max()))


GROUPS = {   # modifier group -> the modifiers it sets in the .mhm
    "gender": ["macrodetails/Gender"], "age": ["macrodetails/Age"], "ethnicity": ["macrodetails/African", "macrodetails/Asian", "macrodetails/Caucasian"],
    "muscle": ["macrodetails-universal/Muscle"], "weight": ["macrodetails-universal/Weight"], "height": ["macrodetails-height/Height"],
    "body proportions": ["macrodetails-proportions/BodyProportions"],
    "body shapes": ["bodyshapes/bodyshapes-elvs-fem-neat-hourglass", "bodyshapes/bodyshapes-elvs-fem-invert-triangle"], "pelvis bulge": ["pelvis/bulge-decr|incr"],
    "breast": ["breast/BreastSize", "breast/BreastFirmness", "breast/breast-dist-decr|incr", "breast/breast-volume-vert-down|up"],
    "measure bust / underbust / waist / hips": ["measure/measure-bust-circ-decr|incr", "measure/measure-underbust-circ-decr|incr",
                                                "measure/measure-waist-circ-decr|incr", "measure/measure-hips-circ-decr|incr"],
}
SLIDERS = {   # candidate sliders for removing the shift: name -> (modifier, lowest, highest)
    "Height": ("macrodetails-height/Height", 0.0, 1.0), "BodyProportions": ("macrodetails-proportions/BodyProportions", 0.0, 1.0),
    "Age": ("macrodetails/Age", 0.1875, 0.5), "Weight": ("macrodetails-universal/Weight", 0.0, 1.0), "Muscle": ("macrodetails-universal/Muscle", 0.0, 1.0),
    "measure upperleg-height": ("measure/measure-upperleg-height-decr|incr", -1.0, 1.0), "measure lowerleg-height": ("measure/measure-lowerleg-height-decr|incr", -1.0, 1.0),
}


def run(base_path, targets_dir, mhm_path, obj_path, ruler_path, sheet_knee_fraction=None, sheet_hip_fraction=None):
    base = read_obj_vertices(base_path, include_helpers=True)
    T = Targets(targets_dir)
    mhm = read_mhm(mhm_path)
    ruler = json.loads(Path(ruler_path).read_text())["measures"]
    chords = {"upper": ruler["measure/measure-upperleg-height-decr|incr"], "lower": ruler["measure/measure-lowerleg-height-decr|incr"]}
    committed = read_obj_vertices(obj_path)
    out = {"inputs": {"base_obj_sha256_12": hashlib.sha256(Path(base_path).read_bytes()).hexdigest()[:12], "target_files": len(T.files),
                      "mhm_modifiers": mhm, "note": "MakeHuman master as fetched 2026-10-24; the rebuild omits pose, skeleton and proxies"}}
    ours = T.mesh(base, mhm)
    # The committed OBJ is exported in the .mhm's pose (standing02) and translated by the exporter, the rebuild is the rest pose where it is made. The legs
    # are not moved by that pose, so the legs must agree once the export's translation is removed; the upper body is reported for what it is worth.
    h = ours[:BODY_VERTICES, 1] - ours[:BODY_VERTICES, 1].min()
    span = h.max()
    rec = {}
    for name, mask in (("legs (below 40% of stature)", h < 0.40 * span), ("torso and head (above 62% of stature)", h > 0.62 * span)):
        d = (committed - ours[:BODY_VERTICES])[mask]
        off = d.mean(axis=0)
        r = np.linalg.norm(d - off, axis=1) * DM_TO_MM
        rec[name] = {"vertices": int(mask.sum()), "export_translation_dm": [float(x) for x in off], "residual_mm_max": float(r.max()), "residual_mm_mean": float(r.mean())}
    out["reconstruction_vs_committed_obj"] = rec
    # the three meshes
    states = {"base.obj (no targets)": None, "default human (macros at their defaults)": {}, "this sculpt (.mhm)": mhm}
    out["knee"] = {}
    for label, st in states.items():
        V = base if st is None else T.mesh(base, st)
        out["knee"][label] = knee_metrics(V, chords)
    out["knee"]["committed OBJ"] = knee_metrics(np.vstack([committed, base[BODY_VERTICES:]]), chords)
    k_base = out["knee"]["base.obj (no targets)"]["knee_fraction"]
    k_def = out["knee"]["default human (macros at their defaults)"]["knee_fraction"]
    k_sc = out["knee"]["this sculpt (.mhm)"]["knee_fraction"]
    out["shift"] = {"sculpt_minus_base_fraction": k_sc - k_base, "sculpt_minus_default_fraction": k_sc - k_def, "default_minus_base_fraction": k_def - k_base,
                    "sculpt_minus_base_mm_at_sculpt_stature": (k_sc - k_base) * out["knee"]["this sculpt (.mhm)"]["stature_mm"],
                    "sheet_knee_fraction": sheet_knee_fraction}
    # attribution of the shift between the default human and the sculpt, by modifier group
    attr = {}
    total = k_sc - k_def
    for name, mods in GROUPS.items():
        alone = {}
        for m in mods:
            alone[m] = mhm[m]
        k_alone = knee_metrics(T.mesh(base, alone), chords)["knee_fraction"]
        without = {m: v for m, v in mhm.items() if m not in mods}
        k_without = knee_metrics(T.mesh(base, without), chords)["knee_fraction"]
        attr[name] = {"one_at_a_time_from_default": k_alone - k_def, "left_out_of_the_sculpt": k_sc - k_without, "modifiers": {m: mhm[m] for m in mods}}
    attr_sum = sum(a["one_at_a_time_from_default"] for a in attr.values())
    out["attribution"] = {"total_fraction": total, "groups": attr, "one_at_a_time_sum": attr_sum, "interaction_residual": total - attr_sum}
    # slider changes that remove the shift
    sliders = {}
    for target_name, target in (("base.obj", k_base), ("sheet", sheet_knee_fraction)):
        if target is None:
            continue
        rows = {}
        for sname, (mod, lo, hi) in SLIDERS.items():
            def f(v, mod=mod):
                st = dict(mhm)
                st[mod] = v
                return knee_metrics(T.mesh(base, st), chords)["knee_fraction"] - target
            root, span = solve(f, lo, hi)
            row = {"modifier": mod, "current": mhm.get(mod, 0.0), "range": [lo, hi], "knee_fraction_over_range": [span[0] + target, span[1] + target]}
            if root is not None:
                st = dict(mhm)
                st[mod] = root
                m = knee_metrics(T.mesh(base, st), chords)
                row.update({"value_that_hits_target": float(root), "change": float(root - mhm.get(mod, 0.0)), "stature_mm_there": m["stature_mm"],
                            "hip_fraction_there": m["hip_fraction"]})
            else:
                row["value_that_hits_target"] = None
            rows[sname] = row
        sliders[target_name] = {"target_knee_fraction": target, "sliders": rows}
    out["slider_changes"] = sliders
    # three sliders together (Height and the two linear leg-height measures) so that the stature stays and the knee and hip land on the sheet's fractions
    if sheet_knee_fraction is not None and sheet_hip_fraction is not None:
        from scipy.optimize import least_squares
        names = ("Height", "measure upperleg-height", "measure lowerleg-height")
        mods = [SLIDERS[n][0] for n in names]
        lo = np.array([SLIDERS[n][1] for n in names])
        hi = np.array([SLIDERS[n][2] for n in names])
        stature0 = out["knee"]["this sculpt (.mhm)"]["stature_mm"]

        def resid(x):
            st = dict(mhm)
            st.update(dict(zip(mods, x)))
            m = knee_metrics(T.mesh(base, st), chords)
            return [(m["knee_fraction"] - sheet_knee_fraction) * 1000, (m["hip_fraction"] - sheet_hip_fraction) * 1000, (m["stature_mm"] - stature0) / 10]

        x0 = np.array([mhm[mods[0]], 0.0, 0.0])
        sol = least_squares(resid, x0, bounds=(lo, hi), diff_step=1e-3)
        st = dict(mhm)
        st.update(dict(zip(mods, sol.x)))
        m = knee_metrics(T.mesh(base, st), chords)
        out["combined_slider_solution"] = {
            "unknowns": dict(zip(names, [float(v) for v in sol.x])), "changes": dict(zip(names, [float(v - w) for v, w in zip(sol.x, x0)])),
            "targets": {"knee_fraction": sheet_knee_fraction, "hip_fraction": sheet_hip_fraction, "stature_mm": stature0},
            "result": m, "residuals": {"knee_fraction": m["knee_fraction"] - sheet_knee_fraction, "hip_fraction": m["hip_fraction"] - sheet_hip_fraction, "stature_mm": m["stature_mm"] - stature0},
            "note": "hip is the top of the Ruler upper-leg chord; the sliders other than these three, and the pose, are left as they are"}
    # the linear measure targets: what one unit of each leg-height slider does
    lin = {}
    for sname in ("measure upperleg-height", "measure lowerleg-height"):
        mod = SLIDERS[sname][0]
        for v in (-1.0, 1.0):
            st = dict(mhm)
            st[mod] = v
            lin[f"{sname} = {v:+.0f}"] = knee_metrics(T.mesh(base, st), chords)
    out["measure_slider_extremes"] = lin
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--base", required=True), ap.add_argument("--targets", required=True)
    ap.add_argument("--mhm", default=str(REPO / "data/makehuman/freyja-body-v1.mhm")), ap.add_argument("--obj", default=str(REPO / "data/makehuman/freyja-body-v1.obj"))
    ap.add_argument("--ruler", default=str(REPO / "data/makehuman/ruler_measures.json"))
    ap.add_argument("--sheet-knee-fraction", type=float, help="the sheet's KJC height over its stature (default: from params/snapshot.csv)")
    ap.add_argument("--out", default=str(REPO / "data/envelope/sculpt_attribution.json"))
    a = ap.parse_args(argv)
    sk = a.sheet_knee_fraction
    sh_ = None
    if sk is None:
        sys.path.insert(0, str(REPO / "tools"))
        from envelope import register
        n = register.sheet_nodes(REPO / "params/snapshot.csv")
        sk = n.kjc / n.stature_mm
        sh_ = n.hjc / n.stature_mm
    res = run(a.base, a.targets, a.mhm, a.obj, a.ruler, sk, sh_)
    Path(a.out).write_text(json.dumps(res, indent=1, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    for k, r in res["reconstruction_vs_committed_obj"].items():
        print(f"rebuild vs committed OBJ, {k}: residual max {r['residual_mm_max']:.3f} mm, mean {r['residual_mm_mean']:.3f} mm")
    for k, v in res["knee"].items():
        print(f"  {k}: knee {v['knee_mm']:.1f} mm of stature {v['stature_mm']:.1f} = {v['knee_fraction']:.4f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
