"""
Stage 2g fixtures for the foot and toe. The committed snapshot predates the `design` range (Joe adds it to the sheet for Part B), so the tests that need
a model with a toe build one from the committed snapshot's values plus the design values of docs/briefs/ariadne/stage2g-sheet-spec.md section 2, into a
temporary directory. Nothing here touches the tracked model or snapshot.
"""
import csv
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "sim" / "scripts"))
sys.path.insert(0, str(REPO / "checks"))
sys.path.insert(0, str(REPO / "tests"))

import pre_processor as pp  # noqa: E402

TEMPLATE = REPO / "sim" / "models" / "freyja_template.xml"
# The fixtures are built from a frozen copy of the snapshot as it was before the Stage 2g sheet rebuild (commit d9b5a48: chord lengths, the template's 41 mm and 165 mm
# foot, no design range). Part A was written against it, the walking reference (sim/benchmarks/walk_reference.json) belongs to it, and a fixture that follows the
# tracked snapshot would be rebuilt by every sheet edit. The tracked model is tested through the checks' context, not through these fixtures.
SNAPSHOT = REPO / "tests" / "fixtures" / "snapshot_pre_stage2g.csv"

# The sheet spec's design range for a 1700 mm stature and a 12.0 degree tilt, in the sheet's units (key, value).
SPEC_DESIGN = {
    "stand_pelvis_tilt_deg": 12.0, "foot_heel_behind_ankle_mm": 61.97, "foot_length_total_mm": 257.11, "foot_ball_length_mm": 190.10,
    "toe_hinge_ahead_ankle_mm": 128.12, "toe_tip_ahead_ankle_mm": 195.14, "foot_half_width_mm": 50.0, "toe_height_mm": 25.0,
    "toe_mass_fraction": 0.144, "toe_com_fraction": 0.436, "toe_stiffness_nm_per_deg": 0.25, "toe_damping_nm_s_per_rad": 0.05,
    "ansur_female_stature_mm": 1628.5, "ansur_female_footlength_mm": 246.3, "ansur_female_balloffootlength_mm": 182.1, "ansur_female_malleolusheight_mm": 62.7,
}
K_ADR0038 = 1.05035  # the scale factor of decisions/0038 at 1700 mm and 12 degrees (sheet spec section 1); the committed snapshot predates it
TOE_ROM = (("Toe", "Extension", 80.0), ("Toe", "Flexion", 0.0))


def snapshot_values():
    with SNAPSHOT.open(encoding="utf-8", newline="") as f:
        return {r["placeholder"]: float(r["value"]) for r in csv.DictReader(f)}


def scaled_snapshot_values(k=K_ADR0038):
    """The committed snapshot with the whole-foot rows scaled as ADR 0038 will scale them (see scale_foot_row), plus the design values in SI and the toe's range."""
    v = snapshot_values()
    for side in ("right", "left"):
        for col in ("length", "com_x", "com_y", "com_z"):
            v[f"foot_{side}_{col}"] *= k
        for col in pp.INERTIA_KEYS:
            v[f"foot_{side}_{col}"] *= k * k
    v.update({pp.DESIGN_KEYS[key][0]: x * pp.DESIGN_KEYS[key][1] for key, x in SPEC_DESIGN.items()})
    v.update({"toe_extension": 80.0, "toe_flexion": 0.0})
    return v


def design_table(**override):
    rows = {**SPEC_DESIGN, **override}
    return pp.RawTable("design", "BSIP Reference", 10, 1, [[k, v] for k, v in rows.items()])


def scale_foot_row(bsip, k=K_ADR0038):
    """The whole-foot BSIP row scaled the way ADR 0038 scales every segment: length and centre of mass by k, inertia by k squared, mass unchanged. Without
    this the committed (unscaled) foot row is too small an inertia to take the toe out of and the remainder breaks the triangle inequality, which says
    something about that row and nothing about the code."""
    header = [pp.column_key(h) for h in bsip.rows[0]]
    row = next(r for r in bsip.rows[1:] if pp.ident(r[0]) == "foot")
    for col in ("length", "com_x", "com_y", "com_z"):
        row[header.index(col)] *= k
    for col in pp.INERTIA_KEYS:
        row[header.index(col)] *= k * k


def tables(design=None, toe_rom=True, scaled=True):
    """Raw sheet tables that reproduce the committed snapshot (foot row scaled by ADR 0038 unless `scaled` is false), plus the design range and the toe's range
    of motion."""
    from test_gate import rebuild_tables_from_snapshot
    t = rebuild_tables_from_snapshot(SNAPSHOT)
    if scaled:
        scale_foot_row(t["bsip"])
    if toe_rom:
        t["rom"].rows = t["rom"].rows + [[j, m, v] for j, m, v in TOE_ROM]
    t["design"] = design if design is not None else design_table()
    return t


def build_model_file(directory, design=None, template=TEMPLATE, scaled=True, **kw):
    """Build the fixture model into `directory` and return its path (no snapshot, no archive, no checks)."""
    directory = Path(directory)
    out = directory / "freyja_fixture.xml"
    pp.build_model(tables(design, scaled=scaled), template=template, output=out, failed_output=directory / "failed.xml", archive=False, **kw)
    return out


_CACHE = {}


def fixture_model_path():
    """The default fixture model, built once per process in a temporary directory that lives as long as the process."""
    if "path" not in _CACHE:
        _CACHE["dir"] = tempfile.TemporaryDirectory()
        _CACHE["path"] = build_model_file(_CACHE["dir"].name)
    return _CACHE["path"]
