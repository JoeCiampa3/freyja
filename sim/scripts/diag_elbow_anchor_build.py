"""Memo 43 diagnostic, step 1 (read-only): rebuild the right and left arm sides in memory exactly as `fy envelope gates` does and pickle them to the path given.
Writes nothing in the repo and touches no cache. Usage: python sim/scripts/diag_elbow_anchor_build.py OUT.pkl"""
import pickle
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))
from envelope import arms, bodies, masses, ruler, trial  # noqa: E402

inp = trial.load_inputs(ROOT, ROOT / "data/makehuman/freyja-body-v2.obj")
feats = trial.find_features(inp)
reg = trial.make_registration(inp, feats, "chords")
tb = bodies.build(inp, feats, reg, masses.load_dumas_table1(ROOT), 2.0)
rm, sh = ruler.load(ROOT), arms.sheet_arm(ROOT / "params/snapshot.csv")
out = {"inp": inp, "tb": tb, "rm": rm, "sh": sh, "R": arms.build_side(inp, tb, rm, sh, "R", 2.0), "L": arms.build_side(inp, tb, rm, sh, "L", 2.0)}
with open(sys.argv[1], "wb") as f:
    pickle.dump(out, f)
print("ok", {s: out[s]["reg"]["stretch"] for s in "RL"})
