"""
Stage 2g T8: sim/scripts/old_box_diag.py builds, in memory, a copy of the model whose foot box is the Stage 2 one. The copy must differ from the model in the two foot
boxes and the two removed toe boxes and in nothing else.

Run from the repo root:
    python -m pytest tests/test_old_box_diag.py
"""
import sys
from pathlib import Path

import mujoco
import numpy as np
import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "sim" / "scripts"))

import old_box_diag as ob  # noqa: E402

XML = (REPO / "sim" / "models" / "freyja.xml").read_text(encoding="utf-8")
NEW = mujoco.MjModel.from_xml_path(str(REPO / "sim" / "models" / "freyja.xml"))
OLD = mujoco.MjModel.from_xml_string(ob.old_box_xml(XML))


def foot_box(model, side):
    g = next(g for g in range(model.ngeom) if model.geom_bodyid[g] == model.body(f"foot_{side}").id and model.geom_type[g] == mujoco.mjtGeom.mjGEOM_BOX)
    return model.geom_pos[g], model.geom_size[g]


@pytest.mark.parametrize("side", ["right", "left"])
def test_the_foot_box_runs_from_41_mm_behind_the_ankle_to_165_mm_ahead_at_the_same_height_and_width(side):
    pos, size = foot_box(OLD, side)
    assert pos[0] - size[0] == pytest.approx(-0.04125, abs=1e-9) and pos[0] + size[0] == pytest.approx(0.165, abs=1e-9)
    p, s = foot_box(NEW, side)
    assert pos[2] == p[2] and size[1] == s[1] and size[2] == s[2] and pos[1] == p[1]


def test_the_toe_boxes_are_gone_and_nothing_else_changed():
    boxes = lambda m, body: [g for g in range(m.ngeom) if m.geom_bodyid[g] == m.body(body).id]  # noqa: E731
    assert boxes(NEW, "toe_right") and not boxes(OLD, "toe_right") and not boxes(OLD, "toe_left")
    assert OLD.nbody == NEW.nbody and OLD.njnt == NEW.njnt and OLD.ngeom == NEW.ngeom - 2
    assert np.array_equal(OLD.body_mass, NEW.body_mass) and np.array_equal(OLD.body_inertia, NEW.body_inertia) and np.array_equal(OLD.jnt_range, NEW.jnt_range)
    assert np.array_equal(OLD.body_pos, NEW.body_pos) and np.array_equal(OLD.body_ipos, NEW.body_ipos)


def test_mutation_a_model_text_without_the_expected_boxes_is_refused():
    with pytest.raises(ValueError):
        ob.old_box_xml(XML.replace('<body name="toe_right"', '<body name="toes_right"'))
