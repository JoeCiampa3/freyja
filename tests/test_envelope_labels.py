"""Brief 12: the arm-labelled vertex set does not depend on the raster's phase. The scan on v3 is slow (about 20 s a phase, a whole-body parity raster each) and sits outside `fy test --quick`;
the mesh-level rule is tested on synthetic tubes in test_arm_vertices_*."""
import sys
from pathlib import Path

import numpy as np
import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "tools"))

from envelope import decompose, features, field, sheet, trial  # noqa: E402
from input_sets import ENVELOPE  # noqa: E402

H = 2.0
Z_SHIFTS = [(0.0, 0.0, d) for d in np.arange(0.25, 2.0, 0.25)]
XY_SHIFTS = [tuple(d if i == j else 0.0 for j in range(3)) for i in (0, 1) for d in (0.5, 1.0, 1.5)]
DIAGONAL = [(d, d, d) for d in (0.5, 1.0, 1.5)]


@pytest.fixture(scope="module")
def world():
    inp = trial.load_inputs(REPO, REPO / "data/makehuman/freyja-body-v3.obj")
    apex = trial.find_features(inp)["crotch_apex_mm"]
    o0 = np.array([inp.V[:, 0].min() - 6.0, inp.V[:, 1].min() - 6.0, -6.0])          # the pre-snap origin that brief 11's phases are measured from

    def arms_at(shift, labels=decompose.labels):
        V, F = inp.V, inp.F
        r = object.__new__(features.BodyRaster)
        r.h, r.o = H, o0 + np.array(shift, float)
        hi = np.array([V[:, 0].max() + 6.0, V[:, 1].max() + 6.0, inp.stature_mesh + 10.0])
        r.inside, r.odd = field.parity_inside(V, F, r.o, H, tuple(int(n) for n in np.ceil((hi - r.o) / H)))
        neck = decompose.neck_height(decompose.profile(r), inp.stature_mesh)
        return np.asarray(labels(V, F, r, apex, neck)) == "arms"
    return arms_at, arms_at((0.0, 0.0, 0.0)), o0


@pytest.mark.slow
@pytest.mark.inputs(*ENVELOPE)
@pytest.mark.parametrize("shift", Z_SHIFTS + XY_SHIFTS + DIAGONAL + ["snap"], ids=str)
def test_the_arm_set_is_the_same_at_every_raster_phase(world, shift):
    arms_at, base, o0 = world
    s = np.floor(o0 / H) * H - o0 if isinstance(shift, str) else shift
    assert int((arms_at(s) != base).sum()) == 0


@pytest.mark.slow
@pytest.mark.inputs(*ENVELOPE)
def test_mutation_the_raster_rule_flips_the_arm_set_at_the_diagonal_phase(world):
    arms_at, base, _ = world
    old = lambda V, F, r, apex, neck: decompose.vertex_regions(V, r, {"apex": apex, "neck": neck})
    assert (arms_at((1.5, 1.5, 1.5), old) != arms_at((0.0, 0.0, 0.0), old)).sum() > 0        # the fix reverted: the scan's assertion fails


# ---- the rule on synthetic bodies --------------------------------------------------------------------------------------------------------

def _box_grid(lo, hi, n=(4, 4, 8)):
    """A closed box mesh as (V, F): six grids of quads, split into triangles, with shared vertices."""
    xs, ys, zs = (np.linspace(lo[i], hi[i], n[i] + 1) for i in range(3))
    idx, V = {}, []

    def vid(i, j, k):
        if (i, j, k) not in idx:
            idx[(i, j, k)] = len(V)
            V.append((xs[i], ys[j], zs[k]))
        return idx[(i, j, k)]
    F = []
    for axis in range(3):
        a, b = [x for x in range(3) if x != axis]
        for side in (0, n[axis]):
            for p in range(n[a]):
                for q in range(n[b]):
                    c = [[0, 0, 0] for _ in range(4)]
                    for w, (dp, dq) in enumerate(((0, 0), (1, 0), (1, 1), (0, 1))):
                        c[w][axis], c[w][a], c[w][b] = side, p + dp, q + dq
                    t = [vid(*x) for x in c]
                    F += [(t[0], t[1], t[2]), (t[0], t[2], t[3])]
    return np.array(V, float), np.array(F, int)


def _weld(parts):
    """Merge the box meshes, welding vertices that coincide (a part attaches to another by sharing a grid line)."""
    V, F, seen = [], [], {}
    for v, f in parts:
        m = []
        for p in v:
            key = tuple(np.round(p, 6))
            if key not in seen:
                seen[key] = len(V)
                V.append(p)
            m.append(seen[key])
        F.append(np.array(m)[f])
    return np.array(V), np.vstack(F)


def _body():
    """A trunk with two legs below the apex at z = 100, an arm hanging from a shoulder bar on each side (it joins the bar at z = 300), and an ear on the head."""
    bar_y = (-200.0, 200.0)
    parts = [_box_grid((-20, -40, 100), (20, 40, 300), (2, 4, 10)),                           # trunk
             _box_grid((-20, -40, 300), (20, 40, 340), (2, 4, 2)),
             _box_grid((-20, -40, 0), (20, -10, 100), (2, 3, 5)), _box_grid((-20, 10, 0), (20, 40, 100), (2, 3, 5)),      # legs
             _box_grid((-20, -200, 300), (20, -40, 340), (2, 8, 2)), _box_grid((-20, 40, 300), (20, 200, 340), (2, 8, 2)),  # shoulder bars
             _box_grid((-20, -200, 150), (20, -160, 300), (2, 2, 6)), _box_grid((-20, 160, 150), (20, 200, 300), (2, 2, 6)),  # arms
             _box_grid((-20, -40, 340), (20, 40, 420), (2, 4, 4)),                                                         # head
             _box_grid((-20, 40, 380), (20, 60, 420), (2, 2, 2))]                                                          # ear, attached to the head
    return _weld(parts)


def test_arm_vertices_are_the_components_that_join_the_core_last_and_stop_at_the_junction():
    V, F = _body()
    m = decompose.arm_vertices(V, F, 100.0)
    arm_box = (np.abs(V[:, 1]) >= 160.0) & (V[:, 2] < 300.0 - 1e-9)
    assert m[arm_box].all() and not m[(V[:, 2] > 300.0) | ((np.abs(V[:, 1]) < 160.0) & (V[:, 2] < 300.0))].any()        # the bar's vertices tie at the junction height: either way


def test_arm_vertices_hold_neither_the_ear_nor_the_legs():
    V, F = _body()
    m = decompose.arm_vertices(V, F, 100.0)
    assert not m[V[:, 2] > 300.0].any() and not m[V[:, 2] <= 100.0].any()


def test_arm_vertices_do_not_depend_on_where_the_raster_would_sit():
    V, F = _body()
    assert (decompose.arm_vertices(V + np.array([0.3, 0.0, 0.7]), F, 100.7) == decompose.arm_vertices(V, F, 100.0)).all()


def test_a_body_with_no_separate_arm_stops():
    V, F = _box_grid((-20, -40, 0), (20, 40, 300), (2, 4, 10))
    with pytest.raises(sheet.StopAndAsk):
        decompose.arm_vertices(V, F, 100.0)
