"""Brief 11 Part B: the arms' vertices do not reach a leg output. Displacing or scaling them leaves the thigh, shank and foot volumes, the ankle section centroid and the thigh rod
example bit-identical. A whole leg build per variant (about a minute each), so slow and outside `fy test --quick`."""
import sys
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "tools"))

from envelope import decompose, features, frames, oracle, trial  # noqa: E402

EX = REPO / "data" / "envelope" / "examples"


def leg_outputs(inp) -> dict:
    feats = trial.find_features(inp)
    reg = trial.make_registration(inp, feats, "chords")
    out = {}
    for name in trial.SEGMENTS:
        res = trial.build_segment(inp, feats, reg, name, trial.VOXEL_MM)
        out[f"{name}_volume"] = res.seg.volume()
        if name == "thigh":
            res.seg.meta = {"segment": "thigh_R", "origin_xyz": [float(x) for x in res.origin_xyz]}
            off = frames.segment_offset_mm("thigh_R", res.seg.meta)
            shapes = oracle.read_shapes(EX / "rod_shapes.yaml")
            for pose in ("feasible", "infeasible"):
                out[f"rod_{pose}"] = oracle.clearance(res.seg, shapes, oracle.read_poses(EX / f"rod_{pose}_poses.csv"), 0.0, frame_offset_mm=off)["margin_mm"]
    out["ankle_centroid"] = feats["raster"].right_section(reg.mesh_nodes["ajc"], 0.0)[1]
    return out


@pytest.fixture(scope="module")
def body():
    inp = trial.load_inputs(REPO, REPO / "data/makehuman/freyja-body-v3.obj")
    arm = decompose.arm_vertices(inp.V, inp.F, trial.find_features(inp)["crotch_apex_mm"])
    return inp, arm, leg_outputs(inp)


def moved(inp, V):
    return SimpleNamespace(**{**vars(inp), "V": V})


def displaced(V, arm):
    W = V.copy()
    W[arm] += [0.7, 1.3, 0.0]
    W[arm & (V[:, 1] < 0)] += [0.0, -6.6, 0.0]         # the right arm outward past a whole voxel, the left one inward: both bounding faces move
    return W


def scaled(V, arm):
    W = V.copy()
    pivot = np.array([0.0, 0.0, V[arm, 2].max()])
    W[arm] = pivot + (V[arm] - pivot) * [1.0, 1.013, 1.0]
    return W


@pytest.mark.slow
@pytest.mark.parametrize("change", [displaced, scaled], ids=lambda f: f.__name__)
def test_moving_the_arms_leaves_every_leg_output_bit_identical(body, change):
    inp, arm, base = body
    got = leg_outputs(moved(inp, change(inp.V, arm)))
    assert {k: got[k] for k in got if got[k] != base[k]} == {}


@pytest.mark.slow
def test_mutation_the_bounding_box_origin_fails_the_above(body, monkeypatch):
    inp, arm, base = body

    def old(self, V, F, z_hi, h=features.GRID_MM, margin=6.0):
        x0, x1 = V[:, 0].min() - margin, V[:, 0].max() + margin
        y0, y1 = V[:, 1].min() - margin, V[:, 1].max() + margin
        self.h, self.o = h, np.array([x0, y0, -margin])
        shape = (int(np.ceil((x1 - x0) / h)), int(np.ceil((y1 - y0) / h)), int(np.ceil((z_hi + margin) / h)))
        self.inside, self.odd = features.field.parity_inside(V, F, self.o, h, shape)
    monkeypatch.setattr(features.BodyRaster, "__init__", old)
    got = leg_outputs(moved(inp, displaced(inp.V, arm)))
    assert any(got[k] != leg_outputs(inp)[k] for k in got)
