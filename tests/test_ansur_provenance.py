"""
Stage 2g T2 (ANSUR provenance): the `design` range carries four `ansur_female_*` keys that nothing else reads. They are the sheet's record of where the
foot lengths and the ankle height came from, so a test recomputes the four means from the public ANSUR II female CSV (outside git, `data/ansur2/raw/`)
and compares them with the sheet's values to 0.05 mm. The test is skipped when the file is absent.

Run from the repo root:
    python -m pytest tests/test_ansur_provenance.py
"""
import csv
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "tests"))
sys.path.insert(0, str(REPO / "sim" / "scripts"))

import foot_help as fh  # noqa: E402
import pre_processor as pp  # noqa: E402
import snapshot_diag as sd  # noqa: E402

CSV = REPO / "data" / "ansur2" / "raw" / "ANSUR_II_FEMALE_Public.csv"
TOL_MM = 0.05  # the brief: the sheet's values are ANSUR's means rounded to 0.1 mm, so a rounding error is 0.05 mm at most
# sheet key -> the CSV column it summarises
KEYS = {"ansur_female_stature_mm": "stature", "ansur_female_footlength_mm": "footlength",
        "ansur_female_balloffootlength_mm": "balloffootlength", "ansur_female_malleolusheight_mm": "lateralmalleolusheight"}


def differences(sheet_mm: dict, csv_path) -> dict:
    """{sheet key: sheet value minus the CSV mean, mm}."""
    st = sd.ansur_stats(csv_path, list(KEYS.values()))
    return {k: sheet_mm[k] - st[col]["mean"] for k, col in KEYS.items()}


def snapshot_mm():
    """The sheet's four values as the committed snapshot holds them (metres there), or None before the build that adds them."""
    v = fh.snapshot_values()
    names = {k: pp.DESIGN_KEYS[k][0] for k in KEYS}
    return {k: v[n] * 1000.0 for k, n in names.items()} if all(n in v for n in names.values()) else None


def test_the_design_reader_carries_the_four_ansur_keys_in_metres_and_nothing_else_uses_them():
    r = pp.Report()
    out = pp.read_design(fh.design_table(), r)
    assert r.errors == [] and r.warnings == []
    assert out["ansur_female_stature"].value == pytest.approx(1.6285) and out["ansur_female_malleolusheight"].value == pytest.approx(0.0627)
    assert out["ansur_female_footlength"].source.startswith("'BSIP Reference'!B")
    assert {pp.DESIGN_KEYS[k][0] for k in KEYS} <= set(out)


def test_the_stature_bound_is_two_metres_and_the_others_still_catch_a_wrong_unit():
    r = pp.Report()
    pp.read_design(fh.design_table(ansur_female_stature_mm=1999.0), r)
    assert r.errors == []
    for bad in (2100.0, 0.0, -1.0):
        r = pp.Report()
        pp.read_design(fh.design_table(ansur_female_stature_mm=bad), r)
        assert any("ansur_female_stature_mm" in e and "outside" in e for e in r.errors), bad
    r = pp.Report()
    rows = [[k, v] for k, v in fh.SPEC_DESIGN.items() if k != "ansur_female_footlength_mm"]
    pp.read_design(pp.RawTable("design", "BSIP Reference", 10, 1, rows), r)
    assert any("ansur_female_footlength_mm" in e and "missing" in e for e in r.errors)


@pytest.mark.skipif(not CSV.exists(), reason="data/ansur2/raw/ANSUR_II_FEMALE_Public.csv is not available")
def test_the_spec_values_are_the_means_of_the_public_csv():
    d = differences({k: fh.SPEC_DESIGN[k] for k in KEYS}, CSV)
    assert all(abs(x) <= TOL_MM for x in d.values()), d


@pytest.mark.skipif(not CSV.exists(), reason="data/ansur2/raw/ANSUR_II_FEMALE_Public.csv is not available")
def test_the_committed_snapshots_values_are_the_means_of_the_public_csv_once_the_build_has_added_them():
    s = snapshot_mm()
    if s is None:
        pytest.skip("the committed snapshot predates the ansur_* keys; the next fy build adds them")
    d = differences(s, CSV)
    assert all(abs(x) <= TOL_MM for x in d.values()), d


def test_mutation_a_sheet_value_off_by_more_than_the_tolerance_fails_the_comparison(tmp_path):
    f = tmp_path / "a.csv"
    with f.open("w", newline="", encoding="latin-1") as fp:
        w = csv.writer(fp)
        w.writerow(["SubjectId", *KEYS.values()])
        for i, x in enumerate((0, 1, 2, 3)):
            w.writerow([i, 1600 + x * 10, 240 + x, 180 + x, 60 + x])
    good = {"ansur_female_stature_mm": 1615.0, "ansur_female_footlength_mm": 241.5, "ansur_female_balloffootlength_mm": 181.5, "ansur_female_malleolusheight_mm": 61.5}
    assert all(abs(x) <= TOL_MM for x in differences(good, f).values())
    for k in KEYS:
        for delta in (0.06, -0.06, 1.0):
            bad = dict(good, **{k: good[k] + delta})
            assert abs(differences(bad, f)[k]) > TOL_MM, (k, delta)
